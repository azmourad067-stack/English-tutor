# Main.py - Version Streamlit Cloud
import streamlit as st
import os

# Configuration API pour Streamlit Cloud
def get_openai_client():
    """Obtenir le client OpenAI depuis les secrets Streamlit"""
    try:
        # Essayer les secrets Streamlit d'abord
        if hasattr(st, 'secrets') and 'OPENAI_API_KEY' in st.secrets:
            api_key = st.secrets['OPENAI_API_KEY']
        # Sinon variable d'environnement
        elif 'OPENAI_API_KEY' in os.environ:
            api_key = os.environ['OPENAI_API_KEY']
        else:
            st.error("""
            ## Configuration requise
            Ajoutez votre clé OpenAI API dans :
            
            **Streamlit Cloud:**
            1. Settings → Secrets
            2. Ajoutez: `OPENAI_API_KEY = "votre-clé"`
            
            **Local:**
            Créez un fichier `.env` avec:
            `OPENAI_API_KEY=votre-clé`
            """)
            st.stop()
        
        from openai import OpenAI
        return OpenAI(api_key=api_key)
        
    except ImportError:
        st.error("Package 'openai' non installé. Ajoutez-le à requirements.txt")
        st.stop()

# Initialiser le client
client = get_openai_client()

# Le reste de votre code...
