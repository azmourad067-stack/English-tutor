import streamlit as st
import os
from dotenv import load_dotenv
import tempfile
from gtts import gTTS
import pyttsx3
from spellchecker import SpellChecker
import spacy
import re
import speech_recognition as sr
import io

# ===== CONFIGURATION GROQ =====
def setup_groq_client():
    """Configurer le client Groq"""
    load_dotenv()
    
    # Essayer différents noms de variables pour la clé
    api_key = None
    possible_keys = [
        os.getenv('GROQ_API_KEY'),
        os.getenv('GROQAPI_KEY'),
        st.secrets.get('GROQ_API_KEY') if hasattr(st, 'secrets') else None,
        st.secrets.get('GROQAPI_KEY') if hasattr(st, 'secrets') else None,
    ]
    
    for key in possible_keys:
        if key:
            api_key = key
            break
    
    if not api_key:
        st.sidebar.warning("🔑 Clé API Groq non trouvée")
        
        with st.sidebar.expander("Configurer la clé API Groq", expanded=True):
            api_key_input = st.text_input(
                "Entrez votre clé Groq API:",
                type="password",
                placeholder="gsk_..."
            )
            
            if api_key_input:
                api_key = api_key_input
                st.success("Clé API Groq configurée !")
                st.session_state.groq_api_key = api_key
            else:
                st.info("""
                **Comment obtenir une clé Groq GRATUITE :**
                1. Allez sur [console.groq.com](https://console.groq.com)
                2. Créez un compte gratuit
                3. Cliquez sur "API Keys" → "Create API Key"
                4. Copiez la clé (commence par `gsk_`)
                5. Collez-la ici
                
                **Avantages de Groq :**
                • Gratuit avec limites généreuses
                • Ultra rapide (LLaMA 3, Mixtral)
                • Pas besoin de carte bancaire
                """)
                return None
    
    try:
        from groq import Groq
        return Groq(api_key=api_key)
    except ImportError:
        st.error("Package 'groq' non installé. Ajoutez 'groq' à requirements.txt")
        return None
    except Exception as e:
        st.error(f"Erreur avec Groq: {str(e)}")
        return None

# ===== FONCTIONS AUDIO AVEC SPEECH_RECOGNITION =====
def transcribe_audio_groq(audio_bytes):
    """Transcrire l'audio avec speech_recognition (gratuit)"""
    try:
        # Créer un fichier temporaire
        with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tmp_file:
            tmp_file.write(audio_bytes)
            tmp_path = tmp_file.name
        
        # Utiliser speech_recognition
        recognizer = sr.Recognizer()
        
        with sr.AudioFile(tmp_path) as source:
            # Ajuster au bruit ambiant
            recognizer.adjust_for_ambient_noise(source, duration=0.5)
            audio = recognizer.record(source)
            
            try:
                # Essayer Google Web Speech API (gratuit)
                text = recognizer.recognize_google(audio, language="en-US")
                os.unlink(tmp_path)
                return text
            except sr.UnknownValueError:
                os.unlink(tmp_path)
                return "Sorry, I couldn't understand the audio. Please try again."
            except sr.RequestError as e:
                os.unlink(tmp_path)
                return f"Speech recognition error: {e}. Please try typing instead."
                
    except Exception as e:
        st.error(f"Erreur de transcription: {str(e)}")
        return None

# ===== FONCTIONS GROQ POUR LA CONVERSATION =====
def get_groq_response(user_input, context, level, topic, client):
    """Obtenir une réponse de Groq"""
    try:
        # Construire le prompt pour Groq
        system_prompt = f"""You are a friendly English conversation partner and teacher.
        Student level: {level}
        Today's topic: {topic}
        
        Your role:
        1. Have natural, friendly conversations about daily life
        2. Ask follow-up questions to keep conversation flowing
        3. Use appropriate vocabulary for student's level
        4. Occasionally introduce useful phrases or expressions
        5. Be encouraging and supportive
        6. Keep responses concise (2-3 sentences)
        7. If student makes mistakes, gently correct them in a friendly way
        
        Conversation context: {context}
        
        Student: {user_input}
        
        Respond naturally as a friend would."""
        
        # Appeler Groq API
        response = client.chat.completions.create(
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_input}
            ],
            model="llama3-8b-8192",  # Modèle gratuit et rapide
            temperature=0.7,
            max_tokens=150,
            top_p=0.9
        )
        
        return response.choices[0].message.content
        
    except Exception as e:
        st.error(f"Erreur Groq: {str(e)}")
        # Réponses de secours
        fallback_responses = [
            "That's interesting! Tell me more about that.",
            "I love practicing English with you! What would you like to talk about?",
            "How was your day? Did anything interesting happen?",
            "Tell me about your hobbies or interests.",
            "What's something you're looking forward to?"
        ]
        import random
        return random.choice(fallback_responses)

