import streamlit as st
import requests
import json

# L'adresse de votre backend FastAPI
API_URL = "http://127.0.0.1:8000"

# Configuration de la page
st.set_page_config(page_title="Agent LLM Local", page_icon="🤖", layout="wide")
st.title("🤖 Agent LLM Local Intelligent")

# Initialisation de la mémoire de conversation dans Streamlit
if "messages" not in st.session_state:
    st.session_state.messages = []

# --- PANNEAU LATÉRAL : UPLOAD DE DOCUMENTS ---
with st.sidebar:
    st.header("📄 Base Documentaire (RAG)")
    st.write("Chargez un document pour que l'agent l'étudie.")
    
    uploaded_file = st.file_uploader("Choisissez un fichier PDF", type=["pdf"])
    
    if st.button("Indexer le document") and uploaded_file:
        with st.spinner("Indexation vectorielle en cours..."):
            files = {"file": (uploaded_file.name, uploaded_file.getvalue(), "application/pdf")}
            try:
                response = requests.post(f"{API_URL}/upload", files=files)
                if response.status_code == 200:
                    data = response.json()
                    st.success(f"✅ {data['message']}")
                else:
                    st.error(f"Erreur : {response.text}")
            except requests.exceptions.ConnectionError:
                st.error("Impossible de contacter le backend. Le serveur FastAPI est-il lancé ?")

# --- ZONE PRINCIPALE : CHAT ---
# Affichage de l'historique des messages
for message in st.session_state.messages:
    with st.chat_message(message["role"]):
        st.markdown(message["content"])

# Zone de saisie utilisateur
if prompt := st.chat_input("Posez une question sur vos documents..."):
    # 1. Afficher la question de l'utilisateur
    with st.chat_message("user"):
        st.markdown(prompt)
    st.session_state.messages.append({"role": "user", "content": prompt})

    # 2. Interroger l'agent (FastAPI)
    with st.chat_message("assistant"):
        payload = {
            "messages": st.session_state.messages, 
            "temperature": 0.1
        }
        
        try:
            # ON ACTIVE stream=True POUR LE MODE MACHINE À ÉCRIRE
            response = requests.post(f"{API_URL}/chat", json=payload, stream=True)
            
            if response.status_code == 200:
                sources = []
                
                # Le "Décodeur" de flux corrigé (sans nonlocal)
                def stream_parser():
                    for line in response.iter_lines():
                        if line:
                            data = json.loads(line.decode("utf-8"))
                            if "sources" in data:
                                # On ajoute les éléments à la liste existante
                                sources.extend(data["sources"])
                            if "chunk" in data:
                                yield data["chunk"]

                # st.write_stream est la fonction magique de Streamlit !
                full_answer = st.write_stream(stream_parser())
                
                if sources:
                    with st.expander("🔍 Voir les sources extraites"):
                        for i, source in enumerate(sources):
                            st.info(f"**Extrait {i+1} :**\n\n{source}")

                st.session_state.messages.append({"role": "assistant", "content": full_answer})
            
            elif response.status_code == 503:
                st.error("L'agent est en cours de démarrage ou les modèles ne sont pas chargés.")
            elif response.status_code == 400:
                st.error("Veuillez d'abord uploader un document.")
            else:
                st.error(f"Erreur du modèle : {response.text}")
                
        except requests.exceptions.ConnectionError:
            st.error("Impossible de contacter le backend. Vérifiez que FastAPI tourne.")