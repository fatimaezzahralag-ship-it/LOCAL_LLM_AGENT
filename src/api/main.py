import os # Importe le module os pour interagir avec le système d'exploitation (chemins, dossiers)
import shutil # Importe shutil pour effectuer des opérations de haut niveau sur les fichiers (copie, suppression)
import json # Importe json pour formater les réponses en flux de données texte (NDJSON)
from typing import Annotated # Importe Annotated pour ajouter des métadonnées de validation aux paramètres
from fastapi import FastAPI, HTTPException, UploadFile, File # Importe les composants de base pour créer l'API et gérer les erreurs/fichiers
from fastapi.responses import StreamingResponse # Importe StreamingResponse pour envoyer la réponse mot par mot au client
from pydantic import BaseModel # Importe BaseModel pour définir et valider la structure des données reçues (JSON)
from contextlib import asynccontextmanager # Importe asynccontextmanager pour gérer les événements de démarrage et d'arrêt du serveur
from fastapi.middleware.cors import CORSMiddleware # Importe le middleware CORS pour autoriser l'interface React à communiquer avec cette API

# Importe les gestionnaires d'Intelligence Artificielle développés dans le projet
from src.engine.llm_manager import LocalLLMManager # Importe le gestionnaire du grand modèle de langage (Génération)
from src.engine.rag_manager import LocalRAGManager # Importe le gestionnaire de recherche vectorielle et lexicale (Recherche)

# Importe les outils d'extraction et de traitement de texte depuis notre lecteur de fichiers
from src.utils.file_reader import extract_text_from_pdf, extract_text_from_txt, extract_text_from_docx, extract_text_from_csv, extract_text_from_image, chunk_text
from src.core.config import settings # Importe les paramètres de configuration globaux du projet (chemins, noms des modèles)

# --- NOUVEAUX IMPORTS : GESTIONNAIRE DE LA BASE DE DONNÉES LOCALES SQLITE ---
from src.core.database import init_db, create_session, save_message, get_session_history, save_document_meta, get_all_sessions, delete_session, rename_session

llm_manager = None # Initialise la variable globale pour le modèle LLM (évite de le recharger à chaque requête)
rag_manager = None # Initialise la variable globale pour le moteur RAG (évite de recharger l'indexation à chaque fois)

@asynccontextmanager # Décorateur pour définir le cycle de vie de l'application FastAPI
async def lifespan(app: FastAPI): # Fonction exécutée au lancement du serveur
    global llm_manager, rag_manager # Indique qu'on va modifier les variables globales définies plus haut
    try: # Tente d'initialiser la base de données SQLite
        init_db() # Crée le fichier de la base de données et configure les tables (sessions, messages, documents) s'ils n'existent pas
    except Exception as exc: # Si une erreur survient pendant l'initialisation de la DB
        print(f"Erreur lors de l'initialisation de la base de données : {exc}") # Log l'erreur dans la console
    try: # Tente de charger le modèle de langage
        llm_manager = LocalLLMManager(model_path=str(settings.llm_model_path), backend=settings.llm_backend) # Charge le LLM en mémoire (RAM/VRAM)
    except Exception as exc: # Si une erreur survient pendant le chargement du LLM
        print(f"LLM indisponible: {exc}") # Affiche l'erreur dans la console du serveur
    try: # Tente de charger le moteur de recherche RAG
        rag_manager = LocalRAGManager(embedding_model_name=settings.embedding_model_name) # Initialise FAISS et BM25 avec le modèle d'embedding
    except Exception as exc: # Si une erreur survient pendant le chargement du RAG
        print(f"RAG indisponible: {exc}") # Affiche l'erreur dans la console du serveur
    yield # Met le code en pause ici : l'API est maintenant prête à recevoir des requêtes web
    llm_manager = None # À l'arrêt du serveur, libère la mémoire allouée au modèle LLM
    rag_manager = None # À l'arrêt du serveur, libère la mémoire allouée au moteur de recherche RAG

app = FastAPI(title="Agent LLM Local - Version Hybride & Persistante", version="4.0.0", lifespan=lifespan) # Initialise l'application FastAPI

# --- BLOC CORS (Sécurité inter-domaines) ---
app.add_middleware( # Ajoute une couche de sécurité au serveur
    CORSMiddleware, # Utilise le module CORS
    allow_origins=["*"],  # Autorise toutes les adresses externes (ex: React sur le port 5173) à appeler cette API
    allow_credentials=True, # Autorise l'envoi de cookies ou d'identifiants si nécessaire
    allow_methods=["*"], # Autorise toutes les méthodes HTTP (GET, POST, PUT, DELETE)
    allow_headers=["*"], # Autorise tous les types d'en-têtes HTTP dans les requêtes
)
# -------------------------------------------

class Message(BaseModel): # Définit la structure d'un message individuel dans le chat
    role: str # Rôle de l'émetteur (ex: "user" ou "assistant")
    content: str # Contenu textuel du message

