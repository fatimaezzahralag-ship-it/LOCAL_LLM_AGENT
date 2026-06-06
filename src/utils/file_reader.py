from typing import List

try:
    import fitz  # PyMuPDF
except ImportError:
    fitz = None

def extract_text_from_pdf(file_path: str) -> str:
    """Extrait le texte brut d'un fichier PDF."""
    if fitz is None:
        raise RuntimeError(
            "PyMuPDF n'est pas installé. Utilise requirements-full.txt pour activer l'extraction PDF."
        )

    doc = fitz.open(file_path)
    text = ""
    for page in doc:
        text += page.get_text("text") + "\n"
    return text

def chunk_text(text: str, chunk_size: int = 1000, overlap: int = 200) -> List[str]:
    """
    Découpe le texte en morceaux de taille 'chunk_size' 
    avec un chevauchement pour ne pas couper le contexte au milieu d'une phrase.
    """
    # Une méthode basique basée sur les caractères. 
    # Pour la V2, on pourra passer sur un tokenizer spécifique.
    chunks = []
    start = 0
    text_length = len(text)
    
    while start < text_length:
        end = start + chunk_size
        chunks.append(text[start:end])
        start = end - overlap
        
    return chunks