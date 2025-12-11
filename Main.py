import streamlit as st
import os
from dotenv import load_dotenv
from openai import OpenAI
import tempfile
import base64
from utils.speech_utils import transcribe_audio, text_to_speech
from utils.grammar_checker import check_and_correct_grammar
from utils.conversation import get_ai_response

# Load environment variables
load_dotenv()

# Initialize OpenAI client
client = OpenAI(api_key=os.getenv('OPENAI_API_KEY'))

# Page configuration
st.set_page_config(
    page_title="English Conversation Partner",
    page_icon="🗣️",
    layout="wide"
)

# Custom CSS for better UI
st.markdown("""
<style>
    .main-header {
        font-size: 2.5rem;
        color: #1E3A8A;
        text-align: center;
        margin-bottom: 2rem;
    }
    .conversation-box {
        background-color: #F3F4F6;
        border-radius: 10px;
        padding: 20px;
        margin: 10px 0;
        min-height: 300px;
        max-height: 400px;
        overflow-y: auto;
    }
    .user-message {
        background-color: #DBEAFE;
        padding: 10px;
        border-radius: 10px;
        margin: 5px 0;
        text-align: right;
    }
    .ai-message {
        background-color: #E5E7EB;
        padding: 10px;
        border-radius: 10px;
        margin: 5px 0;
    }
    .correction {
        background-color: #FEF3C7;
        border-left: 4px solid #F59E0B;
        padding: 8px;
        margin: 5px 0;
        font-size: 0.9rem;
    }
</style>
""", unsafe_allow_html=True)

# App title
st.markdown('<h1 class="main-header">🗣️ English Conversation Partner</h1>', unsafe_allow_html=True)

# Initialize session state for conversation history
if 'conversation_history' not in st.session_state:
    st.session_state.conversation_history = []
if 'corrections' not in st.session_state:
    st.session_state.corrections = []

# Sidebar for settings
with st.sidebar:
    st.header("Settings")
    
    # Voice settings
    st.subheader("Voice Settings")
    voice_gender = st.selectbox(
        "Assistant Voice",
        ["Female", "Male", "Neutral"]
    )
    
    speech_speed = st.slider(
        "Speech Speed",
        min_value=50,
        max_value=300,
        value=150,
        help="Words per minute"
    )
    
    # Conversation settings
    st.subheader("Conversation Settings")
    conversation_topic = st.selectbox(
        "Topic",
        ["Daily Life", "Travel", "Food & Cooking", "Hobbies", "Work & Career", "Free Conversation"]
    )
    
    difficulty_level = st.select_slider(
        "Difficulty Level",
        options=["Beginner", "Intermediate", "Advanced"]
    )
    
    # Correction settings
    st.subheader("Correction Settings")
    correct_grammar = st.checkbox("Correct Grammar", value=True)
    correct_pronunciation = st.checkbox("Suggest Pronunciation", value=True)
    
    if st.button("Clear Conversation", type="secondary"):
        st.session_state.conversation_history = []
        st.session_state.corrections = []
        st.rerun()

# Main layout
col1, col2 = st.columns([2, 1])

with col1:
    # Conversation display
    st.subheader("Conversation")
    conversation_container = st.container()
    
    with conversation_container:
        for message in st.session_state.conversation_history:
            if message["role"] == "user":
                st.markdown(f'<div class="user-message"><strong>You:</strong> {message["content"]}</div>', 
                          unsafe_allow_html=True)
            else:
                st.markdown(f'<div class="ai-message"><strong>Assistant:</strong> {message["content"]}</div>', 
                          unsafe_allow_html=True)
        
        # Show corrections
        if st.session_state.corrections:
            st.subheader("📝 Corrections")
            for correction in st.session_state.corrections[-3:]:  # Show last 3 corrections
                st.markdown(f'<div class="correction">{correction}</div>', unsafe_allow_html=True)

