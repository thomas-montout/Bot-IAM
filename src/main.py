import pandas as pd  # Importe la bibliothèque pandas pour manipuler les tableaux de données (DataFrame)

# ===========================
# ÉTAPE 1 : CHARGER LES DONNÉES ET CRÉER LES CHUNKS
# ===========================

print("Chargement de la matrice IAM...")

# Lecture du fichier Excel contenant la matrice IAM
df = pd.read_excel("data/matriceiam.xlsx")  # Charge le fichier Excel dans un DataFrame

# Création d'une liste vide pour stocker les chunks (un chunk = une application et ses infos)
chunks = []

# Parcours de chaque ligne du tableau (chaque application)
for _, row in df.iterrows():  # .iterrows() permet de parcourir chaque ligne du DataFrame
    chunk = {  # On crée un dictionnaire pour stocker les infos de l'application
        "Application": row["Application"],  # Nom de l'application
        "Domaine": row["Domain"],  # Domaine de l'application
        "Groupe": row["Groupe en charge de la demande"],  # Groupe responsable
        "Gestion": row.get("Gestion de la demande", ""),  # COFITIL ou JIRA (protégé avec .get() si la colonne n'existe pas)
        "Commentaires": row.get("Commentaires", ""),  # Commentaires (protégé avec .get() si la colonne n'existe pas)
    }
    chunks.append(chunk)  # On ajoute ce dictionnaire à la liste des chunks

print(f"✓ {len(chunks)} chunks créés (un par application).\n")


# ===========================
# ÉTAPE 2 : DÉFINIR LA FONCTION DE RECHERCHE
# ===========================

def rechercher_chunks(question, chunks):  # Fonction qui prend la question et la liste des chunks
    """Recherche les chunks pertinents pour la question"""
    resultats = []  # Liste vide pour stocker les chunks trouvés
    
    question_lower = question.lower()  # Convertit la question en minuscules pour une comparaison insensible à la casse
    
    for chunk in chunks:  # Parcourt chaque chunk (chaque application)
        # PROTECTION : vérifier que Application existe et n'est pas NaN
        if pd.isna(chunk["Application"]) or chunk["Application"] == "":  # Si Application est vide ou NaN
            continue  # Continue vers le prochain chunk (saute celui-ci)
        
        # Récupère les champs pertinents du chunk et les convertit en minuscules
        app_lower = str(chunk["Application"]).lower()  # Convertit en string d'abord, puis en minuscules
        commentaires_lower = str(chunk["Commentaires"]).lower()  # Commentaires en minuscules (str() protège contre NaN)
        groupe_lower = str(chunk["Groupe"]).lower()  # Groupe en minuscules
        gestion_lower = str(chunk["Gestion"]).lower()  # Gestion en minuscules (COFITIL ou JIRA)
        
        # Vérifie si le mot-clé de la question se trouve dans l'application, les commentaires, le groupe ou la gestion
        if (question_lower in app_lower or 
            question_lower in commentaires_lower or 
            question_lower in groupe_lower or
            question_lower in gestion_lower):
            resultats.append(chunk)  # Si on trouve une correspondance, on ajoute le chunk aux résultats
    
    return resultats  # On retourne la liste des chunks trouvés


# ===========================
# ÉTAPE 3 : VÉRIFIER LES CHUNKS
# ===========================

print("=== VÉRIFICATION DES CHUNKS ===\n")

print(f"Total de chunks créés : {len(chunks)}")  # Affiche le nombre total de chunks

