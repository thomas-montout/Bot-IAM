import os
import pathlib
import pandas as pd
from dotenv import load_dotenv
import google.genai as genai
import certifi

# Forcer Python à utiliser les certificats à jour de certifi
os.environ['SSL_CERT_FILE'] = certifi.where()

# ===========================
# ÉTAPE 0 : CONFIGURATION DE GEMINI
# ===========================

# Charger les variables d'environnement depuis le fichier .env
load_dotenv()

# Récupérer la clé API depuis .env ou variables système
api_key = os.getenv("GOOGLE_API_KEY") or os.getenv("GEMINI_API_KEY")

if not api_key:
    print("Erreur : aucune clé API trouvée dans GOOGLE_API_KEY ou GEMINI_API_KEY.")
    print("Veuillez définir la clé dans un fichier .env ou comme variable d'environnement.")
    exit(1)

try:
    # Création du client Gemini avec la clé API
    client = genai.Client(api_key=api_key)
    print("Configuration de l'API Gemini réussie.")

    # Test minimal pour vérifier que le modèle répond
    test_response = client.models.generate_content(
        model="models/gemini-1.5-flash",
        contents="Test de connexion API"
    )
    if test_response and hasattr(test_response, "text"):
        print("Modèle Gemini accessible et opérationnel.")

except Exception as e:
    print(f"Erreur lors de la configuration de l'API Gemini : {e}")
    exit(1)

# ===========================
# ÉTAPE 1 : CHARGER LES DONNÉES
# ===========================

print("Chargement de la matrice IAM...")

SCRIPT_DIR = pathlib.Path(__file__).parent.resolve()
PROJECT_ROOT = SCRIPT_DIR.parent
DATA_FILE_PATH = PROJECT_ROOT / "data" / "matriceiam.xlsx"

try:
    df = pd.read_excel(DATA_FILE_PATH)
    print(f"Fichier chargé : {DATA_FILE_PATH}")
    print(f"Nombre de lignes : {len(df)}")
except FileNotFoundError:
    print(f"Fichier introuvable : {DATA_FILE_PATH}")
    exit(1)
except Exception as e:
    print(f"Erreur lors du chargement du fichier Excel : {e}")
    exit(1)

# ===========================
# ÉTAPE 2 : CRÉER DES CHUNKS
# ===========================

def create_chunks(dataframe, chunk_size=20):
    """
    Découpe un DataFrame en plusieurs morceaux (chunks) pour éviter
    d'envoyer trop de données à la fois à l'API Gemini.
    """
    chunks = []
    for start in range(0, len(dataframe), chunk_size):
        end = start + chunk_size
        chunks.append(dataframe.iloc[start:end])
    return chunks

chunks = create_chunks(df, chunk_size=20)
print(f"Données découpées en {len(chunks)} chunks de 20 lignes maximum.")

# ===========================
# ÉTAPE 3 : ENVOYER LES CHUNKS À GEMINI
# ===========================

for i, chunk in enumerate(chunks, start=1):
    try:
        chunk_text = chunk.to_csv(index=False)

        prompt = (
            f"Voici un extrait de la matrice IAM (chunk {i}/{len(chunks)}):\n"
            f"{chunk_text}\n"
            "Analyse ces données et résume les points importants."
        )

        response = client.models.generate_content(
            model="models/gemini-1.5-flash",
            contents=prompt
        )

        print(f"\n--- Réponse de Gemini pour le chunk {i} ---")
        print(response.text)

    except Exception as e:
        print(f"Erreur lors du traitement du chunk {i} : {e}")
