import os
import pathlib
import pandas as pd
from dotenv import load_dotenv
import google.genai as genai
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

# --- Fonctions de configuration et de chargement ---

def configure_gemini():
    """Charge la clé API et configure le client Gemini."""
    load_dotenv()
    api_key = os.getenv("GOOGLE_API_KEY") or os.getenv("GEMINI_API_KEY")
    if not api_key:
        raise ValueError("Clé API non trouvée. Définissez GOOGLE_API_KEY ou GEMINI_API_KEY.")
    
    client = genai.Client(api_key=api_key)
    # On effectue un appel simple pour vérifier que la clé API est valide et que le service est accessible.
    client.generate_content("test")
    print("Configuration de l'API Gemini réussie.")
    return client

def load_iam_data():
    """Charge la matrice IAM depuis le fichier Excel."""
    SCRIPT_DIR = pathlib.Path(__file__).parent.resolve()
    PROJECT_ROOT = SCRIPT_DIR.parent
    DATA_FILE_PATH = PROJECT_ROOT / "data" / "matriceiam.xlsx"
    
    if not DATA_FILE_PATH.exists():
        raise FileNotFoundError(f"Fichier introuvable : {DATA_FILE_PATH}")
        
    df = pd.read_excel(DATA_FILE_PATH)
    # Pour simplifier la recherche, nous créons une nouvelle colonne 'searchable_text'
    # qui contient tout le texte d'une ligne, en minuscules.
    df['searchable_text'] = df.apply(
        lambda row: ' '.join(row.astype(str).values), axis=1
    ).str.lower()
    print(f"Fichier de données chargé : {len(df)} lignes.")
    return df

# --- Initialisation de l'API et des ressources ---

app = FastAPI()

# Configuration CORS pour autoriser les requêtes du frontend Next.js
# (qui tournera sur http://localhost:3000 par défaut)
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

# Ces ressources (client Gemini, données du DataFrame) sont chargées une seule fois
# au démarrage du serveur pour de meilleures performances.
try:
    gemini_client = configure_gemini()
    iam_df = load_iam_data()
except Exception as e:
    print(f"ERREUR CRITIQUE AU DÉMARRAGE : {e}")
    gemini_client = None
    iam_df = None

# --- Logique de recherche (Retrieval) ---

def find_relevant_context(query: str, df: pd.DataFrame, top_k=5):
    """
    Recherche très simple par mot-clé pour trouver des lignes pertinentes.
    Une vraie application RAG utiliserait des embeddings vectoriels.
    """
    if df is None:
        return "Les données de la matrice IAM ne sont pas chargées."

    query_lower = query.lower()
    # La recherche s'effectue en vérifiant si la chaîne de caractères de la requête
    # est présente dans notre colonne 'searchable_text'.
    results = df[df['searchable_text'].str.contains(query_lower, na=False)]
    
    if results.empty:
        return "Aucun contexte pertinent n'a été trouvé dans les documents."

    # Nous retournons les lignes les plus pertinentes sous forme de texte au format CSV pour les inclure dans le prompt.
    context_text = results.head(top_k).to_csv(index=False)
    return context_text

# --- Endpoint de l'API ---

class Question(BaseModel):
    query: str

@app.post("/api/ask")
async def ask_bot(question: Question):
    if not gemini_client or iam_df is None:
        raise HTTPException(status_code=503, detail="Le service est indisponible, le backend n'a pas pu s'initialiser correctement.")

    # Étape 1 (Retrieval) : Nous recherchons les informations pertinentes dans nos données.
    relevant_context = find_relevant_context(question.query, iam_df)

    # Étape 2 (Augmented) : Nous construisons un prompt détaillé pour le modèle, en incluant le contexte trouvé.
    prompt = f"""Contexte:
{relevant_context}
---
Question: {question.query}
---
En te basant UNIQUEMENT sur le contexte ci-dessus, réponds à la question. Si le contexte ne contient pas la réponse, dis "Je n'ai pas trouvé l'information dans mes documents."."""

    # Étape 3 (Generation) : Nous envoyons le prompt au modèle Gemini pour générer la réponse.
    try:
        response = gemini_client.generate_content(prompt)
        return {"answer": response.text}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Erreur lors de l'appel à l'API Gemini: {e}")
