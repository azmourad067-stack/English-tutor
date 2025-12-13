import streamlit as st
import requests
import json
from datetime import datetime
from streamlit_mic_recorder import mic_recorder
import base64
import os
from pathlib import Path

# Configuration de la page
st.set_page_config(
    page_title="English Conversation Practice",
    page_icon="🗣️",
    layout="wide"
)

# Dossier pour sauvegarder les conversations
SAVE_DIR = Path("saved_conversations")
SAVE_DIR.mkdir(exist_ok=True)

# Fonction pour charger les conversations sauvegardées
def load_saved_conversations():
    """Charge toutes les conversations depuis le dossier de sauvegarde"""
    conversations = []
    if SAVE_DIR.exists():
        for file_path in SAVE_DIR.glob("*.json"):
            try:
                with open(file_path, 'r', encoding='utf-8') as f:
                    conv = json.load(f)
                    conv['file_path'] = str(file_path)
                    conversations.append(conv)
            except Exception as e:
                st.error(f"Erreur lors du chargement de {file_path.name}: {e}")
    
    # Trier par date (plus récent en premier)
    conversations.sort(key=lambda x: x.get('date', ''), reverse=True)
    return conversations

# Fonction pour sauvegarder une conversation
def save_conversation(conversation_data):
    """Sauvegarde une conversation dans un fichier JSON"""
    try:
        # Créer un nom de fichier unique
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        safe_title = "".join(c for c in conversation_data['title'] if c.isalnum() or c in (' ', '-', '_')).strip()
        safe_title = safe_title.replace(' ', '_')[:50]  # Limiter la longueur
        filename = f"{timestamp}_{safe_title}.json"
        file_path = SAVE_DIR / filename
        
        # Ajouter le chemin du fichier
        conversation_data['file_path'] = str(file_path)
        
        # Sauvegarder
        with open(file_path, 'w', encoding='utf-8') as f:
            json.dump(conversation_data, f, indent=2, ensure_ascii=False)
        
        return True, file_path
    except Exception as e:
        return False, str(e)

# Fonction pour supprimer une conversation
def delete_conversation(file_path):
    """Supprime une conversation du disque"""
    try:
        Path(file_path).unlink()
        return True
    except Exception as e:
        st.error(f"Erreur lors de la suppression: {e}")
        return False

# Initialisation de la session
if "messages" not in st.session_state:
    st.session_state.messages = []
if "corrections" not in st.session_state:
    st.session_state.corrections = []
if "conversation_count" not in st.session_state:
    st.session_state.conversation_count = 0
if "audio_processed" not in st.session_state:
    st.session_state.audio_processed = False
if "conversation_title" not in st.session_state:
    st.session_state.conversation_title = ""
if "current_file_path" not in st.session_state:
    st.session_state.current_file_path = None

# Charger les conversations sauvegardées au démarrage
saved_conversations = load_saved_conversations()

# Titre et description
st.title("🗣️ English Conversation Practice")
st.markdown("### Pratiquez votre anglais avec une conversation naturelle - 100% GRATUIT")

