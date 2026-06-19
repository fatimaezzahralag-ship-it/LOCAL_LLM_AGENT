import faiss
import numpy as np
from sentence_transformers import SentenceTransformer
from rank_bm25 import BM25Okapi

class LocalRAGManager:
    def __init__(self, embedding_model_name: str = "sentence-transformers/all-MiniLM-L6-v2"):
        self.encoder = SentenceTransformer(embedding_model_name)
        self.dimension = self.encoder.get_sentence_embedding_dimension()
        
        # --- STRUCTURE MULTI-BASES ---
        # Au lieu d'une variable unique, on utilise des dictionnaires pour stocker une base par mission
        self.indices = {}          # { "session_id": faiss.IndexFlatL2 }
        self.bm25_models = {}      # { "session_id": BM25Okapi }
        self.documents_stores = {} # { "session_id": ["chunk1", "chunk2"] }
        
    def _ensure_session_exists(self, session_id: str):
        """Vérifie si la mission a déjà sa propre base vectorielle. Sinon, on la crée."""
        if session_id not in self.indices:
            self.indices[session_id] = faiss.IndexFlatL2(self.dimension)
            self.bm25_models[session_id] = None
            self.documents_stores[session_id] = []

    def add_documents(self, chunks: list[str], session_id: str = "default_mission"):
        """Indexe les documents UNIQUEMENT dans le conteneur FAISS/BM25 de la mission ciblée."""
        if not chunks:
            return
        
        self._ensure_session_exists(session_id) # On prépare le "tiroir" pour cette mission
        print(f"Indexation de {len(chunks)} chunks pour la mission '{session_id}'...")
        
        # --- Indexation FAISS Isolée ---
        embeddings = self.encoder.encode(chunks, convert_to_numpy=True)
        self.indices[session_id].add(embeddings)
        self.documents_stores[session_id].extend(chunks)
        
        # --- Indexation BM25 Isolée ---
        tokenized_corpus = [chunk.lower().split() for chunk in self.documents_stores[session_id]]
        self.bm25_models[session_id] = BM25Okapi(tokenized_corpus)
        
        print(f"Documents indexés avec succès dans la base isolée '{session_id}'.")

    def search(self, query: str, top_k: int = 3, session_id: str = "default_mission") -> list[str]:
        """Recherche hybride limitée au périmètre strict de la session demandée."""
        # Si la session n'existe pas ou qu'aucun document n'y a été chargé
        if session_id not in self.documents_stores or not self.documents_stores[session_id]:
            return []

        # 1. Recherche Sémantique (FAISS) dans la base spécifique
        query_embedding = self.encoder.encode([query], convert_to_numpy=True)
        distances, faiss_indices = self.indices[session_id].search(query_embedding, top_k)
        
        # 2. Recherche par Mots-clés (BM25) dans la base spécifique
        tokenized_query = query.lower().split()
        bm25_scores = self.bm25_models[session_id].get_scores(tokenized_query)
        bm25_indices = np.argsort(bm25_scores)[::-1][:top_k]
        
        # 3. Fusion des résultats
        combined_indices = list(set(faiss_indices[0].tolist() + bm25_indices.tolist()))
        combined_indices = [idx for idx in combined_indices if idx != -1]
        
        return [self.documents_stores[session_id][idx] for idx in combined_indices[:top_k]]

    def clear(self, session_id: str = None):
        """Purge la mémoire. Cible une mission précise si un ID est fourni, sinon rase toute la mémoire RAM."""
        if session_id:
            if session_id in self.indices:
                del self.indices[session_id]
                del self.bm25_models[session_id]
                del self.documents_stores[session_id]
                print(f"Mémoire vectorielle purgée pour la mission {session_id}.")
        else:
            self.indices.clear()
            self.bm25_models.clear()
            self.documents_stores.clear()
            print("Purge globale : toutes les bases vectorielles ont été détruites.")