# ===== FONCTIONS UTILITAIRES =====
def text_to_speech_gtts(text, voice_type="female"):
    """Synthèse vocale avec gTTS"""
    try:
        temp_file = tempfile.NamedTemporaryFile(delete=False, suffix=".mp3")
        temp_path = temp_file.name
        temp_file.close()
        
        tts = gTTS(text=text, lang='en', slow=False)
        tts.save(temp_path)
        return temp_path
        
    except Exception as e:
        # Fallback avec pyttsx3
        try:
            engine = pyttsx3.init()
            voices = engine.getProperty('voices')
            
            if voice_type == "female" and len(voices) > 1:
                engine.setProperty('voice', voices[1].id)
            elif voice_type == "male" and len(voices) > 0:
                engine.setProperty('voice', voices[0].id)
            
            engine.setProperty('rate', 150)
            engine.setProperty('volume', 0.9)
            
            engine.save_to_file(text, temp_path)
            engine.runAndWait()
            return temp_path
            
        except Exception as e2:
            st.error(f"Erreur synthèse vocale: {str(e2)}")
            return None

def check_grammar_simple(text):
    """Vérification de grammaire"""
    corrections = []
    spell = SpellChecker(language='en')
    
    # Erreurs courantes
    common_errors = {
        r'\bi (am|was)\b': 'I',
        r'your welcome': "you're welcome",
        r'could of': 'could have',
        r'would of': 'would have',
        r'should of': 'should have',
    }
    
    for pattern, correction in common_errors.items():
        if re.search(pattern, text, re.IGNORECASE):
            corrections.append(f"Common error: Use '{correction}'")
    
    # Vérifier l'orthographe
    words = text.split()
    misspelled = spell.unknown(words)
    
    if misspelled:
        for word in misspelled:
            correction = spell.correction(word)
            if correction and correction != word:
                corrections.append(f"Spelling: '{word}' → '{correction}'")
    
    if corrections:
        return "💡 Suggestions:\n" + "\n".join(f"- {c}" for c in corrections[:3])
    return None

# ===== INITIALISATION =====
# Configurer le client Groq
client = setup_groq_client()

# Initialiser SpaCy
try:
    nlp = spacy.load("en_core_web_sm")
except:
    st.info("📦 Downloading language model...")
    import subprocess
    subprocess.run(["python", "-m", "spacy", "download", "en_core_web_sm"])
    nlp = spacy.load("en_core_web_sm")

# ===== INTERFACE STREAMLIT =====
st.set_page_config(
    page_title="English Conversation Partner (Groq)",
    page_icon="⚡",
    layout="wide"
)

# CSS personnalisé
st.markdown("""
<style>
    .main-header {
        font-size: 2.5rem;
        color: #7C3AED;
        text-align: center;
        margin-bottom: 1rem;
    }
    .sub-header {
        color: #8B5CF6;
        text-align: center;
        margin-bottom: 2rem;
    }
    .groq-badge {
        background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
        color: white;
        padding: 5px 15px;
        border-radius: 20px;
        display: inline-block;
        font-size: 0.8rem;
        margin-bottom: 20px;
    }
    .user-message {
        background-color: #E0E7FF;
        padding: 12px;
        border-radius: 10px;
        margin: 8px 0;
        text-align: right;
        border-left: 4px solid #4F46E5;
    }
    .ai-message {
        background-color: #F3F4F6;
        padding: 12px;
        border-radius: 10px;
        margin: 8px 0;
        border-left: 4px solid #8B5CF6;
    }
    .correction {
        background-color: #FEF3C7;
        border-left: 4px solid #F59E0B;
        padding: 10px;
        margin: 8px 0;
        font-size: 0.9rem;
        border-radius: 5px;
    }
    .feature-card {
        background: white;
        padding: 15px;
        border-radius: 10px;
        border: 1px solid #E5E7EB;
        margin: 10px 0;
    }
</style>
""", unsafe_allow_html=True)

# En-tête avec badge Groq
st.markdown('<div class="groq-badge">⚡ Powered by Groq AI</div>', unsafe_allow_html=True)
st.markdown('<h1 class="main-header">🗣️ English Conversation Partner</h1>', unsafe_allow_html=True)
st.markdown('<p class="sub-header">Practice English with AI - Fast & Free with Groq</p>', unsafe_allow_html=True)

# Initialiser l'état de session
if 'conversation_history' not in st.session_state:
    st.session_state.conversation_history = []
if 'corrections' not in st.session_state:
    st.session_state.corrections = []
if 'groq_api_key' not in st.session_state:
    st.session_state.groq_api_key = None

