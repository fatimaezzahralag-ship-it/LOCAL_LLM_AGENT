import os

from src.core.config import settings

try:
    from sentence_transformers import SentenceTransformer
    import faiss
    import numpy as np
    import torch
except ImportError:
    SentenceTransformer = None
    faiss = None
    np = None
    torch = None

class LocalRAGManager:
    def __init__(self, embedding_model_name: str = "BAAI/bge-m3"):
        if SentenceTransformer is None or faiss is None or np is None or torch is None:
            raise RuntimeError(
                "Dépendances RAG manquantes. Installe requirements-full.txt pour activer FAISS et les embeddings."
            )

        self.device = "cuda" if torch.cuda.is_available() else "cpu"
        print(f"Chargement du modèle d'embedding {embedding_model_name} sur {self.device}...")
        self.encoder = SentenceTransformer(embedding_model_name, device=self.device)
        
        # Initialisation de FAISS
        self.dimension = self.encoder.get_sentence_embedding_dimension()
        # Utilisation de l'index L2 standard. (Faiss-GPU peut être activé pour des millions de vecteurs)
        self.index = faiss.IndexFlatL2(self.dimension) 
        self.documents_store = [] # Pour garder une trace du texte original
        
        # Dossier de sauvegarde
        self.db_path = str(settings.vector_db_dir)
        os.makedirs(self.db_path, exist_ok=True)

    def add_documents(self, chunks: list[str]):
        """Vectorise une liste de textes et les ajoute à la base FAISS."""
        if not chunks:
            return
        
        print(f"Calcul des embeddings pour {len(chunks)} chunks...")
        # L'encodage se fait par lots (batch) très rapidement sur GPU
        embeddings = self.encoder.encode(chunks, show_progress_bar=True)
        
        # Ajout à FAISS et stockage du texte
        self.index.add(np.array(embeddings).astype('float32'))
        self.documents_store.extend(chunks)
        print("Documents indexés avec succès.")

    def search(self, query: str, top_k: int = 3) -> list[str]:
        """Cherche les chunks les plus pertinents pour une question donnée."""
        if self.index.ntotal == 0:
            return []
            
        query_vector = self.encoder.encode([query])
        _, indices = self.index.search(np.array(query_vector).astype('float32'), top_k)
        
        results = []
        for idx in indices[0]:
            if idx != -1 and idx < len(self.documents_store):
                results.append(self.documents_store[idx])
        return results