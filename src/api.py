# ============================================================================
# Bot-IAM — Backend API
#
# Pipeline RAG (Retrieval-Augmented Generation) vectoriel pour répondre à des
# questions sur la matrice IAM (fichier Excel).
#
# Flux global :
#   1. Au démarrage : chaque ligne du .xlsx est transformée en VECTEUR d'embedding
#      (un "résumé sémantique" de la ligne sous forme de 3072 nombres).
#   2. Quand une question arrive : on embed aussi la question, puis on cherche
#      les lignes les plus PROCHES SÉMANTIQUEMENT (similarité cosinus).
#   3. On envoie ces lignes + la question à Gemini, qui rédige la réponse.
# ============================================================================

import os
import pathlib
import re
import time
import numpy as np
import pandas as pd
from dotenv import load_dotenv
import google.genai as genai
from google.genai import types
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

# --- Constantes ---------------------------------------------------------------

# Modèle qui RÉDIGE la réponse finale. flash-lite est choisi pour son quota
# free-tier plus généreux (≈1000 req/jour) que flash (≈20 req/jour).
CHAT_MODEL = "gemini-2.5-flash-lite"

# Modèle qui transforme un texte en VECTEUR (embedding) de dimension 3072.
# Deux textes proches sémantiquement → vecteurs proches dans l'espace 3072-dim.
EMBEDDING_MODEL = "gemini-embedding-001"

# Le quota gratuit Gemini est de 100 requêtes/min pour les embeddings, et
# CHAQUE item dans `contents=[...]` compte comme une requête séparée.
# On envoie donc 50 items par appel, et on attend 65s entre deux appels
# (>60s pour passer la fenêtre glissante de rate-limit en toute sécurité).
EMBEDDING_BATCH_SIZE = 50
EMBEDDING_BATCH_PAUSE_SECONDS = 65


# --- Configuration et chargement ---------------------------------------------

def configure_gemini():
    """Charge la clé API depuis .env et crée le client Gemini."""
    load_dotenv()
    # On accepte les deux noms de variable usuels pour ne pas piéger l'utilisateur.
    api_key = os.getenv("GOOGLE_API_KEY") or os.getenv("GEMINI_API_KEY")
    if not api_key:
        raise ValueError("Clé API non trouvée. Définissez GOOGLE_API_KEY ou GEMINI_API_KEY.")

    # Note : on n'envoie volontairement AUCUN appel de test ici. Un simple
    # generate_content("test") consommerait 1 requête sur le quota journalier
    # à chaque redémarrage du serveur — gaspillage qu'on évite.
    client = genai.Client(api_key=api_key)
    print("Configuration de l'API Gemini réussie.")
    return client


def _embed_call_with_retry(client, batch, task_type, max_retries=4):
    """
    Appelle embed_content avec retry exponentiel sur les erreurs 429 (rate-limit).

    Quand Gemini renvoie un 429, le message contient un champ retryDelay qui
    indique COMBIEN DE TEMPS attendre avant de re-essayer. On parse ce délai
    et on l'utilise — plus fiable qu'un backoff arbitraire.
    """
    for attempt in range(max_retries):
        try:
            return client.models.embed_content(
                model=EMBEDDING_MODEL,
                contents=batch,
                # task_type optimise les embeddings pour leur usage :
                #   RETRIEVAL_DOCUMENT pour les documents stockés,
                #   RETRIEVAL_QUERY pour les questions à matcher.
                config=types.EmbedContentConfig(task_type=task_type),
            )
        except Exception as e:
            msg = str(e)
            # Si c'est un rate-limit ET qu'il nous reste des tentatives, on attend.
            if ("429" in msg or "RESOURCE_EXHAUSTED" in msg) and attempt < max_retries - 1:
                # On extrait le retryDelay du message d'erreur (format JSON-ish).
                m = re.search(r"'retryDelay': '([\d.]+)s'", msg) or re.search(r"retry in ([\d.]+)s", msg)
                delay = float(m.group(1)) if m else 60.0
                # Petit buffer de sécurité + plafond pour éviter une attente déraisonnable.
                delay = min(delay + 2, 90)
                print(f"Rate limit atteint, attente {delay:.1f}s avant retry (tentative {attempt+1}/{max_retries})...")
                time.sleep(delay)
                continue
            # Toute autre erreur (auth, réseau, etc.) : on remonte sans retry.
            raise
    raise RuntimeError("Max retries exceeded for embed_content")


