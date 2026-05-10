# Bot-IAM

## Description

Bot-IAM est une application web qui utilise un modèle de langage (Google Gemini) pour répondre à des questions concernant une matrice de gestion des identités et des accès (IAM). L'application est basée sur une architecture **RAG (Retrieval-Augmented Generation) vectorielle** : les lignes du fichier Excel sont transformées en *embeddings* (vecteurs sémantiques) puis recherchées par similarité cosinus avant d'être envoyées à Gemini pour générer la réponse.

## Architecture

Le projet est divisé en deux parties principales :

*   **Backend** : Une API web développée en Python avec le framework **FastAPI**. Elle :
    *   charge la matrice IAM depuis `data/matriceiam.xlsx`,
    *   génère (et met en cache sur disque) les embeddings de chaque ligne avec `gemini-embedding-001`,
    *   à chaque question, embed la requête, calcule la similarité cosinus avec les documents et envoie le top-k à Gemini (`gemini-2.5-flash-lite`) pour générer la réponse.
*   **Frontend** : Une interface utilisateur développée avec **Next.js** (React). Elle permet à l'utilisateur de poser des questions via une interface de chat et d'afficher les réponses reçues du backend.

## Pile technique (backend)

| Composant | Choix | Rôle |
|---|---|---|
| Framework web | **FastAPI** + uvicorn | API HTTP asynchrone, doc Swagger auto |
| Données | **pandas** + **openpyxl** | Lecture de `matriceiam.xlsx` |
| SDK Gemini | **google-genai** (≥1.0) | Nouvelle API officielle Google (remplace `google-generativeai`) |
| Modèle d'embedding | `gemini-embedding-001` | Transforme chaque ligne et chaque requête en vecteur 3072-dim |
| Modèle de chat | `gemini-2.5-flash-lite` | Génère la réponse finale (quota free-tier plus généreux que `flash`) |
| Calcul vectoriel | **numpy** | Similarité cosinus + cache `.npz` |
| Configuration | **python-dotenv** | Lecture de `.env` (clé API) |

## Prérequis

*   [Python](https://www.python.org/downloads/) **3.10+** (testé sur 3.13)
*   [Node.js](https://nodejs.org/) (version 18.17 ou supérieure)
*   Une clé API **Google Gemini** (https://aistudio.google.com/app/apikey)

## Installation

### 1. Cloner le dépôt

```bash
git clone <URL_DU_DEPOT>
cd Bot-IAM
```

### 2. Configurer le Backend (Python)

a. **Créer et activer un environnement virtuel** :

```powershell
# Sur Windows (PowerShell)
python -m venv .venv
.\.venv\Scripts\Activate.ps1
```

```bash
# Sur macOS/Linux
python -m venv .venv
source .venv/bin/activate
```

b. **Installer les dépendances Python** :

```bash
pip install -r requirements.txt
```

Le fichier `requirements.txt` contient :
```
pandas
openpyxl
google-genai>=1.0.0
python-dotenv
fastapi
uvicorn[standard]
```

> ⚠️ `openpyxl` est requis par pandas pour lire les fichiers `.xlsx`.
> ⚠️ Ne pas confondre `google-genai` (nouveau SDK, utilisé ici) et `google-generativeai` (ancien SDK déprécié, API différente).

### 3. Configurer le Frontend (Next.js)

```bash
cd frontend
npm install
```

### 4. Configurer les variables d'environnement

Créer un fichier `.env` à la racine et y mettre :

```
GOOGLE_API_KEY="VOTRE_CLE_API_ICI"
```

(`GEMINI_API_KEY` est également accepté.)

## Utilisation

### 1. Démarrer le serveur Backend

Depuis la racine du projet, environnement virtuel activé :

```powershell
uvicorn src.api:app --reload
```

Le backend sera accessible à `http://127.0.0.1:8000`.
La documentation interactive Swagger est sur `http://127.0.0.1:8000/docs`.

**Au premier démarrage**, le serveur génère les embeddings de toutes les lignes du xlsx. Cela peut prendre quelques minutes à cause du rate-limit du free-tier Gemini (100 embed/min) — des pauses sont ajoutées entre chaque batch de 50. Les embeddings sont ensuite sauvegardés dans `data/matriceiam_embeddings.npz` ; les démarrages suivants seront **instantanés**.

Le cache est invalidé automatiquement si :
*   le `.xlsx` a été modifié (mtime différent), ou
*   le nombre de lignes a changé.

### 2. Démarrer le serveur Frontend

```bash
cd frontend
npm run dev
```

Le frontend sera accessible à `http://localhost:3000`.

### 3. Tester l'API directement

```powershell
$body = @{ query = "Comment demander Adobe Illustrator ?" } | ConvertTo-Json
Invoke-RestMethod -Uri "http://127.0.0.1:8000/api/ask" -Method Post `
  -Body $body -ContentType "application/json; charset=utf-8"
```

## Pipeline RAG en bref

```
                   ┌────────────────────────────┐
   Démarrage  ───► │ Embed chaque ligne du xlsx │  ──►  data/*.npz (cache)
                   │ (RETRIEVAL_DOCUMENT)       │
                   └────────────────────────────┘

   Requête  ──► Embed question ──► Similarité cosinus ──► top-k lignes
                                   (numpy matmul)         (≥ seuil 0.4)
                                                              │
                                                              ▼
                                              Prompt = contexte + question
                                                              │
                                                              ▼
                                                  Gemini Flash Lite ──► réponse
```

Voir `resume_apprentissage.txt` pour l'explication détaillée du concept de RAG.

## Robustesse

*   **Rate-limit Gemini** : retry avec backoff exponentiel sur les erreurs 429, en respectant le `retryDelay` renvoyé par l'API (côté embedding ET côté chat).
*   **Cache embeddings** : invalidation automatique sur `mtime` du xlsx, fichier `.npz` portable.
*   **Seuil de similarité** : `min_similarity=0.4` évite de renvoyer du contexte non-pertinent → permet au modèle de répondre "Je n'ai pas trouvé l'information" plutôt que d'halluciner.
