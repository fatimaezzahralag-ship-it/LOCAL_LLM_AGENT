import streamlit as st
import requests

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
            # Préparation du fichier pour l'envoi vers FastAPI
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
        with st.spinner("L'agent réfléchit..."):
            try:
                response = requests.post(f"{API_URL}/chat", json={"prompt": prompt, "temperature": 0.1})
                
                if response.status_code == 200:
                    data = response.json()
                    answer = data["response"]
                    sources = data.get("sources", [])

                    # Afficher la réponse
                    st.markdown(answer)
                    
                    # Afficher les sources (chunks FAISS) dans un menu déroulant
                    if sources:
                        with st.expander("🔍 Voir les sources extraites de FAISS"):
                            for i, source in enumerate(sources):
                                st.info(f"**Extrait {i+1} :**\n\n{source}")

                    # Sauvegarder dans l'historique
                    st.session_state.messages.append({"role": "assistant", "content": answer})
                
                elif response.status_code == 503:
                    st.error("L'agent est en cours de démarrage ou les modèles ne sont pas chargés.")
                else:
                    st.error(f"Erreur du modèle : {response.text}")
                    
            except requests.exceptions.ConnectionError:
                st.error("Impossible de contacter le backend. Vérifiez que FastAPI tourne.")
                