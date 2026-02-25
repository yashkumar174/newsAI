import os
import re
import tempfile
from openai import OpenAI
from dotenv import load_dotenv

load_dotenv()


def strip_markdown(text: str) -> str:
    """Remove markdown formatting for cleaner TTS output."""
    text = re.sub(r'\*+', '', text)
    text = re.sub(r'\[([^\]]+)\]\([^\)]+\)', r'\1', text)
    text = re.sub(r'https?://\S+', '', text)
    text = re.sub(r'[🔗📰⏰🚨☀️✅❌👋🔍🗣️🔄⚙️]', '', text)
    text = re.sub(r'\n{3,}', '\n\n', text)
    text = re.sub(r' {2,}', ' ', text)
    return text.strip()


def text_to_speech(text: str) -> str:
    """
    Convert text to speech using OpenAI TTS and save as an mp3 file.
    Returns the path to the temporary mp3 file.
    """
    clean_text = strip_markdown(text)

    if not clean_text:
        raise ValueError("No text to convert to speech.")

    # Truncate to 4096 chars (OpenAI TTS limit)
    if len(clean_text) > 4096:
        clean_text = clean_text[:4096]

    client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

    response = client.audio.speech.create(
        model="tts-1",
        voice="nova",       # Options: alloy, echo, fable, onyx, nova, shimmer
        input=clean_text,
    )

    temp_file = tempfile.NamedTemporaryFile(delete=False, suffix='.mp3', prefix='news_voice_')
    response.stream_to_file(temp_file.name)

    return temp_file.name


def cleanup_audio(file_path: str):
    """Remove a temporary audio file after sending."""
    try:
        if file_path and os.path.exists(file_path):
            os.remove(file_path)
    except OSError:
        pass