class PromptRequest(BaseModel): # Définit la structure de la requête envoyée par React pour chatter
    messages: list[Message] # Liste contenant l'historique complet de la conversation transmis par le front
    temperature: float = 0.1 # Paramètre de créativité du modèle (0.1 = très précis et factuel)
    session_id: str = "default_mission" # ID unique de la session/mission en cours pour l'isolation de l'historique

@app.post("/upload") # Crée une route d'API accessible via la méthode HTTP POST à l'adresse /upload
def upload_document(file: Annotated[UploadFile, File(...)], session_id: str = "default_mission"): # Reçoit le fichier et son ID de mission associé
    if rag_manager is None: # Vérifie si le moteur de recherche est bien démarré
        raise HTTPException(status_code=503, detail="Moteur RAG indisponible.") # Renvoie une erreur si le moteur est hors ligne
    
    file_location = settings.raw_documents_dir / file.filename # Construit le chemin final pour sauvegarder le fichier sur le disque dur
    os.makedirs(settings.raw_documents_dir, exist_ok=True) # Crée le dossier de stockage s'il n'existe pas déjà (ignore si existant)
    
    with open(file_location, "wb+") as file_object: # Ouvre un nouveau fichier physique en mode écriture binaire
        shutil.copyfileobj(file.file, file_object) # Copie le flux de données reçu depuis internet vers le disque dur local
        
    # --- L'AIGUILLEUR DE FORMATS MULTIPLES ---
    extension = file.filename.split(".")[-1].lower() # Coupe le nom du fichier par les points et récupère la dernière partie en minuscules
    
    if extension == "pdf": # Si l'extension indique un fichier PDF
        raw_text = extract_text_from_pdf(file_location) # Appelle la fonction dédiée à l'extraction des PDF
    elif extension in ["txt", "md"]: # Si l'extension indique un fichier texte brut ou Markdown
        raw_text = extract_text_from_txt(file_location) # Appelle la fonction dédiée à l'extraction de texte simple
    elif extension in ["docx", "doc"]: # Si l'extension indique un document Microsoft Word
        raw_text = extract_text_from_docx(file_location) # Appelle la fonction dédiée à l'extraction Word
    elif extension == "csv": # Si l'extension indique un fichier tableur basique
        raw_text = extract_text_from_csv(file_location) # Appelle la fonction dédiée à l'extraction de données tabulaires
    elif extension in ["png", "jpg", "jpeg"]: # Si l'extension indique une image ou un scan
        raw_text = extract_text_from_image(file_location) # Appelle la fonction d'Intelligence Artificielle visuelle OCR
    else: # Si le fichier a une extension inconnue (ex: .exe, .zip)
        os.remove(file_location) # Supprime le fichier du disque par sécurité
        raise HTTPException(status_code=400, detail=f"Format .{extension} non supporté.") # Refuse l'opération et prévient l'utilisateur
    # -----------------------------------------

    # --- ENREGISTREMENT DES MÉTADONNÉES DANS LA BASE DE DONNÉES ---
    create_session(session_id, f"Mission {session_id}") # Crée automatiquement la session en DB si elle n'existait pas encore
    save_document_meta(session_id, file.filename, str(file_location)) # Enregistre l'existence du document pour cette mission spécifique

    chunks = chunk_text(raw_text, chunk_size=1000, overlap=200) # Découpe le texte extrait en paragraphes pour faciliter la recherche vectorielle
    
    rag_manager.add_documents(chunks, session_id=session_id) # Envoie les morceaux de texte au moteur RAG pour être indexés (convertis en vecteurs et mots-clés)
    
    return {"status": "success", "message": f"Document .{extension.upper()} indexé et lié à la session '{session_id}' avec succès."} # Réponse de succès

@app.post("/clear_docs") # Crée une route POST pour vider la mémoire du système
def clear_documents(): # Fonction exécutée lors de l'appui sur le bouton "Purger"
    """Vide le moteur RAG et supprime les fichiers stockés localement.""" # Docstring décrivant la fonction
    if rag_manager is None: # Vérifie si le moteur est disponible
        raise HTTPException(status_code=503, detail="Moteur RAG indisponible.") # Bloque l'opération si le moteur est éteint
    
    rag_manager.clear() # Appelle la fonction interne du RAG pour effacer les index FAISS et BM25 de la RAM
    
    if os.path.exists(settings.raw_documents_dir): # Vérifie si le dossier de stockage physique existe bien
        shutil.rmtree(settings.raw_documents_dir) # Supprime complètement le dossier et tout ce qu'il contient
        os.makedirs(settings.raw_documents_dir, exist_ok=True) # Recrée un dossier vide et propre immédiatement après
        
    return {"status": "success", "message": "Base documentaire purgée avec succès."} # Confirme le succès à l'interface React