# Sidebar pour les paramètres
with st.sidebar:
    st.header("⚙️ Paramètres")
    
    # Choix du service gratuit
    service = st.radio(
        "Service d'IA (gratuit)",
        ["Groq (Recommandé)", "Hugging Face"],
        help="Groq est plus rapide et performant"
    )
    
    # Clé API selon le service
    if service == "Groq (Recommandé)":
        st.info("🎉 Groq offre une API gratuite avec 14,400 requêtes/jour !")
        api_key = st.text_input(
            "Clé API Groq (gratuite)",
            type="password",
            help="Obtenez votre clé sur console.groq.com"
        )
        st.markdown("[📝 Obtenir une clé Groq gratuite](https://console.groq.com)")
        
        # Aide pour vérifier la clé
        with st.expander("❓ Problème avec la clé API ?"):
            st.markdown("""
            **Si la transcription audio ne fonctionne pas:**
            
            1. **Vérifiez votre clé:**
               - Allez sur [console.groq.com](https://console.groq.com)
               - Cliquez sur "API Keys"
               - Vérifiez que votre clé est active
            
            2. **Créez une nouvelle clé:**
               - Cliquez sur "Create API Key"
               - Donnez-lui un nom
               - Copiez la clé complète (commence par `gsk_...`)
               - Collez-la dans le champ ci-dessus
            
            3. **Vérifiez le format:**
               - La clé doit commencer par `gsk_`
               - Elle fait environ 50-60 caractères
               - Pas d'espaces avant/après
            
            4. **En attendant:**
               - Vous pouvez taper vos messages au lieu de parler
               - Les réponses audio fonctionneront toujours
            """)
    else:
        st.info("🤗 Hugging Face offre une API gratuite !")
        api_key = st.text_input(
            "Clé API Hugging Face (gratuite)",
            type="password",
            help="Obtenez votre clé sur huggingface.co"
        )
        st.markdown("[📝 Obtenir une clé HF gratuite](https://huggingface.co/settings/tokens)")
    
    # Option audio
    st.subheader("🔊 Options Audio")
    enable_tts = st.checkbox(
        "Activer les réponses audio",
        value=True,
        help="L'IA vous répondra en audio"
    )
    
    if enable_tts:
        voice_choice = st.selectbox(
            "Voix",
            ["alloy", "echo", "fable", "onyx", "nova", "shimmer"],
            index=4,
            help="Choisissez la voix de l'assistant"
        )
        
        auto_play = st.checkbox(
            "Lecture automatique",
            value=True,
            help="Jouer l'audio automatiquement"
        )
    
    # Niveau d'anglais
    level = st.selectbox(
        "Votre niveau d'anglais",
        ["Débutant (A1-A2)", "Intermédiaire (B1-B2)", "Avancé (C1-C2)"]
    )
    
    # Sujets de conversation
    st.subheader("📚 Sujets suggérés")
    topics = [
        "Daily routines", "Hobbies", "Travel", "Food & Cooking",
        "Movies & TV", "Work & Career", "Family & Friends",
        "Weather", "Technology", "Sports"
    ]
    selected_topic = st.selectbox("Choisir un sujet", ["Libre"] + topics)
    
    # Statistiques
    st.subheader("📊 Statistiques")
    st.metric("Messages envoyés", st.session_state.conversation_count)
    st.metric("Corrections reçues", len(st.session_state.corrections))
    
    # Sauvegarde de conversation
    st.subheader("💾 Sauvegarde")
    
    if len(st.session_state.messages) > 0:
        conv_title = st.text_input(
            "Titre de la conversation",
            value=st.session_state.conversation_title,
            placeholder="Ex: Ma première conversation"
        )
        
        col_save1, col_save2 = st.columns(2)
        
        with col_save1:
            if st.button("💾 Sauvegarder", use_container_width=True):
                if conv_title.strip():
                    conversation_data = {
                        "title": conv_title,
                        "date": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                        "level": level,
                        "topic": selected_topic,
                        "messages": st.session_state.messages.copy(),
                        "corrections": st.session_state.corrections.copy(),
                        "message_count": st.session_state.conversation_count
                    }
                    
                    success, result = save_conversation(conversation_data)
                    
                    if success:
                        st.session_state.conversation_title = conv_title
                        st.session_state.current_file_path = str(result)
                        st.success(f"✅ Sauvegardé dans: {result.name}")
                        st.rerun()
                    else:
                        st.error(f"❌ Erreur de sauvegarde: {result}")
                else:
                    st.error("⚠️ Donnez un titre à la conversation")
        
        with col_save2:
            # Télécharger en JSON
            if st.session_state.messages:
                conversation_json = json.dumps({
                    "title": conv_title or "Conversation sans titre",
                    "date": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                    "level": level,
                    "topic": selected_topic,
                    "messages": st.session_state.messages,
                    "corrections": st.session_state.corrections
                }, indent=2, ensure_ascii=False)
                
                st.download_button(
                    label="📥 Télécharger",
                    data=conversation_json,
                    file_name=f"conversation_{datetime.now().strftime('%Y%m%d_%H%M')}.json",
                    mime="application/json",
                    use_container_width=True
                )
    
    # Historique des conversations
    if len(saved_conversations) > 0:
        st.subheader(f"📚 Conversations ({len(saved_conversations)})")
        
        # Option de recherche
        search_term = st.text_input("🔍 Rechercher", placeholder="Titre ou sujet...")
        
        # Filtrer les conversations
        filtered_convs = saved_conversations
        if search_term:
            filtered_convs = [
                conv for conv in saved_conversations 
                if search_term.lower() in conv['title'].lower() 
                or search_term.lower() in conv.get('topic', '').lower()
            ]
        
        for idx, conv in enumerate(filtered_convs):
            # Indiquer si c'est la conversation actuelle
            is_current = st.session_state.current_file_path == conv.get('file_path')
            title_prefix = "🟢 " if is_current else "📝 "
            
            with st.expander(f"{title_prefix}{conv['title']} - {conv['date'][:16]}"):
                st.markdown(f"**Niveau:** {conv['level']}")
                st.markdown(f"**Sujet:** {conv['topic']}")
                st.markdown(f"**Messages:** {conv['message_count']}")
                st.markdown(f"**Corrections:** {len(conv['corrections'])}")
                
                if is_current:
                    st.info("🟢 C'est la conversation actuelle")
                
                col1, col2, col3 = st.columns(3)
                
                with col1:
                    if st.button("👁️ Charger", key=f"view_{idx}"):
                        st.session_state.messages = conv['messages'].copy()
                        st.session_state.corrections = conv['corrections'].copy()
                        st.session_state.conversation_count = conv['message_count']
                        st.session_state.conversation_title = conv['title']
                        st.session_state.current_file_path = conv.get('file_path')
                        st.rerun()
                
                with col2:
                    conv_json = json.dumps(conv, indent=2, ensure_ascii=False)
                    st.download_button(
                        label="📥 Export",
                        data=conv_json,
                        file_name=f"{conv['title'].replace(' ', '_')}.json",
                        mime="application/json",
                        key=f"download_{idx}"
                    )
                
                with col3:
                    if st.button("🗑️ Supprimer", key=f"delete_{idx}"):
                        if delete_conversation(conv.get('file_path')):
                            st.success("✅ Conversation supprimée")
                            # Si on supprime la conversation actuelle, réinitialiser
                            if is_current:
                                st.session_state.current_file_path = None
                            st.rerun()
    else:
        st.info("📚 Aucune conversation sauvegardée pour le moment")
    
    # Bouton pour réinitialiser
    if st.button("🔄 Nouvelle conversation"):
        st.session_state.messages = []
        st.session_state.corrections = []
        st.session_state.audio_processed = False
        st.session_state.conversation_title = ""
        st.session_state.current_file_path = None
        st.rerun()

