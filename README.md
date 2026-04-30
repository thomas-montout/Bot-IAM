# Bot-IAM

## Description

Bot-IAM est une application web qui utilise un modèle de langage (Google Gemini) pour répondre à des questions concernant une matrice de gestion des identités et des accès (IAM). L'application est basée sur une architecture RAG (Retrieval-Augmented Generation), ce qui lui permet de fournir des réponses précises en se basant sur les données d'un fichier Excel.

## Architecture

Le projet est divisé en deux parties principales :

*   **Backend** : Une API web développée en Python avec le framework **FastAPI**. Elle gère le chargement des données, la recherche d'informations pertinentes (Retrieval) et la communication avec l'API de Google Gemini pour générer les réponses.
*   **Frontend** : Une interface utilisateur développée avec **Next.js** (React). Elle permet à l'utilisateur de poser des questions via une interface de chat et d'afficher les réponses reçues du backend.

## Prérequis

Avant de commencer, assurez-vous d'avoir installé les logiciels suivants sur votre machine :

*   [Python](https://www.python.org/downloads/) (version 3.9 ou supérieure)
*   [Node.js](https://nodejs.org/) (version 18.17 ou supérieure)

## Installation

Suivez ces étapes pour configurer le projet en local.

### 1. Cloner le dépôt

```bash
git clone <URL_DU_DEPOT>
cd Bot-IAM
```

### 2. Configurer le Backend (Python)

a. **Créer et activer un environnement virtuel** :

```bash
# Se placer à la racine du projet
python -m venv venv

# Activer l'environnement
# Sur Windows
.\venv\Scripts\activate

# Sur macOS/Linux
source venv/bin/activate
```

b. **Installer les dépendances Python** :

```bash
pip install -r requirements.txt
```

### 3. Configurer le Frontend (Next.js)

a. **Naviguer vers le dossier du frontend** :

```bash
cd frontend
```

b. **Installer les dépendances Node.js** :

```bash
npm install
```

### 4. Configurer les variables d'environnement

a. **Créer un fichier `.env`** à la racine du projet `Bot-IAM`.

b. **Ajouter votre clé d'API Google Gemini** dans ce fichier :

```
GOOGLE_API_KEY="VOTRE_CLE_API_ICI"
```

## Utilisation

Pour lancer l'application, vous devez démarrer le serveur backend et le serveur frontend dans deux terminaux distincts.

### 1. Démarrer le serveur Backend

Ouvrez un terminal, activez l'environnement virtuel et lancez le serveur FastAPI :

```bash
# Se placer dans le dossier src
cd src
# Lancer le serveur
uvicorn api:app --reload
```

Le backend sera accessible à l'adresse `http://127.0.0.1:8000`.

### 2. Démarrer le serveur Frontend

Ouvrez un second terminal et lancez le serveur de développement Next.js :

```bash
# Se placer dans le dossier frontend
cd frontend
# Lancer le serveur
npm run dev
```

Le frontend sera accessible dans votre navigateur à l'adresse `http://localhost:3000`.