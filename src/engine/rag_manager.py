import os
import faiss
import numpy as np
from sentence_transformers import SentenceTransformer
from rank_bm25 import BM25Okapi
import pickle

class LocalRAGManager:
    def __init__(self, embedding_model_name: str = "sentence-transformers/all-MiniLM-L6-v2"):
        self.encoder = SentenceTransformer(embedding_model_name)
        self.dimension = self.encoder.get_sentence_embedding_dimension()
        
        # 1. Base FAISS (Recherche Sémantique)
        self.index = faiss.IndexFlatL2(self.dimension)
        
        # 2. Base BM25 (Recherche de Mots-clés)
        self.bm25 = None
        
        self.documents_store = []
        
    def add_documents(self, chunks: list[str]):
        """Indexe les documents dans FAISS et BM25."""
        if not chunks:
            return
        
        print(f"Indexation de {len(chunks)} chunks en cours...")
        
        # --- Indexation FAISS ---
        embeddings = self.encoder.encode(chunks, convert_to_numpy=True)
        self.index.add(embeddings)
        self.documents_store.extend(chunks)
        
        # --- Indexation BM25 ---
        # On découpe (tokenize) les textes en mots simples pour BM25
        tokenized_corpus = [chunk.lower().split() for chunk in self.documents_store]
        self.bm25 = BM25Okapi(tokenized_corpus)
        
        print("Documents indexés avec succès dans FAISS et BM25.")

    def search(self, query: str, top_k: int = 3) -> list[str]:
        """Recherche hybride : FAISS (Sémantique) + BM25 (Mots-clés)."""
        if not self.documents_store:
            return []

        # 1. Recherche Sémantique (FAISS)
        query_embedding = self.encoder.encode([query], convert_to_numpy=True)
        distances, faiss_indices = self.index.search(query_embedding, top_k)
        
        # 2. Recherche par Mots-clés (BM25)
        tokenized_query = query.lower().split()
        bm25_scores = self.bm25.get_scores(tokenized_query)
        bm25_indices = np.argsort(bm25_scores)[::-1][:top_k]
        
        # 3. Fusion des résultats (Reranking simple)
        # On combine les index trouvés sans faire de doublons
        combined_indices = list(set(faiss_indices[0].tolist() + bm25_indices.tolist()))
        
        # Si on ne trouve rien d'utile (indices à -1), on nettoie
        combined_indices = [idx for idx in combined_indices if idx != -1]
        
        # On retourne les chunks fusionnés
        return [self.documents_store[idx] for idx in combined_indices[:top_k]]