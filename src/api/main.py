import os
import shutil
import json
from typing import Annotated
from fastapi import FastAPI, HTTPException, UploadFile, File
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from contextlib import asynccontextmanager
from fastapi.middleware.cors import CORSMiddleware # NOUVELLE LIGNE À AJOUTER EN HAUT

from src.engine.llm_manager import LocalLLMManager
from src.engine.rag_manager import LocalRAGManager
from src.utils.file_reader import extract_text_from_pdf, chunk_text
from src.core.config import settings

llm_manager = None
rag_manager = None

@asynccontextmanager
async def lifespan(app: FastAPI):
    global llm_manager, rag_manager
    try:
        llm_manager = LocalLLMManager(model_path=str(settings.llm_model_path), backend=settings.llm_backend)
    except Exception as exc:
        print(f"LLM indisponible: {exc}")
    try:
        rag_manager = LocalRAGManager(embedding_model_name=settings.embedding_model_name)
    except Exception as exc:
        print(f"RAG indisponible: {exc}")
    yield
    llm_manager = None
    rag_manager = None

app = FastAPI(title="Agent LLM Local - Version Hybride", version="3.0.0", lifespan=lifespan)
# --- NOUVEAU BLOC CORS ---
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # En production, on mettra l'URL exacte de React
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
# -------------------------
class Message(BaseModel):
    role: str
    content: str

class PromptRequest(BaseModel):
    messages: list[Message]
    temperature: float = 0.1

@app.post("/upload")
def upload_document(file: Annotated[UploadFile, File(...)]):
    if rag_manager is None:
        raise HTTPException(status_code=503, detail="Moteur RAG indisponible.")
    
    file_location = settings.raw_documents_dir / file.filename
    os.makedirs(settings.raw_documents_dir, exist_ok=True)
    
    with open(file_location, "wb+") as file_object:
        shutil.copyfileobj(file.file, file_object)
        
    raw_text = extract_text_from_pdf(file_location)
    chunks = chunk_text(raw_text, chunk_size=1000, overlap=200)
    
    # Le rag_manager va maintenant indexer dans FAISS ET dans BM25
    rag_manager.add_documents(chunks)
    
    return {"status": "success", "message": f"Document indexé avec succès dans FAISS et BM25."}

@app.post("/chat")
async def chat_endpoint(request: PromptRequest):
    if llm_manager is None or rag_manager is None:
        raise HTTPException(status_code=503, detail="Modèles non chargés.")
    
    if not rag_manager.documents_store:
        raise HTTPException(status_code=400, detail="Veuillez uploader un document PDF d'abord.")

    # On récupère la dernière question posée
    user_query = request.messages[-1].content
    
    # Le rag_manager.search() fait maintenant la fusion BM25 + FAISS
    context_chunks = rag_manager.search(user_query, top_k=3)
    context_text = "\n\n---\n\n".join(context_chunks)
    
    # --- LA NOUVELLE CONSIGNE HYBRIDE ---
    augmented_prompt = f"""Réponds à la question en te basant sur le contexte ci-dessous.
Tu as le droit d'utiliser tes connaissances générales pour faire des déductions logiques entre la question et le contexte (ex: géographie, synonymes).
Si l'information est totalement absente, dis uniquement 'Je n'ai pas trouvé l'information'.

CONTEXTE :
{context_text}

QUESTION :
{user_query}"""

    formatted_messages = [{"role": msg.role, "content": msg.content} for msg in request.messages]
    formatted_messages[-1]["content"] = augmented_prompt

    # Le Générateur de Flux (Streaming)
    async def response_generator():
        # 1. On envoie les sources en premier
        yield json.dumps({"sources": context_chunks}) + "\n"
        
        # 2. On envoie les mots au fur et à mesure
        async for chunk in llm_manager.stream_response(formatted_messages, temperature=request.temperature):
            if chunk:
                yield json.dumps({"chunk": chunk}) + "\n"

    # On retourne une StreamingResponse (le canal reste ouvert)
    return StreamingResponse(response_generator(), media_type="application/x-ndjson")