def _embed_texts(client, texts, task_type):
    """
    Transforme une liste de textes en matrice d'embeddings, batch par batch.

    Retour : np.ndarray de shape (len(texts), 3072) en float32.
             float32 est suffisamment précis pour la similarité cosinus et
             divise par 2 l'empreinte mémoire/disque par rapport à float64.
    """
    vectors = []
    total_batches = (len(texts) + EMBEDDING_BATCH_SIZE - 1) // EMBEDDING_BATCH_SIZE
    for batch_idx, i in enumerate(range(0, len(texts), EMBEDDING_BATCH_SIZE)):
        batch = texts[i:i + EMBEDDING_BATCH_SIZE]
        # Pause AVANT les batches >0 pour éviter de griller la fenêtre de rate-limit.
        if batch_idx > 0:
            print(f"Pause {EMBEDDING_BATCH_PAUSE_SECONDS}s entre batches (rate limit)...")
            time.sleep(EMBEDDING_BATCH_PAUSE_SECONDS)
        print(f"  Batch {batch_idx+1}/{total_batches} ({len(batch)} items)...")
        result = _embed_call_with_retry(client, batch, task_type)
        # result.embeddings est une liste d'objets ContentEmbedding ;
        # .values est la liste de 3072 floats du vecteur.
        vectors.extend(e.values for e in result.embeddings)
    return np.array(vectors, dtype=np.float32)


def load_iam_data(client):
    """
    Charge la matrice IAM (Excel) et associe à chaque ligne son embedding.

    Stratégie de cache :
      - Au premier démarrage : on calcule les embeddings (lent, coûteux)
        et on les sauvegarde dans un fichier .npz à côté du .xlsx.
      - Aux démarrages suivants : on relit le .npz → instantané.
      - Le cache est invalidé si le .xlsx a été modifié (mtime différent)
        ou si le nombre de lignes a changé.
    """
    SCRIPT_DIR = pathlib.Path(__file__).parent.resolve()
    PROJECT_ROOT = SCRIPT_DIR.parent
    DATA_FILE_PATH = PROJECT_ROOT / "data" / "matriceiam.xlsx"
    CACHE_FILE_PATH = PROJECT_ROOT / "data" / "matriceiam_embeddings.npz"

    if not DATA_FILE_PATH.exists():
        raise FileNotFoundError(f"Fichier introuvable : {DATA_FILE_PATH}")

    df = pd.read_excel(DATA_FILE_PATH)

    # Pour pouvoir embedder une ligne, il faut un SEUL texte par ligne.
    # On concatène toutes les colonnes en une chaîne.
    # Important : str(v) au lieu de .astype(str) car en pandas 3.x, astype ne
    # convertit pas systématiquement les NaN floats en strings → on tombe sur
    # "TypeError: sequence item 0: expected str instance, float found".
    df['searchable_text'] = df.apply(
        lambda row: ' '.join(str(v) for v in row.values), axis=1
    )

    # mtime = timestamp de dernière modification du .xlsx, sert de "version" pour le cache.
    data_mtime = DATA_FILE_PATH.stat().st_mtime
    embeddings = None
    if CACHE_FILE_PATH.exists():
        try:
            cached = np.load(CACHE_FILE_PATH)
            # Validité : même fichier source (mtime identique) ET même nombre de lignes.
            if (float(cached['mtime'][0]) == data_mtime
                    and len(cached['embeddings']) == len(df)):
                embeddings = cached['embeddings']
                print(f"Embeddings rechargés depuis le cache : {embeddings.shape}")
        except Exception as e:
            # Cache corrompu : on log et on régénère plutôt que de crasher.
            print(f"Cache d'embeddings illisible, régénération : {e}")

    if embeddings is None:
        print(f"Génération des embeddings pour {len(df)} lignes...")
        embeddings = _embed_texts(client, df['searchable_text'].tolist(), "RETRIEVAL_DOCUMENT")
        # On sauvegarde mtime sous forme de tableau (np.savez stocke des arrays).
        np.savez(CACHE_FILE_PATH, embeddings=embeddings, mtime=np.array([data_mtime]))
        print(f"Embeddings sauvegardés : {embeddings.shape}")

    print(f"Fichier de données chargé : {len(df)} lignes.")
    return df, embeddings


# --- Initialisation de l'API et des ressources -------------------------------

app = FastAPI()