# Vérification de la clé API
if not api_key:
    st.warning("⚠️ Veuillez entrer votre clé API gratuite dans la barre latérale pour commencer.")
    
    col1, col2 = st.columns(2)
    
    with col1:
        st.success("### 🚀 Option 1: Groq (Recommandé)")
        st.markdown("""
        **Avantages:**
        - ✅ Très rapide
        - ✅ 14,400 requêtes/jour GRATUITES
        - ✅ Meilleure qualité de réponse
        - ✅ Reconnaissance vocale (Whisper)
        - ✅ Synthèse vocale incluse
        
        **Comment faire:**
        1. Allez sur [console.groq.com](https://console.groq.com)
        2. Créez un compte gratuit
        3. Allez dans "API Keys"
        4. Créez une nouvelle clé
        5. Copiez-la dans la barre latérale
        """)
    
    with col2:
        st.info("### 🤗 Option 2: Hugging Face")
        st.markdown("""
        **Avantages:**
        - ✅ Totalement gratuit
        - ✅ Pas de limite stricte
        - ✅ Beaucoup de modèles disponibles
        
        **Note:** La synthèse vocale nécessite Groq
        
        **Comment faire:**
        1. Allez sur [huggingface.co](https://huggingface.co)
        2. Créez un compte gratuit
        3. Allez dans Settings > Access Tokens
        4. Créez un nouveau token
        5. Copiez-le dans la barre latérale
        """)
    
    st.stop()

