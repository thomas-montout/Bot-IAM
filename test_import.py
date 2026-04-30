import sys
print("Chemins de recherche Python (sys.path):")
for p in sys.path:
    print(f"- {p}")

try:
    import google.genai as genai
    print("\n✓ Importation de 'google.genai' réussie !")
    print(f"Version de google-generativeai: {genai.__version__}")
except ImportError as e:
    print(f"\n❌ Erreur d'importation : {e}")
except Exception as e:
    print(f"\n❌ Une autre erreur est survenue : {e}")