# CORS : autorise le frontend Next.js (port 3000) à appeler ce backend (port 8000).
# Sans ça, le navigateur bloquerait les requêtes cross-origin.
origins = [
    "http://localhost:3000",
]
app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Les ressources lourdes (client Gemini, DataFrame, matrice d'embeddings) sont
# chargées UNE SEULE FOIS au démarrage du serveur, pas à chaque requête.
# Si l'initialisation échoue, on met les variables à None et on renverra
# un 503 sur l'endpoint plutôt que de planter le process.
try:
    gemini_client = configure_gemini()
    iam_df, iam_embeddings = load_iam_data(gemini_client)
except Exception as e:
    print(f"ERREUR CRITIQUE AU DÉMARRAGE : {e}")
    gemini_client = None
    iam_df = None
    iam_embeddings = None


# --- Logique de recherche vectorielle (Retrieval) ----------------------------

def find_relevant_context(query: str, client, df: pd.DataFrame, embeddings: np.ndarray, top_k=5, min_similarity=0.4):
    """
    Trouve les lignes du DataFrame les plus pertinentes pour la question.

    Étapes :
      1. Embed la question (en mode RETRIEVAL_QUERY, optimisé pour matcher).
      2. Calcule la similarité COSINUS entre la question et chaque document.
      3. Garde le top-k au-dessus du seuil min_similarity.

    Pourquoi le seuil ? Sans lui, on renverrait toujours k lignes même quand
    la question est hors-sujet, ce qui pousserait Gemini à halluciner. Avec
    le seuil, on peut renvoyer "rien" et le modèle dira honnêtement
    "Je n'ai pas trouvé l'information".
    """
    if df is None or embeddings is None:
        return "Les données de la matrice IAM ne sont pas chargées."

    # _embed_texts renvoie une matrice ; on prend la première (et unique) ligne.
    query_vec = _embed_texts(client, [query], "RETRIEVAL_QUERY")[0]

    # Similarité cosinus = produit scalaire des vecteurs NORMALISÉS.
    # Mathématiquement : cos(A,B) = (A·B) / (||A|| * ||B||).
    # On divise chaque vecteur par sa norme → ||v||=1 → le produit scalaire
    # devient directement le cosinus. Le +1e-10 évite la division par zéro
    # sur un vecteur nul (cas pathologique).
    q_norm = query_vec / (np.linalg.norm(query_vec) + 1e-10)
    d_norm = embeddings / (np.linalg.norm(embeddings, axis=1, keepdims=True) + 1e-10)
    # d_norm @ q_norm = produit matriciel → vecteur des N similarités.
    sims = d_norm @ q_norm

    # argsort(-sims) trie par similarité décroissante ; on garde les k premiers.
    top_idx = np.argsort(-sims)[:top_k]
    # Filtre par seuil : on ne garde que les vraies correspondances.
    top_idx = [int(i) for i in top_idx if sims[i] >= min_similarity]

    if not top_idx:
        return "Aucun contexte pertinent n'a été trouvé dans les documents."

    # On retire la colonne searchable_text (artefact interne) avant de sérialiser.
    # to_csv produit un texte tabulaire compact, facile à lire pour le LLM.
    results = df.iloc[top_idx].drop(columns=['searchable_text'], errors='ignore')
    return results.to_csv(index=False)


# --- Endpoint HTTP -----------------------------------------------------------

class Question(BaseModel):
    """Schéma du body JSON attendu : {"query": "ma question"}."""
    query: str


@app.post("/api/ask")
async def ask_bot(question: Question):
    # Si une ressource n'a pas pu être chargée au démarrage, on refuse poliment.
    if not gemini_client or iam_df is None or iam_embeddings is None:
        raise HTTPException(status_code=503, detail="Le service est indisponible, le backend n'a pas pu s'initialiser correctement.")

    # --- R : Retrieval ---
    # On récupère les lignes du .xlsx les plus pertinentes pour la question.
    relevant_context = find_relevant_context(question.query, gemini_client, iam_df, iam_embeddings)

    # --- A : Augmented ---
    # On construit le prompt en injectant le contexte trouvé. La consigne
    # "UNIQUEMENT sur le contexte" + la phrase de repli forcent le modèle à
    # rester factuel et à admettre son ignorance plutôt qu'à halluciner.
    prompt = f"""Contexte:
{relevant_context}
---
Question: {question.query}
---
En te basant UNIQUEMENT sur le contexte ci-dessus, réponds à la question. Si le contexte ne contient pas la réponse, dis "Je n'ai pas trouvé l'information dans mes documents."."""

    # --- G : Generation ---
    # Appel à Gemini, avec le même mécanisme de retry-with-backoff qu'au démarrage.
    # On limite à 3 tentatives car ici c'est une requête utilisateur en direct :
    # attendre 65s × plusieurs fois rendrait l'API inutilisable.
    for attempt in range(3):
        try:
            response = gemini_client.models.generate_content(model=CHAT_MODEL, contents=prompt)
            return {"answer": response.text}
        except Exception as e:
            msg = str(e)
            if ("429" in msg or "RESOURCE_EXHAUSTED" in msg) and attempt < 2:
                m = re.search(r"'retryDelay': '([\d.]+)s'", msg) or re.search(r"retry in ([\d.]+)s", msg)
                delay = float(m.group(1)) if m else 30.0
                delay = min(delay + 2, 65)
                print(f"Rate limit chat, attente {delay:.1f}s avant retry...")
                time.sleep(delay)
                continue
            # Toute autre erreur (ou rate-limit après les 3 tentatives) : on
            # remonte un 500 propre côté HTTP, avec le message d'origine.
            raise HTTPException(status_code=500, detail=f"Erreur lors de l'appel à l'API Gemini: {e}")