# Système de prompt pour l'IA
def get_system_prompt(level, topic):
    level_instructions = {
        "Débutant (A1-A2)": "Use simple vocabulary and short sentences. Speak slowly and clearly.",
        "Intermédiaire (B1-B2)": "Use everyday vocabulary with some idioms. Encourage natural conversation.",
        "Avancé (C1-C2)": "Use advanced vocabulary and complex structures. Challenge the learner."
    }
    
    topic_instruction = f" Focus the conversation on {topic}." if topic != "Libre" else ""
    
    return f"""You are a friendly English conversation partner helping a French speaker practice English.

Level: {level}
Instructions: {level_instructions[level]}{topic_instruction}

Your role:
1. Have natural, friendly conversations like a friend would
2. Ask follow-up questions to keep the conversation flowing
3. If the user makes grammatical errors, gently correct them by:
   - First responding naturally to their message
   - Then adding a helpful note like "💡 Petite correction: instead of 'I go yesterday', say 'I went yesterday'"
4. Encourage the user and be supportive
5. Keep responses concise (2-4 sentences typically)
6. Use casual, friendly language
7. Show interest in what they say

Remember: You're a conversation partner, not a strict teacher. Make it fun and natural!"""

# Fonction pour transcrire l'audio avec Groq Whisper
def transcribe_audio_groq(audio_bytes, api_key):
    """Transcrit l'audio avec Groq Whisper"""
    try:
        url = "https://api.groq.com/openai/v1/audio/transcriptions"
        
        headers = {
            "Authorization": f"Bearer {api_key}"
        }
        
        files = {
            "file": ("audio.wav", audio_bytes, "audio/wav"),
            "model": (None, "whisper-large-v3"),
            "language": (None, "en")
        }
        
        response = requests.post(url, headers=headers, files=files, timeout=30)
        response.raise_for_status()
        return response.json()["text"]
    
    except requests.exceptions.HTTPError as e:
        if e.response.status_code == 401:
            raise Exception("Clé API Groq invalide ou expirée. Vérifiez votre clé dans la barre latérale.")
        elif e.response.status_code == 403:
            raise Exception("Accès refusé. Assurez-vous que votre clé API Groq a les permissions nécessaires.")
        else:
            raise Exception(f"Erreur API Groq: {e.response.status_code} - {e.response.text}")
    except requests.exceptions.Timeout:
        raise Exception("La transcription a pris trop de temps. Réessayez avec un audio plus court.")
    except Exception as e:
        raise Exception(f"Erreur de transcription: {str(e)}")

# Fonction alternative de transcription avec Web Speech API (via navigateur)
def transcribe_audio_browser():
    """Alternative: utilise l'API de reconnaissance vocale du navigateur"""
    st.info("""
    💡 **Alternative gratuite sans API:**
    
    Si la transcription Groq ne fonctionne pas:
    1. Utilisez la reconnaissance vocale de votre navigateur (Chrome/Edge recommandé)
    2. Ou tapez directement votre message
    3. Ou vérifiez que votre clé API Groq est valide
    
    **Pour vérifier votre clé Groq:**
    - Allez sur console.groq.com
    - Vérifiez que la clé est active
    - Créez une nouvelle clé si nécessaire
    """)

# Fonction pour générer l'audio avec OpenAI TTS (compatible Groq)
def text_to_speech(text, api_key, voice="nova"):
    """Utilise l'API OpenAI TTS (gratuit avec certains services ou limité)"""
    try:
        # Pour une solution 100% gratuite, on utilise gTTS via web
        # Mais avec Groq, on peut aussi utiliser leur endpoint TTS s'ils en ont un
        
        # Alternative gratuite : Google TTS via gTTS
        from gtts import gTTS
        import io
        
        # Créer l'audio
        tts = gTTS(text=text, lang='en', slow=False)
        
        # Sauvegarder dans un buffer
        audio_buffer = io.BytesIO()
        tts.write_to_fp(audio_buffer)
        audio_buffer.seek(0)
        
        return audio_buffer.read()
    
    except ImportError:
        # Si gTTS n'est pas disponible, on essaie l'API OpenAI (payante mais compatible)
        st.warning("⚠️ gTTS non installé. Installez-le avec: pip install gtts")
        return None
    except Exception as e:
        st.error(f"Erreur TTS: {str(e)}")
        return None

