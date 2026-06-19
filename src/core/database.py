import sqlite3 # Importe le module natif SQLite de Python pour gérer la base de données locale
import os # Importe le module os pour manipuler les chemins de fichiers et dossiers
from datetime import datetime # Importe datetime pour horodater les messages et les uploads
from src.core.config import settings # Importe les configurations pour connaître les dossiers de stockage

DB_PATH = os.path.join(os.path.dirname(__file__), "../../logisync_database.db") # Définit l'emplacement physique du fichier de base de données

def get_db_connection():
    """Crée et retourne une connexion active vers le fichier de la base de données SQLite."""
    conn = sqlite3.connect(DB_PATH) # Ouvre le fichier unique SQLite (le crée s'il n'existe pas)
    conn.row_factory = sqlite3.Row # Permet de récupérer les résultats sous forme de dictionnaires plutôt que de simples tuples
    return conn # Renvoie l'objet de connexion

def init_db():
    """Initialise la base de données en créant la structure des tables indispensables."""
    conn = get_db_connection() # Récupère une connexion active
    cursor = conn.cursor() # Crée un curseur pour exécuter des commandes SQL
    
    # 1. TABLE DES SESSIONS (Missions / Dossiers d'analyse)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS sessions (
            session_id TEXT PRIMARY KEY,          -- Identifiant unique textuel de la session (ex: UUID ou timestamp)
            title TEXT NOT NULL,                  -- Titre de la mission donné par l'utilisateur ou par défaut
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP -- Date et heure de création automatique
        );
    """)
    
    # 2. TABLE DES MESSAGES (Historique de la mémoire conversationnelle)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS messages (
            message_id INTEGER PRIMARY KEY AUTOINCREMENT, -- Identifiant unique incrémenté automatiquement
            session_id TEXT NOT NULL,                     -- Clé étrangère reliant le message à sa session
            role TEXT NOT NULL,                           -- Rôle de l'émetteur : 'user' ou 'assistant'
            content TEXT NOT NULL,                        -- Le texte brut du message
            timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP, -- Horodatage du message
            FOREIGN KEY (session_id) REFERENCES sessions(session_id) ON DELETE CASCADE -- Supprime les messages si la session est supprimée
        );
    """)
    
    # 3. TABLE DES DOCUMENTS METADATA (Pour la gestion de plusieurs bases documentaires)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS documents (
            doc_id INTEGER PRIMARY KEY AUTOINCREMENT, -- Identifiant unique du document indexé
            session_id TEXT NOT NULL,                 -- Clé étrangère reliant le document à une mission spécifique
            filename TEXT NOT NULL,                   -- Nom d'origine du fichier (ex: rapport_mensuel.pdf)
            file_path TEXT NOT NULL,                  -- Chemin local où le fichier est physiquement stocké
            uploaded_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP, -- Date d'indexation
            FOREIGN KEY (session_id) REFERENCES sessions(session_id) ON DELETE CASCADE
        );
    """)
    
    conn.commit() # Valide et enregistre définitivement les modifications de structure sur le disque dur
    conn.close() # Ferme proprement la connexion pour libérer les ressources système
    print("Structure de la base de données SQLite validée et opérationnelle.") # Message de log de démarrage

# --- FONCTIONS DE MANIPULATION DES DONNÉES (CRUD) ---

def create_session(session_id: str, title: str):
    """Enregistre une nouvelle mission d'analyse dans le système."""
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("INSERT OR IGNORE INTO sessions (session_id, title) VALUES (?, ?)", (session_id, title))
    conn.commit()
    conn.close()

def save_message(session_id: str, role: str, content: str):
    """Sauvegarde un message (opérateur ou IA) pour garantir la persistance de la mémoire."""
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("INSERT INTO messages (session_id, role, content) VALUES (?, ?, ?)", (session_id, role, content))
    conn.commit()
    conn.close()

def get_session_history(session_id: str) -> list:
    """Récupère l'intégralité de l'historique d'une discussion pour la réinjecter dans le contexte de l'IA."""
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT role, content FROM messages WHERE session_id = ? ORDER BY timestamp ASC", (session_id,))
    rows = cursor.fetchall()
    conn.close()
    return [{"role": row["role"], "content": row["content"]} for row in rows] # Convertit les lignes SQL en liste de dictionnaires pour FastAPI

def save_document_meta(session_id: str, filename: str, file_path: str):
    """Associe l'indexation d'un fichier à une base/session spécifique."""
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("INSERT INTO documents (session_id, filename, file_path) VALUES (?, ?, ?)", (session_id, filename, file_path))
    conn.commit()
    conn.close()

def get_all_sessions() -> list:
    """Récupère la liste de toutes les missions enregistrées pour l'affichage sur la Sidebar React."""
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT session_id, title, created_at FROM sessions ORDER BY created_at DESC")
    rows = cursor.fetchall()
    conn.close()
    return [dict(row) for row in rows]

def delete_session(session_id: str):
    """Supprime définitivement une mission et tout son historique associé."""
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM sessions WHERE session_id = ?", (session_id,))
    conn.commit()
    conn.close()

def rename_session(session_id: str, new_title: str):
    """Met à jour le titre d'une mission existante."""
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("UPDATE sessions SET title = ? WHERE session_id = ?", (new_title, session_id))
    conn.commit()
    conn.close()