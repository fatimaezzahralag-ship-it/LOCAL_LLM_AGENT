import os
import shutil
from typing import Annotated
from fastapi import FastAPI, HTTPException, UploadFile, File
from pydantic import BaseModel
from contextlib import asynccontextmanager

# Importation de nos modules locaux
from src.engine.llm_manager import LocalLLMManager
from src.engine.rag_manager import LocalRAGManager
from src.utils.file_reader import extract_text_from_pdf, chunk_text
from src.core.config import settings

# Variables globales pour maintenir les modèles en VRAM
llm_manager = None
rag_manager = None

@asynccontextmanager
async def lifespan(app: FastAPI):
    global llm_manager, rag_manager
    
    # 1. Chargement du modèle LLM et du RAG selon la configuration locale
    try:
        llm_manager = LocalLLMManager(
            model_path=str(settings.llm_model_path),
            backend=settings.llm_backend,
        )
    except Exception as exc:
        llm_manager = None
        print(f"LLM indisponible au démarrage: {exc}")

    try:
        rag_manager = LocalRAGManager(embedding_model_name=settings.embedding_model_name)
    except Exception as exc:
        rag_manager = None
        print(f"RAG indisponible au démarrage: {exc}")
    
    yield
    
    # Nettoyage à l'arrêt du serveur
    llm_manager = None
    rag_manager = None

app = FastAPI(
    title="Agent LLM Local - Prototype",
    description="API locale complète avec RAG et inférence GPU",
    version="1.0.0",
    lifespan=lifespan
)

upload_responses = {
    400: {"description": "Fichier non supporté"},
    500: {"description": "Erreur pendant le traitement"},
    503: {"description": "Moteur RAG indisponible"},
}

chat_responses = {
    400: {"description": "Aucun document indexé"},
    500: {"description": "Erreur de génération"},
    503: {"description": "Modèles non chargés"},
}

# --- Modèles de données ---
class PromptRequest(BaseModel):
    prompt: str
    temperature: float = 0.1

class GenerationResponse(BaseModel):
    response: str
    sources: list[str] = []

# --- Endpoints ---

@app.post("/upload", responses=upload_responses)
def upload_document(file: Annotated[UploadFile, File(...)]):
    """Reçoit un PDF, extrait le texte, le découpe et l'indexe dans FAISS."""
    if rag_manager is None:
        raise HTTPException(status_code=503, detail="Le moteur RAG n'est pas disponible.")

    if not file.filename.endswith('.pdf'):
        raise HTTPException(status_code=400, detail="Seuls les fichiers PDF sont supportés pour le prototype.")
    
    # Sauvegarde temporaire du fichier
    file_location = settings.raw_documents_dir / file.filename
    os.makedirs(settings.raw_documents_dir, exist_ok=True)
    
    try:
        with open(file_location, "wb+") as file_object:
            shutil.copyfileobj(file.file, file_object)
            
        # Extraction et découpage
        raw_text = extract_text_from_pdf(file_location)
        chunks = chunk_text(raw_text, chunk_size=1000, overlap=200)
        
        # Vectorisation sur GPU
        rag_manager.add_documents(chunks)
        
        return {
            "status": "success", 
            "message": f"Document {file.filename} indexé avec succès.",
            "chunks_processed": len(chunks)
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Erreur lors du traitement : {str(e)}")

@app.post("/chat", response_model=GenerationResponse, responses=chat_responses)
async def chat_endpoint(request: PromptRequest):
    """Recherche des informations dans FAISS puis interroge le LLM."""
    if llm_manager is None or rag_manager is None:
        raise HTTPException(status_code=503, detail="Les modèles ne sont pas encore chargés.")
    
    # OPTIMISATION : Vérifier s'il y a des documents avant de déranger le modèle
    if not rag_manager.documents_store:
        return {
            "response": "Veuillez d'abord uploader un document PDF avant de me poser une question.",
            "sources": []
        }

    try:
        # 1. Recherche sémantique dans les documents (Top 3 des passages pertinents)
        context_chunks = rag_manager.search(request.prompt, top_k=3)
        context_text = "\n\n---\n\n".join(context_chunks)
        
        # 2. Construction du Prompt Système + Contexte
        augmented_prompt = f"""Réponds à la question de l'utilisateur en te basant STRICTEMENT sur le contexte ci-dessous.
Si l'information n'y est pas, dis uniquement 'Je n'ai pas trouvé l'information dans vos documents.'
Reste concis (3 ou 4 phrases maximum).

CONTEXTE :
{context_text}

QUESTION :
{request.prompt}"""

        # 3. Génération de la réponse via le GPU (ultra rapide grâce au nouveau llm_manager)
        answer = await llm_manager.generate_response(
            prompt=augmented_prompt,
            temperature=request.temperature
        )
        
        return {
            "response": answer,
            "sources": context_chunks # On renvoie les sources pour affichage côté front
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Erreur du modèle : {str(e)}")