# Barre latérale
with st.sidebar:
    st.header("⚙️ Configuration")
    
    if not client:
        st.error("❌ Groq API Key Missing")
        
        col1, col2 = st.columns(2)
        with col1:
            if st.button("🔄 Try Again", use_container_width=True):
                st.rerun()
        with col2:
            if st.button("🎮 Demo Mode", use_container_width=True):
                st.session_state.demo_mode = True
                st.rerun()
    
    st.header("🎛️ Settings")
    
    # Options de voix
    st.subheader("Voice Settings")
    voice_gender = st.selectbox(
        "Assistant Voice",
        ["Female", "Male"]
    )
    
    # Sujets de conversation
    st.subheader("Conversation Topic")
    conversation_topic = st.selectbox(
        "Choose a topic",
        [
            "Daily Life", "Travel", "Food & Cooking", "Hobbies", 
            "Work & Career", "Movies & TV", "Sports", "Music",
            "Technology", "Health & Fitness", "Free Conversation"
        ]
    )
    
    # Niveau de difficulté
    difficulty_level = st.select_slider(
        "Difficulty Level",
        options=["Beginner", "Intermediate", "Advanced"],
        value="Intermediate"
    )
    
    # Corrections
    st.subheader("Corrections")
    correct_grammar = st.checkbox("Correct my grammar", value=True)
    show_pronunciation = st.checkbox("Show pronunciation tips", value=True)
    
    # Boutons d'action
    col1, col2 = st.columns(2)
    with col1:
        if st.button("🗑️ Clear Chat", use_container_width=True):
            st.session_state.conversation_history = []
            st.session_state.corrections = []
            st.rerun()
    with col2:
        if st.button("💡 Conversation Tips", use_container_width=True):
            st.info("💬 **Tips for better practice:**\n1. Speak naturally\n2. Don't worry about mistakes\n3. Ask questions\n4. Use new vocabulary")

# Interface principale
col1, col2 = st.columns([2, 1])

with col1:
    # Zone de conversation
    st.subheader("💬 Conversation")
    
    conversation_container = st.container(height=400)
    with conversation_container:
        if not st.session_state.conversation_history:
            st.info("👋 Start by saying hello! Record your voice or type a message.")
        
        for message in st.session_state.conversation_history:
            if message["role"] == "user":
                st.markdown(f'<div class="user-message"><strong>You:</strong> {message["content"]}</div>', 
                          unsafe_allow_html=True)
            else:
                st.markdown(f'<div class="ai-message"><strong>Assistant:</strong> {message["content"]}</div>', 
                          unsafe_allow_html=True)
    
    # Affichage des corrections
    if st.session_state.corrections:
        st.subheader("📝 Corrections & Tips")
        for correction in st.session_state.corrections[-3:]:
            st.markdown(f'<div class="correction">{correction}</div>', unsafe_allow_html=True)

with col2:
    # Zone d'entrée
    st.subheader("🎤 Speak or Type")
    
    # Option 1: Enregistrement audio
    st.write("**Record your message:**")
    audio_data = st.audio_input(
        "Click to record",
        key="audio_input",
        help="Click to start, click again to stop"
    )
    
    # Option 2: Texte
    st.write("**Or type your message:**")
    text_input = st.text_area(
        "Type here:",
        height=120,
        placeholder="Hello! How are you today?",
        label_visibility="collapsed"
    )
    
    # Bouton d'envoi
    send_disabled = not client and not st.session_state.get('demo_mode', False)
    
    if st.button("🚀 Send Message", 
                 type="primary", 
                 use_container_width=True,
                 disabled=send_disabled):
        
        user_input = ""
        
        # Traiter l'audio
        if audio_data:
            with st.spinner("🎤 Listening..."):
                user_input = transcribe_audio_groq(audio_data)
                if user_input:
                    st.success("✅ Transcribed successfully!")
        
        # Sinon utiliser le texte
        if not user_input and text_input:
            user_input = text_input
        
        if user_input:
            # Ajouter à l'historique
            st.session_state.conversation_history.append({
                "role": "user",
                "content": user_input
            })
            
            # Vérifier la grammaire
            if correct_grammar:
                with st.spinner("🔍 Checking grammar..."):
                    correction = check_grammar_simple(user_input)
                    if correction:
                        st.session_state.corrections.append(correction)
            
            # Obtenir une réponse
            with st.spinner("💭 Thinking..."):
                # Mode démo ou réel
                if not client and st.session_state.get('demo_mode', False):
                    # Réponses démo
                    demo_responses = [
                        "Hi there! I'm your English practice partner. How can I help you practice today?",
                        "Great to meet you! What would you like to talk about?",
                        "I'd love to help you practice English! Tell me about your day.",
                        "Hello! I'm here to help you improve your English. What's on your mind?"
                    ]
                    import random
                    ai_response = random.choice(demo_responses)
                else:
                    # Contexte pour la conversation
                    context = "\n".join([
                        f"{msg['role']}: {msg['content']}" 
                        for msg in st.session_state.conversation_history[-4:]
                    ])
                    
                    # Obtenir réponse Groq
                    ai_response = get_groq_response(
                        user_input,
                        context,
                        difficulty_level,
                        conversation_topic,
                        client
                    )
                
                # Ajouter la réponse
                st.session_state.conversation_history.append({
                    "role": "assistant",
                    "content": ai_response
                })
                
                # Synthèse vocale
                with st.spinner("🔊 Generating voice..."):
                    audio_file = text_to_speech_gtts(ai_response, voice_gender.lower())
                    
                    if audio_file:
                        st.audio(audio_file, format='audio/mp3')
                        
                        # Option de téléchargement
                        with open(audio_file, "rb") as f:
                            audio_bytes = f.read()
                        
                        st.download_button(
                            label="📥 Download Audio",
                            data=audio_bytes,
                            file_name="english_practice.mp3",
                            mime="audio/mp3",
                            use_container_width=True
                        )
            
            st.rerun()

