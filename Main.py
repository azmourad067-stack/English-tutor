""" Streamlit English Tutor App Features:

Conversational practice using OpenAI ChatCompletion (chat-like corrections & conversation)

Text input conversation

Audio file upload -> transcription using OpenAI Whisper (if user supplies API key)

Server-side TTS using gTTS (assistant speaks responses)

Simple conversation history, correction highlights and suggestions


Notes / requirements:

Python 3.8+

pip install streamlit openai gtts pydub

Requires ffmpeg for pydub (to convert audio formats)

You must provide your OPENAI_API_KEY either in the sidebar or as env var


This is a single-file app to run with: streamlit run streamlit_english_tutor.py """

import os import streamlit as st from gtts import gTTS from io import BytesIO import openai from pydub import AudioSegment

---------------------- Helpers ----------------------

def init(): if 'history' not in st.session_state: st.session_state.history = []  # list of (role, text) if 'openai_key' not in st.session_state: st.session_state.openai_key = os.getenv('OPENAI_API_KEY', '') if 'last_response_audio' not in st.session_state: st.session_state.last_response_audio = None

def set_openai_key(key): st.session_state.openai_key = key openai.api_key = key

def call_openai_chat(messages, model="gpt-4o-mini", temperature=0.7): # messages is a list of dicts {role: 'user'/'assistant'/'system', content: '...'} if not st.session_state.openai_key: st.error("Aucun OPENAI_API_KEY fourni. Entrez-le dans la barre latérale.") return None try: openai.api_key = st.session_state.openai_key resp = openai.ChatCompletion.create( model=model, messages=messages, temperature=temperature, max_tokens=800, ) return resp.choices[0].message.content.strip() except Exception as e: st.error(f"Erreur OpenAI: {e}") return None

def transcribe_audio_file(uploaded_file): # Accepts WAV/MP3/OGG etc; convert to wav then send to OpenAI whisper if key present if not st.session_state.openai_key: st.error("Aucun OPENAI_API_KEY fourni. Entrez-le dans la barre latérale pour activer la transcription audio.") return None try: audio = AudioSegment.from_file(uploaded_file) wav_io = BytesIO() audio.export(wav_io, format='wav') wav_io.seek(0) openai.api_key = st.session_state.openai_key resp = openai.Audio.transcribe("whisper-1", wav_io) return resp['text'] except Exception as e: st.error(f"Erreur transcription: {e}") return None

def tts_and_play(text, lang='en'): try: tts = gTTS(text=text, lang=lang) mp3_io = BytesIO() tts.write_to_fp(mp3_io) mp3_io.seek(0) st.session_state.last_response_audio = mp3_io.read() st.audio(st.session_state.last_response_audio, format='audio/mp3') except Exception as e: st.error(f"Erreur TTS: {e}")

---------------------- UI ----------------------

st.set_page_config(page_title="English Buddy — Practice English", layout='wide') init()

Sidebar

st.sidebar.title("Paramètres") api_key_input = st.sidebar.text_input("OpenAI API Key (optionnel mais recommandé)", type='password', value=st.session_state.openai_key) if api_key_input and api_key_input != st.session_state.openai_key: set_openai_key(api_key_input)

st.sidebar.markdown("---") model_choice = st.sidebar.selectbox("Model (OpenAI)", options=["gpt-4o-mini", "gpt-4o", "gpt-3.5-turbo"], index=0) temp = st.sidebar.slider("Temperature", 0.0, 1.0, 0.7)

st.sidebar.markdown("---") st.sidebar.markdown("Mode d'entrée vocal") st.sidebar.markdown("1) Enregistrer un audio puis téléverser (fonctionne tout de suite).\n2) Utiliser la reconnaissance vocale du navigateur: appuyez sur 'Start (Browser mic)' puis copiez le texte reconnu dans la zone de saisie. (la capture live est limitée par Streamlit sans composant personnalisé)")

Layout

col1, col2 = st.columns([3, 1])

with col1: st.title("English Buddy — discute avec une amie")

# Conversation area
convo_container = st.container()
with convo_container:
    for role, text in st.session_state.history:
        if role == 'user':
            st.markdown(f"**You:** {text}")
        else:
            st.markdown(f"**Buddy:** {text}")

st.markdown("---")

# Input methods
st.subheader("Ta réponse / Parle")
input_mode = st.radio("Mode d'entrée", options=["Texte", "Téléverser audio (fichier)", "Reconnaissance vocale navigateur (copier-coller)"])

user_text = ""
if input_mode == "Texte":
    user_text = st.text_input("Écris ou parle (tape ici)", key='typed_input')
elif input_mode == "Téléverser audio (fichier)":
    uploaded = st.file_uploader("Téléverse ton enregistrement (mp3/wav/ogg)")
    if uploaded is not None:
        with st.spinner("Transcription en cours..."):
            transcription = transcribe_audio_file(uploaded)
        if transcription:
            st.success("Transcription: " + transcription)
            user_text = transcription