@app.post("/chat") # Crée la route principale POST pour discuter avec l'agent
async def chat_endpoint(request: PromptRequest): # Fonction asynchrone qui reçoit la conversation de l'utilisateur
    if llm_manager is None or rag_manager is None: # Vérification de sécurité des moteurs
        raise HTTPException(status_code=503, detail="Modèles non chargés.") # Erreur si l'IA est hors ligne
    
    if request.session_id not in rag_manager.documents_stores or not rag_manager.documents_stores[request.session_id]: # Vérifie si la base de données de documents est vide
        raise HTTPException(status_code=400, detail="Veuillez uploader un document d'abord.") # Force l'utilisateur à fournir du contexte
        
    user_query = request.messages[-1].content # Isole le texte de la toute dernière question posée par l'opérateur
    
    # --- PERSISTANCE DE LA MÉMOIRE ENTRANTE ---
    create_session(request.session_id, f"Mission {request.session_id}") # S'assure que la session de chat existe en DB
    save_message(request.session_id, "user", user_query) # Sauvegarde immédiatement la question de l'opérateur dans le disque dur local

    context_chunks = rag_manager.search(user_query, top_k=3, session_id=request.session_id) # Fouille la base hybride pour trouver les 3 meilleurs passages correspondant à la question
    context_text = "\n\n---\n\n".join(context_chunks) # Assemble ces 3 passages en un seul grand bloc de texte séparé par des tirets
    
    # Prépare l'instruction stricte qui va encadrer la réponse de l'IA (le Prompt système)
    augmented_prompt = f"""Réponds à la question en te basant sur le contexte ci-dessous.
Tu as le droit d'utiliser tes connaissances générales pour faire des déductions logiques entre la question et le contexte (ex: géographie, synonymes).
Si l'information est totalement absente, dis uniquement 'Je n'ai pas trouvé l'information'.

CONTEXTE :
{context_text}

QUESTION :
{user_query}""" # Formate la chaîne de caractères avec le contexte trouvé et la question réelle

    formatted_messages = [{"role": msg.role, "content": msg.content} for msg in request.messages] # Transforme les données reçues en dictionnaire classique compréhensible par le modèle
    formatted_messages[-1]["content"] = augmented_prompt # Remplace discrètement la question basique de l'utilisateur par notre question enrichie (avec consignes et contexte)

    async def response_generator(): # Définit une sous-fonction génératrice asynchrone pour le flux de réponse
        yield json.dumps({"sources": context_chunks}) + "\n" # Envoie d'abord les sources extraites à React en format JSON
        
        full_response = "" # Variable locale pour accumuler l'intégralité des mots générés par l'IA afin de les stocker en DB à la fin
        async for chunk in llm_manager.stream_response(formatted_messages, temperature=request.temperature): # Boucle qui attend chaque nouveau mot généré par le LLM
            if chunk: # S'il y a bien un morceau de texte généré
                full_response += chunk # Ajoute le mot à notre variable de sauvegarde globale
                yield json.dumps({"chunk": chunk}) + "\n" # L'encapsule en JSON et l'envoie immédiatement au navigateur web
        
        # --- PERSISTANCE DE LA MÉMOIRE SORTANTE ---
        save_message(request.session_id, "assistant", full_response) # Une fois le flux terminé, sauvegarde la réponse complète de l'IA au chaud dans SQLite

    return StreamingResponse(response_generator(), media_type="application/x-ndjson") # Maintient la connexion HTTP ouverte et envoie le flux en continu (format NDJSON)

# --- NOUVELLES ROUTES POUR LA GESTION ET LA NAVIGATION DANS L'HISTORIQUE ---

@app.get("/sessions") # Crée une route GET pour lister toutes les sessions existantes
def list_sessions(): # Fonction de listing
    """Retourne la liste complète de l'historique des missions pour l'affichage sidebar."""
    return {"status": "success", "sessions": get_all_sessions()} # Renvoie la liste structurée des sessions stockées en DB

@app.get("/history/{session_id}") # Crée une route dynamique GET pour charger l'historique d'une session précise
def load_history(session_id: str): # Fonction de chargement de mémoire
    """Récupère l'historique complet des messages passés d'une session pour restaurer le chat React."""
    history = get_session_history(session_id) # Interroge SQLite pour extraire tous les messages de cette session ordonnés par date
    return {"status": "success", "session_id": session_id, "history": history} # Renvoie l'historique complet au frontend React

# Définition des structures pour les requêtes de gestion des sessions
class RenameRequest(BaseModel):
    new_title: str

@app.delete("/sessions/{session_id}")
def delete_session_endpoint(session_id: str):
    """Route pour supprimer une mission."""
    try:
        delete_session(session_id)
        # Optionnel : On pourrait aussi purger la base vectorielle spécifique ici via rag_manager.clear(session_id)
        if rag_manager is not None:
            rag_manager.clear(session_id)
        return {"status": "success", "message": f"Session {session_id} supprimée."}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.put("/sessions/{session_id}")
def rename_session_endpoint(session_id: str, request: RenameRequest):
    """Route pour renommer une mission."""
    try:
        rename_session(session_id, request.new_title)
        return {"status": "success", "message": f"Session {session_id} renommée en {request.new_title}."}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))