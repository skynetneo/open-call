# app/transcription.py
import base64
import httpx
import io
from pydub import AudioSegment  # Ensure pydub is installed
from app.config import settings
from app.logger import logger

async def transcribe_audio_streaming(audio_payload: str, http_client: httpx.AsyncClient) -> str:
    """Converts u-law audio to PCM WAV and transcribes using Whisper."""
    try:
        ulaw_audio_bytes = base64.b64decode(audio_payload)
        # Pydub can read u-law directly.  No need to specify format="ulaw".
        audio = AudioSegment.from_file(io.BytesIO(ulaw_audio_bytes), format="mulaw")
        audio = audio.set_frame_rate(8000).set_channels(1).set_sample_width(2)  # Ensure correct format
        pcm_data = io.BytesIO()
        audio.export(pcm_data, format="wav")
        pcm_data.seek(0)  # Rewind

        async with http_client as client:  # Use the provided client
            response = await client.post(settings.WHISPER_API_URL, files={"file": ("audio.wav", pcm_data, "audio/wav")})
            response.raise_for_status()  # Raise HTTP errors
            return response.json().get("text", "").strip()

    except httpx.HTTPError as e:
        logger.error(f"Whisper API error: {e}")
        return ""  # Return empty string on error
    except Exception as e:
        logger.error(f"Transcription error: {e}")
        return ""  # Return empty string on error