else:
    st.markdown("**Navigateur:** clique sur Start puis copy -> puis colle le texte ici.\nCe bouton utilise l'API Web Speech du navigateur. (Chrome/Edge recommandés)")
    js_html = '''
    <div>
    <button id="start">Start (Browser mic)</button>
    <button id="stop">Stop</button>
    <button id="copy">Copy recognized text</button>
    <p id="status">Status: idle</p>
    <textarea id="result" rows=4 style="width:100%"></textarea>
    <script>
    let rec;
    try{
        const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition;
        rec = new SpeechRecognition();
        rec.lang = 'en-US';
        rec.interimResults = true;
        let finalTranscript = '';
        rec.onresult = (e) => {
            let interim = '';
            for (let i = e.resultIndex; i < e.results.length; ++i) {
                if (e.results[i].isFinal) {
                    finalTranscript += e.results[i][0].transcript;
                } else {
                    interim += e.results[i][0].transcript;
                }
            }
            document.getElementById('result').value = finalTranscript + interim;
        }
        rec.onend = () => { document.getElementById('status').innerText='Status: stopped'; }
    } catch(e){
        document.getElementById('status').innerText = 'Web Speech API non supporté dans ce navigateur.';
    }
    document.getElementById('start').onclick = () => { rec && rec.start(); document.getElementById('status').innerText='Status: recording'; }
    document.getElementById('stop').onclick = () => { rec && rec.stop(); document.getElementById('status').innerText='Status: stopping'; }
    document.getElementById('copy').onclick = () => { const t = document.getElementById('result').value; navigator.clipboard.writeText(t); alert('Texte copié — colle-le dans la zone d\'entrée de Streamlit'); }
    </script>
    '''
    st.components.v1.html(js_html, height=220)
    user_text = st.text_input("Colle ici le texte reconnu par le navigateur", key='browser_input')

# Send button
if st.button("Envoyer"):
    if not user_text:
        st.warning("Rien à envoyer — tape quelque chose ou téléverse un audio.")
    else:
        # Append user message
        st.session_state.history.append(('user', user_text))

        # Build messages for OpenAI: include a system prompt to behave like a friendly English tutor
        system_prompt = (
            "You are an empathetic, patient English-speaking friend and tutor. "
            "You should converse naturally about everyday topics, correct the user's English mistakes gently by showing the corrected sentence and a short explanation in French, "
            "and propose follow-up questions to keep the conversation going. Keep responses friendly and roughly 1-3 short paragraphs."
        )
        messages = [
            {"role": "system", "content": system_prompt},
        ]
        # Include short conversation history to keep context (last 8 messages)
        history_slice = st.session_state.history[-10:]
        for role, text in history_slice:
            messages.append({"role": "user" if role=='user' else "assistant", "content": text})

        with st.spinner("Buddy réfléchit..."):
            assistant_reply = call_openai_chat(messages, model=model_choice, temperature=temp)

        if assistant_reply:
            st.session_state.history.append(('assistant', assistant_reply))
            # Show updated convo
            st.experimental_rerun()

st.markdown('---')
st.subheader('Options de correction')
if st.checkbox('Afficher dernière correction séparément'):
    # Try to detect a correction block produced by the assistant by searching history for keywords
    for role, text in reversed(st.session_state.history):
        if role=='assistant' and ('correction' in text.lower() or 'corrig' in text.lower() or 'correct' in text.lower()):
            st.markdown(text)
            break

with col2: st.markdown('## Contrôles rapides') if st.button('Réécouter dernier message (TTS)'): if st.session_state.history and st.session_state.history[-1][0]=='assistant': tts_and_play(st.session_state.history[-1][1]) else: st.info('Aucun message assistant à lire.')

st.markdown('---')
st.markdown('### Historique (export)')
if st.button('Exporter la conversation (.txt)'):
    txt = ''
    for role, text in st.session_state.history:
        prefix = 'You:' if role=='user' else 'Buddy:'
        txt += f"{prefix} {text}\n\n"
    b = BytesIO()
    b.write(txt.encode('utf-8'))
    b.seek(0)
    st.download_button('Télécharger conversation', data=b, file_name='conversation.txt')

st.markdown('---')
st.markdown('### Astuces & limitations')
st.write(
    '- Pour une vraie capture micro live intégrée, on peut ajouter le composant `streamlit-webrtc` ou développer un composant Streamlit personnalisé (je peux t\'aider à le faire).\n'
    '- La transcription audio utilise l\'API OpenAI Whisper si tu fournis ta clé.\n'
    '- La synthèse vocale est faite via gTTS (Google TTS). Pour un son plus naturel on peut intégrer les services TTS commerciaux (ex: Amazon Polly, Azure, ou OpenAI TTS si disponible).\n'
    '- Respecte les quotas et coûts de l\'API OpenAI si tu l\'utilises.'
)

Show TTS playback if exists

if st.session_state.last_response_audio: st.audio(st.session_state.last_response_audio, format='audio/mp3')

Footer quick explanation

st.caption('App built for practice: corrections, conversational prompts, transcription and TTS. Je peux l'adapter selon tes préférences (niveau, sujets, style de correction, fréquence des corrections, etc.).')