# Fonction pour créer un lecteur audio HTML5
def create_audio_player(audio_bytes, auto_play=True):
    """Crée un lecteur audio HTML5 avec les données audio"""
    if audio_bytes:
        audio_base64 = base64.b64encode(audio_bytes).decode()
        autoplay_attr = "autoplay" if auto_play else ""
        audio_html = f"""
        <audio controls {autoplay_attr} style="width: 100%;">
            <source src="data:audio/mp3;base64,{audio_base64}" type="audio/mp3">
            Votre navigateur ne supporte pas l'élément audio.
        </audio>
        """
        return audio_html
    return None

# Fonction pour appeler l'API Groq
def call_groq_api(messages, api_key, system_prompt):
    url = "https://api.groq.com/openai/v1/chat/completions"
    
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json"
    }
    
    api_messages = [{"role": "system", "content": system_prompt}]
    api_messages.extend(messages)
    
    data = {
        "model": "llama-3.3-70b-versatile",
        "messages": api_messages,
        "temperature": 0.7,
        "max_tokens": 1000
    }
    
    response = requests.post(url, headers=headers, json=data)
    response.raise_for_status()
    return response.json()["choices"][0]["message"]["content"]

# Fonction pour appeler l'API Hugging Face
def call_huggingface_api(messages, api_key, system_prompt):
    url = "https://api-inference.huggingface.co/models/meta-llama/Meta-Llama-3-8B-Instruct"
    
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json"
    }
    
    full_prompt = system_prompt + "\n\n"
    for msg in messages:
        role = "User" if msg["role"] == "user" else "Assistant"
        full_prompt += f"{role}: {msg['content']}\n"
    full_prompt += "Assistant:"
    
    data = {
        "inputs": full_prompt,
        "parameters": {
            "max_new_tokens": 500,
            "temperature": 0.7,
            "return_full_text": False
        }
    }
    
    response = requests.post(url, headers=headers, json=data)
    response.raise_for_status()
    result = response.json()
    
    if isinstance(result, list) and len(result) > 0:
        return result[0].get("generated_text", "")
    return ""

# Fonction pour analyser les corrections
def extract_corrections(response_text):
    if "💡" in response_text or "correction" in response_text.lower():
        lines = response_text.split("\n")
        for line in lines:
            if "💡" in line or "correction" in line.lower():
                return line.strip()
    return None

# Fonction pour traiter un message (texte ou audio)
def process_message(user_input):
    if not user_input or user_input.strip() == "":
        return
    
    # Ajouter le message de l'utilisateur
    st.session_state.messages.append({"role": "user", "content": user_input})
    st.session_state.conversation_count += 1
    
    # Préparer les messages pour l'API
    api_messages = [
        {"role": msg["role"], "content": msg["content"]}
        for msg in st.session_state.messages
    ]
    
    # Obtenir la réponse de l'IA
    try:
        system_prompt = get_system_prompt(level, selected_topic)
        
        if service == "Groq (Recommandé)":
            assistant_message = call_groq_api(api_messages, api_key, system_prompt)
        else:
            assistant_message = call_huggingface_api(api_messages, api_key, system_prompt)
        
        # Sauvegarder la réponse
        st.session_state.messages.append({
            "role": "assistant",
            "content": assistant_message
        })
        
        # Extraire et sauvegarder les corrections
        correction = extract_corrections(assistant_message)
        if correction:
            st.session_state.corrections.append({
                "timestamp": datetime.now().strftime("%H:%M"),
                "user_message": user_input,
                "correction": correction
            })
        
        return assistant_message
        
    except requests.exceptions.HTTPError as e:
        if e.response.status_code == 401:
            st.error("❌ Clé API invalide. Vérifiez votre clé dans la barre latérale.")
        elif e.response.status_code == 429:
            st.error("⏳ Limite de taux atteinte. Attendez quelques secondes et réessayez.")
        else:
            st.error(f"❌ Erreur API: {str(e)}")
        return None
    except Exception as e:
        st.error(f"❌ Erreur: {str(e)}")
        return None