print("\n--- Les 3 premiers chunks ---")
for i in range(min(3, len(chunks))):  # Affiche les 3 premiers (ou moins s'il y en a peu)
    chunk = chunks[i]  # Récupère le i-ème chunk
    print(f"\nChunk {i+1}:")  # Affiche le numéro du chunk (i+1 car on compte à partir de 1)
    print(f"  Application: {chunk['Application']}")  # Affiche le nom de l'application
    print(f"  Domaine: {chunk['Domaine']}")  # Affiche le domaine
    print(f"  Groupe: {chunk['Groupe']}")  # Affiche le groupe responsable
    print(f"  Gestion: {chunk['Gestion']}")  # Affiche le type de gestion (COFITIL ou JIRA)
    commentaires_court = str(chunk['Commentaires'])[:100] if chunk['Commentaires'] else "Aucun commentaire"  # Prend les 100 premiers caractères des commentaires
    print(f"  Commentaires: {commentaires_court}...")  # Affiche les commentaires tronqués

# Vérifier qu'il n'y a pas de chunks avec Application vide
print("\n=== VÉRIFICATION DES CHUNKS VIDES ===\n")

chunks_vides = 0  # Compteur de chunks vides

for chunk in chunks:  # Parcourt tous les chunks
    if pd.isna(chunk["Application"]) or chunk["Application"] == "":  # Si Application est vide
        chunks_vides += 1  # Incrémente le compteur

print(f"Nombre de chunks avec Application vide : {chunks_vides}")  # Affiche le nombre

if chunks_vides == 0:  # Si aucun chunk n'est vide
    print("✓ Tous les chunks sont valides !")  # Message de confirmation
else:  # Si y a des chunks vides
    print(f"⚠ {chunks_vides} chunks ont une application vide (ils seront ignorés)")  # Message d'avertissement

# Tester la recherche
print("\n=== TEST DE RECHERCHE ===\n")

mots_cles_test = ["PEPS", "Calypso", "SAP", "application"]  # Quelques mots-clés à tester

for mot in mots_cles_test:  # Boucle sur chaque mot-clé
    resultats = rechercher_chunks(mot, chunks)  # Cherche les chunks contenant ce mot
    print(f"Recherche '{mot}': {len(resultats)} résultat(s) trouvé(s)")  # Affiche le nombre de résultats
    
    for res in resultats[:2]:  # Affiche maximum les 2 premiers résultats (pour ne pas surcharger)
        print(f"  - {res['Application']}")  # Affiche le nom de l'application trouvée


# ===========================
# ÉTAPE 4 : BOUCLE INTERACTIVE SIMPLE (sans Gemini encore)
# ===========================

print("\n" + "="*60)
print("ASSISTANT IAM - VERSION TEST")
print("="*60 + "\n")

while True:  # Boucle infinie (jusqu'à ce que l'utilisateur quitte)
    question = input("📝 Quelle est ta question sur une application IAM ? (tape 'quit' pour quitter) : ")  # Demande la question
    
    if question.lower() == "quit":  # Si l'utilisateur tape "quit"
        print("\n👋 Au revoir !")  # Affiche un message
        break  # Quitte la boucle
    
    # Rechercher les chunks pertinents
    chunks_pertinents = rechercher_chunks(question, chunks)  # Trouve les chunks qui correspondent
    
    if chunks_pertinents:  # Si on a trouvé au moins un chunk
        print(f"\n✓ {len(chunks_pertinents)} résultat(s) pertinent(s) trouvé(s).\n")  # Affiche le nombre de résultats
        
        # Afficher les résultats trouvés
        for i, chunk in enumerate(chunks_pertinents):  # Boucle sur chaque chunk pertinent
            print(f"--- Application {i+1} : {chunk['Application']} ---")  # Affiche le numéro et le nom
            print(f"Domaine: {chunk['Domaine']}")  # Affiche le domaine
            print(f"Groupe responsable: {chunk['Groupe']}")  # Affiche le groupe
            print(f"Gestion de la demande: {chunk['Gestion']}")  # Affiche le type de gestion (COFITIL ou JIRA)
            print(f"Commentaires: {chunk['Commentaires']}\n")  # Affiche les commentaires
    else:  # Si aucun chunk n'a été trouvé
        print("❌ Aucun résultat trouvé pour cette question. Essaie avec d'autres mots-clés.\n")  # Message d'erreur

