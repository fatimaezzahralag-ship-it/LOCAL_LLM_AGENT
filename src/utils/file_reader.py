import csv # Importe le module standard Python pour lire les fichiers tableurs (Comma Separated Values)
from typing import List # Importe le typage 'List' pour préciser le format de retour des fonctions (sécurité du code)

# --- GESTION SÉCURISÉE DES LIBRAIRIES EXTERNES ---
# On utilise des blocs try/except pour que l'application ne plante pas totalement si une librairie manque

try: # Tente de charger la librairie pour les PDF
    import fitz  # PyMuPDF : le moteur d'extraction de texte pour les fichiers PDF
except ImportError: # Si la librairie n'est pas trouvée sur l'ordinateur
    fitz = None # On déclare la variable à "None" (Vide) pour gérer l'erreur proprement plus tard

try: # Tente de charger la librairie pour les fichiers Microsoft Word
    import docx # python-docx : le moteur d'extraction pour les fichiers .docx
except ImportError: # Si la librairie n'est pas installée
    docx = None # On déclare la variable à "None"
    
try:
    import pytesseract # Le pont Python vers le moteur OCR Tesseract
    from PIL import Image # Pillow : librairie pour ouvrir et manipuler les images
    # --- CONFIGURATION DU CHEMIN TESSERACT POUR WSL ---
    pytesseract.pytesseract.tesseract_cmd = r'/usr/bin/tesseract' 
except ImportError:
    pytesseract = None
    Image = None


# --- 1. EXTRACTEUR PDF ---
def extract_text_from_pdf(file_path: str) -> str: # Fonction qui prend le chemin du fichier et renvoie du texte brut
    """Extrait le texte brut d'un fichier PDF.""" # Description de la fonction (Docstring)
    if fitz is None: # Si le moteur PyMuPDF n'est pas installé
        raise RuntimeError( # Déclenche une erreur système avec un message clair pour l'administrateur
            "PyMuPDF n'est pas installé. Utilise requirements-full.txt pour activer l'extraction PDF."
        )

    doc = fitz.open(file_path) # Demande au moteur d'ouvrir et de charger le fichier PDF en mémoire
    text = "" # Initialise une chaîne de caractères vide qui va stocker tout le texte
    for page in doc: # Crée une boucle qui va lire le PDF page par page
        text += page.get_text("text") + "\n" # Extrait le texte de la page actuelle, l'ajoute à la variable globale, et saute une ligne
    return text # Renvoie le texte complet à l'application principale


# --- 2. EXTRACTEUR TEXTE BRUT (.txt, .md) ---
def extract_text_from_txt(file_path: str) -> str: # Fonction dédiée aux fichiers déjà en format texte
    """Extrait le texte brut d'un fichier texte ou markdown (.txt, .md).""" # Docstring
    with open(file_path, "r", encoding="utf-8") as file: # Ouvre le fichier en mode "r" (lecture seule) avec le bon encodage (utf-8 pour les accents)
        text = file.read() # Lit l'intégralité du fichier d'un seul coup et le stocke en mémoire
    return text # Renvoie le texte lu


# --- 3. EXTRACTEUR MICROSOFT WORD (.docx) ---
def extract_text_from_docx(file_path: str) -> str: # Fonction dédiée aux documents bureautiques
    """Extrait le texte brut d'un fichier Microsoft Word (.docx).""" # Docstring
    if docx is None: # Sécurité : vérifie si le moteur Word est bien installé
        raise RuntimeError("python-docx n'est pas installé. Lancez 'pip install python-docx'.") # Bloque l'exécution avec la consigne de réparation
    
    doc = docx.Document(file_path) # Demande au moteur de "décortiquer" le fichier Word (qui est en réalité un dossier zippé contenant du XML)
    text = "" # Initialise la variable de stockage
    for para in doc.paragraphs: # Parcourt le document Word paragraphe par paragraphe (pour garder la structure)
        text += para.text + "\n" # Ajoute le texte du paragraphe et simule la touche 'Entrée' (\n) pour aérer la lecture
    return text # Renvoie l'intégralité du document Word transformé en texte simple


# --- 4. EXTRACTEUR TABLEUR (.csv) ---
def extract_text_from_csv(file_path: str) -> str: # Fonction dédiée aux données tabulaires
    """Extrait et linéarise le contenu d'un fichier tableur CSV pour qu'il soit lisible par l'IA.""" # Docstring
    text = "" # Initialise la variable de stockage
    with open(file_path, "r", encoding="utf-8") as file: # Ouvre le fichier tableau en mode lecture
        reader = csv.reader(file) # Utilise l'outil Python pour comprendre les lignes et les colonnes du tableau
        for row in reader: # Analyse le tableau ligne par ligne
            # Relie toutes les cellules de la ligne avec une virgule et un espace, puis saute une ligne
            # Exemple : "Produit A", "10€", "En stock" -> devient "Produit A, 10€, En stock"
            text += ", ".join(row) + "\n" 
    return text # Renvoie le tableau sous une forme que le modèle de langage peut comprendre

# --- 5. NOUVEAU : EXTRACTEUR VISION OCR (Images/Scans) ---
def extract_text_from_image(file_path: str) -> str:
    """Utilise l'Intelligence Artificielle visuelle (OCR) pour lire le texte sur une image."""
    if pytesseract is None or Image is None:
        raise RuntimeError("pytesseract ou Pillow n'est pas installé. Lancez 'pip install pytesseract Pillow'.")
    
    try:
        # Ouvre l'image avec Pillow
        img = Image.open(file_path)
        # Demande à Tesseract de lire l'image. On force la détection en Français (fra) et Anglais (eng)
        text = pytesseract.image_to_string(img, lang='fra+eng')
        return text
    except Exception as e:
        raise RuntimeError(f"Erreur lors de la lecture optique de l'image : {str(e)}")

# --- 6. LE DÉCOUPEUR SÉMANTIQUE (CHUNKER) ---
def chunk_text(text: str, chunk_size: int = 1000, overlap: int = 200) -> List[str]: # Fonction qui coupe le grand texte en petits morceaux (chunks)
    """
    Découpe le texte en morceaux de taille 'chunk_size' 
    avec un chevauchement pour ne pas couper le contexte au milieu d'une phrase.
    """ # Explication de l'objectif de la fonction
    
    # Une méthode basique basée sur le nombre de caractères. 
    # (Note architecte: Pour la V2 en production lourde, on pourra utiliser un tokenizer mathématique)
    chunks = [] # Initialise une liste vide qui contiendra tous les "morceaux" de texte
    start = 0 # Définit le point de départ de la coupe (caractère 0)
    text_length = len(text) # Calcule le nombre total de lettres/caractères dans tout le document
    
    while start < text_length: # Tant que le point de départ n'a pas atteint la toute fin du document
        end = start + chunk_size # Calcule le point d'arrivée de la coupe (ex: 0 + 1000 = caractère 1000)
        chunks.append(text[start:end]) # Découpe le bloc de texte entre 'start' et 'end' et le range dans la boîte (liste)
        
        # C'est la magie du "Chevauchement" (Overlap) pour éviter de couper une phrase en deux :
        # Au lieu de reprendre exactement où on s'est arrêté (1000), on recule un peu (1000 - 200 = 800)
        # Le prochain bloc commencera à 800, incluant la fin du bloc précédent pour garder le contexte logique !
        start = end - overlap 
        
    return chunks # Renvoie la liste complète des morceaux découpés au moteur de recherche RAG