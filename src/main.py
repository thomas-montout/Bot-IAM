import pandas as pd

# Lecture du fichier Excel
df = pd.read_excel("data/matriceiam.xlsx")  # adapte le chemin si besoin
        
mot_cle = input("Entrez un mot-clé à rechercher : ")

resultats = df[df['Application'].str.contains(mot_cle, case=False, na=False)]
print(resultats)