# Zone de conversation
st.subheader("💬 Conversation")

# Afficher l'historique des messages
for i, msg in enumerate(st.session_state.messages):
    with st.chat_message(msg["role"]):
        st.write(msg["content"])
        
        # Ajouter un lecteur audio pour les messages de l'assistant
        if msg["role"] == "assistant" and enable_tts:
            # Créer une clé unique pour chaque message
            audio_key = f"audio_{i}"
            
            # Vérifier si l'audio existe déjà dans la session
            if audio_key not in st.session_state:
                with st.spinner("🔊 Génération audio..."):
                    audio_bytes = text_to_speech(msg["content"], api_key, voice_choice if 'voice_choice' in locals() else "nova")
                    if audio_bytes:
                        st.session_state[audio_key] = audio_bytes
            
            # Afficher le lecteur audio
            if audio_key in st.session_state:
                audio_html = create_audio_player(st.session_state[audio_key], auto_play=False)
                if audio_html:
                    st.markdown(audio_html, unsafe_allow_html=True)

# Section d'entrée avec micro et texte
col1, col2 = st.columns([3, 1])

with col1:
    user_input = st.chat_input("Tapez votre message en anglais...")
    
with col2:
    st.markdown("### 🎤")
    audio = mic_recorder(
        start_prompt="🎤 Parler",
        stop_prompt="⏹️ Stop",
        just_once=True,
        use_container_width=True,
        key='recorder'
    )

# Traiter l'entrée texte
if user_input:
    with st.chat_message("user"):
        st.write(user_input)
    
    with st.chat_message("assistant"):
        with st.spinner("💭 En train de réfléchir..."):
            assistant_response = process_message(user_input)
            
            if assistant_response:
                st.write(assistant_response)
                
                # Générer et jouer l'audio
                if enable_tts:
                    with st.spinner("🔊 Génération audio..."):
                        audio_bytes = text_to_speech(assistant_response, api_key, voice_choice if 'voice_choice' in locals() else "nova")
                        if audio_bytes:
                            # Sauvegarder dans la session
                            audio_key = f"audio_{len(st.session_state.messages)-1}"
                            st.session_state[audio_key] = audio_bytes
                            
                            # Afficher le lecteur
                            audio_html = create_audio_player(audio_bytes, auto_play=auto_play if 'auto_play' in locals() else True)
                            if audio_html:
                                st.markdown(audio_html, unsafe_allow_html=True)

# Traiter l'entrée audio
if audio and not st.session_state.audio_processed:
    with st.spinner("🎤 Transcription en cours..."):
        try:
            audio_bytes = audio['bytes']
            
            if service == "Groq (Recommandé)":
                try:
                    transcription = transcribe_audio_groq(audio_bytes, api_key)
                except Exception as e:
                    st.error(f"❌ {str(e)}")
                    transcribe_audio_browser()
                    transcription = None
            else:
                st.warning("⚠️ La transcription audio nécessite Groq. Veuillez sélectionner Groq dans les paramètres.")
                transcription = None
            
            if transcription:
                st.session_state.audio_processed = True
                
                with st.chat_message("user"):
                    st.write(f"🎤 {transcription}")
                
                with st.chat_message("assistant"):
                    with st.spinner("💭 En train de réfléchir..."):
                        assistant_response = process_message(transcription)
                        
                        if assistant_response:
                            st.write(assistant_response)
                            
                            # Générer et jouer l'audio
                            if enable_tts:
                                with st.spinner("🔊 Génération audio..."):
                                    audio_bytes_response = text_to_speech(assistant_response, api_key, voice_choice if 'voice_choice' in locals() else "nova")
                                    if audio_bytes_response:
                                        audio_key = f"audio_{len(st.session_state.messages)-1}"
                                        st.session_state[audio_key] = audio_bytes_response
                                        audio_html = create_audio_player(audio_bytes_response, auto_play=auto_play if 'auto_play' in locals() else True)
                                        if audio_html:
                                            st.markdown(audio_html, unsafe_allow_html=True)
        
        except Exception as e:
            st.error(f"❌ Erreur inattendue: {str(e)}")
            st.info("💡 Essayez de taper votre message à la place, ou vérifiez votre clé API Groq.")