# Section d'exercices
st.divider()
st.subheader("💪 Practice Exercises")

tab1, tab2, tab3 = st.tabs(["Vocabulary Builder", "Grammar Practice", "Pronunciation"])

with tab1:
    col1, col2 = st.columns([2, 1])
    with col1:
        st.markdown("""
        <div class="feature-card">
        <h4>📚 Word of the Day</h4>
        Learn new vocabulary with context
        </div>
        """, unsafe_allow_html=True)
    
    with col2:
        if st.button("Get New Word", use_container_width=True):
            if client:
                with st.spinner("Finding interesting word..."):
                    word_response = get_groq_response(
                        f"Give me one useful English word at {difficulty_level} level with its definition and an example sentence",
                        "",
                        difficulty_level,
                        "Vocabulary",
                        client
                    )
                    st.info(word_response)
            else:
                st.info("**Perseverance** (noun):\nContinuing to try despite difficulties.\nExample: Learning English requires perseverance and regular practice.")

with tab2:
    grammar_point = st.selectbox(
        "Choose grammar point:",
        ["Present Tenses", "Past Tenses", "Future Tenses", "Conditionals", "Prepositions", "Articles"],
        key="grammar_select"
    )
    
    if st.button(f"Practice {grammar_point}", use_container_width=True):
        if client:
            with st.spinner("Creating exercise..."):
                exercise = get_groq_response(
                    f"Create a short exercise with 3 questions to practice {grammar_point} at {difficulty_level} level",
                    "",
                    difficulty_level,
                    "Grammar",
                    client
                )
                st.info(exercise)
        else:
            st.info(f"**{grammar_point} Practice:**\n1. Complete the sentence: I usually ___ (go) to work at 8 AM.\n2. What's the correct form? She ___ (study) English every day.\n3. Make a question: you / like / learning English?")

with tab3:
    if st.button("🎯 Get Tongue Twister", use_container_width=True):
        if client:
            with st.spinner("Finding tongue twister..."):
                tongue_twister = get_groq_response(
                    "Give me an English tongue twister suitable for pronunciation practice",
                    "",
                    difficulty_level,
                    "Pronunciation",
                    client
                )
                st.info(tongue_twister)
                
                # Dire lentement
                slow_text = f"Say this slowly: {tongue_twister}"
                slow_audio = text_to_speech_gtts(slow_text, voice_gender.lower())
                if slow_audio:
                    st.audio(slow_audio, format='audio/mp3')
        else:
            st.info("**Tongue Twister:**\nShe sells seashells by the seashore.")

# Pied de page
st.divider()
col1, col2, col3 = st.columns(3)
with col1:
    st.caption("⚡ **Powered by Groq**")
    st.caption("Fast LLM inference")
with col2:
    st.caption("🎯 **Free to use**")
    st.caption("No credit card required")
with col3:
    st.caption("🗣️ **Real conversations**")
    st.caption("Practice daily English")

# Information sur l'utilisation de Groq
with st.expander("ℹ️ About Groq API"):
    st.markdown("""
    **Why Groq?**
    - 🆓 **Free tier** with generous limits
    - ⚡ **Ultra-fast** responses (200+ tokens/sec)
    - 🤖 **Modern models** (LLaMA 3, Mixtral)
    - 🔒 **Privacy focused**
    
    **How to get your API key:**
    1. Go to [console.groq.com](https://console.groq.com)
    2. Sign up for free
    3. Navigate to "API Keys"
    4. Click "Create API Key"
    5. Copy the key (starts with `gsk_`)
    6. Paste in the sidebar
    
    **Current limits (free tier):**
    - 30 requests per minute
    - Suitable for regular practice
    - No credit card required
    """)