with col2:
    # Voice input section
    st.subheader("Speak Now")
    
    # Record audio
    audio_value = st.audio_input(
        "Record your message",
        sample_rate=16000,  # Optimal for speech recognition[citation:3]
        help="Click to start recording, click again to stop"
    )
    
    # Or type input
    text_input = st.text_area(
        "Or type your message:",
        height=100,
        placeholder="Type your message here..."
    )
    
    # Process button
    if st.button("Send Message", type="primary", use_container_width=True):
        user_input = ""
        
        # Process audio if available
        if audio_value:
            with st.spinner("Transcribing your speech..."):
                try:
                    # Transcribe audio to text
                    user_input = transcribe_audio(audio_value, client)
                    st.success("Speech transcribed successfully!")
                except Exception as e:
                    st.error(f"Error transcribing audio: {str(e)}")
                    user_input = ""
        
        # Use text input if no audio or transcription failed
        if not user_input and text_input:
            user_input = text_input
        
        if user_input:
            # Add user message to history
            st.session_state.conversation_history.append({
                "role": "user",
                "content": user_input
            })
            
            # Check grammar if enabled
            if correct_grammar and user_input:
                with st.spinner("Checking grammar..."):
                    correction = check_and_correct_grammar(user_input)
                    if correction:
                        st.session_state.corrections.append(correction)
            
            # Get AI response
            with st.spinner("Thinking of a response..."):
                try:
                    # Get conversation context
                    context = "\n".join([
                        f"{msg['role']}: {msg['content']}" 
                        for msg in st.session_state.conversation_history[-5:]  # Last 5 messages
                    ])
                    
                    # Get AI response
                    ai_response = get_ai_response(
                        user_input,
                        context,
                        difficulty_level,
                        conversation_topic,
                        client
                    )
                    
                    # Add AI response to history
                    st.session_state.conversation_history.append({
                        "role": "assistant",
                        "content": ai_response
                    })
                    
                    # Convert response to speech
                    with st.spinner("Generating voice response..."):
                        audio_file = text_to_speech(
                            ai_response,
                            voice_gender.lower(),
                            speech_speed
                        )
                        
                        # Play audio
                        if audio_file:
                            st.audio(audio_file, format='audio/mp3')
                            
                            # Download option
                            with open(audio_file, "rb") as f:
                                audio_bytes = f.read()
                            
                            st.download_button(
                                label="Download Response Audio",
                                data=audio_bytes,
                                file_name="english_response.mp3",
                                mime="audio/mp3"
                            )
                    
                except Exception as e:
                    st.error(f"Error generating response: {str(e)}")
            
            st.rerun()

# Practice exercises section
st.divider()
st.subheader("💪 Practice Exercises")

tab1, tab2, tab3 = st.tabs(["Vocabulary", "Grammar", "Pronunciation"])

with tab1:
    if st.button("Give me a new word to learn"):
        word_response = get_ai_response(
            "Give me one useful English word to learn with its definition and example sentence",
            "",
            difficulty_level,
            "Vocabulary",
            client
        )
        st.info(word_response)

with tab2:
    grammar_point = st.selectbox(
        "Practice a grammar point",
        ["Present Tense", "Past Tense", "Future Tense", "Conditionals", "Prepositions"]
    )
    if st.button(f"Practice {grammar_point}"):
        exercise = get_ai_response(
            f"Create a short exercise to practice {grammar_point} with 3 questions",
            "",
            difficulty_level,
            "Grammar",
            client
        )
        st.info(exercise)

with tab3:
    if st.button("Practice pronunciation with tongue twister"):
        tongue_twister = get_ai_response(
            "Give me an English tongue twister suitable for my level",
            "",
            difficulty_level,
            "Pronunciation",
            client
        )
        st.info(tongue_twister)
        if st.button("Say it slowly"):
            slow_audio = text_to_speech(
                f"Say this slowly: {tongue_twister}",
                voice_gender.lower(),
                100  # Slow speed
            )
            if slow_audio:
                st.audio(slow_audio, format='audio/mp3')
