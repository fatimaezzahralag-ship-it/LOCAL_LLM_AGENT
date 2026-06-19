# Local LLM Agent

## Run the API

Use the project virtualenv explicitly so the shell does not fall back to the system `uvicorn`:

```bash
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements.txt
./run_api.sh
```

## Environment

The project is configured to use:

- `LLM_BACKEND=transformers`
- `LLM_MODEL_PATH=models/Llama-3B-Instruct`

## Notes

- Do not run `uvicorn` directly unless you know it resolves to `.venv/bin/uvicorn`.
- If you want the RAG and model stack, install `requirements-full.txt`.

🚀 Alignement Opérationnel (Installation)

1. Configuration du Backend (FastAPI)
Assurez-vous d'avoir Python 3.10+ installé.

Bash
# Activer l'environnement virtuel WSL / Linux
source venv_wsl/bin/activate

# Lancer le serveur d'inférence central
python -m uvicorn src.api.main:app --host 0.0.0.0 --port 8000
Le backend est actif sur http://127.0.0.1:8000.

2. Configuration du Frontend (React)
Nécessite Node.js v20+ installé nativement dans votre environnement d'exécution.

Bash
# Entrer dans le dossier de l'interface
cd frontend

# Installer les dépendances tactiques (Lucide Icons, Tailwind, etc.)
npm install

# Déployer l'interface en mode développement
npm run dev
L'interface est accessible sur http://localhost:5173.

🧪 Protocole de Validation Technique
Pour valider le bon fonctionnement de la recherche hybride et de la mémoire contextuelle, utilisez le scénario de test suivant :

Indexation : Chargez un document technique ou un manuel logistique via le panneau latéral.

Test Sémantique & Mots-clés : Posez une question sur une procédure spécifique. Résultat attendu : Streaming fluide et affichage immédiat des sources textuelles.

Test de Continuité Logique (Mémoire) : Posez une question de suivi implicite (ex: "Et quel formulaire appliquer si le pays de destination change pour la France ?"). Résultat attendu : L'agent fait le lien avec la question précédente, utilise sa mémoire et applique une déduction géographique (France = Europe) pour extraire la bonne consigne.

🔒 Sécurité & Confidentialité
Ce système est conçu pour un déploiement souverain. Aucune donnée, requête ou document indexé ne transite par un serveur tiers ou une API cloud. Tout le cycle de traitement de la donnée (chiffrement, vectorisation, inférence) s'effectue au sein de l'infrastructure locale.