# Réinitialiser le flag audio après traitement
if st.session_state.audio_processed:
    st.session_state.audio_processed = False

# Afficher les corrections récentes dans un expander
if st.session_state.corrections:
    with st.expander("📝 Corrections récentes"):
        for corr in reversed(st.session_state.corrections[-5:]):
            st.markdown(f"**[{corr['timestamp']}]** Vous: _{corr['user_message']}_")
            st.markdown(f"{corr['correction']}")
            st.divider()

# Résumé de la conversation actuelle
if len(st.session_state.messages) > 0:
    with st.expander("📊 Résumé de cette conversation"):
        st.markdown(f"""
        - **Messages échangés:** {len(st.session_state.messages)} ({len([m for m in st.session_state.messages if m['role'] == 'user'])} de vous)
        - **Corrections reçues:** {len(st.session_state.corrections)}
        - **Niveau:** {level}
        - **Sujet:** {selected_topic}
        - **Durée approximative:** ~{len(st.session_state.messages) * 30} secondes
        """)
        
        if not st.session_state.conversation_title:
            st.info("💡 N'oubliez pas de sauvegarder cette conversation dans la barre latérale !")
        else:
            if st.session_state.current_file_path:
                st.success(f"✅ Cette conversation est sauvegardée: '{st.session_state.conversation_title}'")
            else:
                st.warning(f"⚠️ Titre défini mais pas encore sauvegardé sur le disque")

# Section d'aide en bas
with st.expander("ℹ️ Comment utiliser cette application"):
    st.markdown("""
    **Conseils pour bien pratiquer:**
    
    1. **Soyez naturel**: Écrivez ou parlez comme vous le feriez normalement
    2. **Ne vous inquiétez pas des erreurs**: C'est en faisant des erreurs qu'on apprend !
    3. **Utilisez les sujets suggérés**: Ils vous aident à démarrer une conversation
    4. **Relisez les corrections**: Elles sont sauvegardées dans la section "Corrections récentes"
    5. **Pratiquez régulièrement**: 10-15 minutes par jour font une grande différence
    6. **Écoutez les réponses**: Activez l'audio pour améliorer votre compréhension orale
    
    **Fonctionnalités:**
    - ✅ Conversations naturelles en anglais
    - ✅ 🎤 Reconnaissance vocale (parlez en anglais!)
    - ✅ 🔊 Réponses audio (écoutez l'anglais!)
    - ✅ 💾 Sauvegarde des conversations
    - ✅ 📥 Export en JSON
    - ✅ 📚 Historique des conversations
    - ✅ Corrections grammaticales douces
    - ✅ Questions pour maintenir la conversation
    - ✅ Adaptation à votre niveau
    - ✅ Sujets variés du quotidien
    - ✅ 100% GRATUIT (Groq + gTTS)
    
    **Utiliser le micro:**
    - Cliquez sur "🎤 Parler" pour commencer l'enregistrement
    - Parlez en anglais
    - Cliquez sur "⏹️ Stop" pour terminer
    - Votre parole sera transcrite et vous recevrez une réponse audio!
    
    **Options audio:**
    - Activez/désactivez les réponses audio dans la barre latérale
    - Choisissez parmi 6 voix différentes
    - Lecture automatique ou manuelle
    
    **Sauvegarde:**
    - 💾 Sauvegardez vos conversations sur le disque (persistant)
    - 📥 Exportez-les en JSON pour les partager
    - 📚 Consultez votre historique à tout moment (même après fermeture)
    - 👁️ Rechargez une ancienne conversation pour la continuer
    - 🗑️ Supprimez les conversations dont vous n'avez plus besoin
    - 🔍 Recherchez dans vos conversations sauvegardées
    - 🟢 Voyez quelle conversation est actuellement active
    """)

# Footer
st.markdown("---")
st.markdown(
    "<div style='text-align: center; color: gray;'>"
    "💡 Application 100% gratuite - Propulsée par Groq + gTTS 🚀<br>"
    "🎤 Reconnaissance vocale + 🔊 Synthèse vocale + 💾 Sauvegarde incluses"
    "</div>",
    unsafe_allow_html=True
)
