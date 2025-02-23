# app/clients.py
import httpx
from twilio.rest import Client  # Still synchronous, but we'll handle it
from groq import Groq
from supabase import create_client, Client as SupabaseClientType
from google.cloud import aiplatform
from google.oauth2 import service_account
import json
from app.config import settings
from app.logger import logger  # Use the application logger
import asyncio

class TwilioClient:
    def __init__(self):
        self.client = Client(settings.TWILIO_ACCOUNT_SID, settings.TWILIO_AUTH_TOKEN)
        self.twilio_number = settings.TWILIO_NUMBER

    async def make_call(self, to_number, twiml_url):
        # Wrap synchronous call in asyncio.to_thread
        return await asyncio.to_thread(self.client.calls.create, to=to_number, from_=self.twilio_number, url=twiml_url, method="POST")

    async def send_sms(self, to_number, message):
        # Wrap synchronous call in asyncio.to_thread
        return await asyncio.to_thread(self.client.messages.create, to=to_number, from_=self.twilio_number, body=message)

class SupabaseClient:
    def __init__(self, http_client: httpx.AsyncClient):
        self.client: SupabaseClientType = create_client(settings.SUPABASE_URL, settings.SUPABASE_KEY)
        self.bucket = settings.SUPABASE_BUCKET
        self.http_client = http_client  # Use the injected client

    async def insert(self, table_name, data):
        # Use asyncio.to_thread for synchronous Supabase operations
        result = await asyncio.to_thread(self.client.table(table_name).insert(data).execute)
        return result.data[0]  # Access data correctly

    async def update(self, table_name, data, key_column, key_value):
        result = await asyncio.to_thread(self.client.table(table_name).update(data).eq(key_column, key_value).execute)
        return result.data #Correct return

    async def get(self, table_name, key_column, key_value):
        result = await asyncio.to_thread(self.client.table(table_name).select("*").eq(key_column, key_value).execute)
        return result.data[0] if result.data else None
    async def get_all(self, table_name: str) -> list:
        """Retrieves all records from the specified table."""
        try:
            result = await asyncio.to_thread(self.client.table(table_name).select("*").execute)
            return result.data
        except Exception as e:
            logger.error(f"Error retrieving all records from table {table_name}: {e}")
            return []


    async def upload_file(self, data: bytes, filename: str) -> str:
        """Uploads a file to Supabase Storage and returns the public URL."""
        try:
            # Use the Supabase client's upload method (more robust)
            await asyncio.to_thread(self.client.storage.from_(self.bucket).upload, path=filename, file=data)
            public_url = self.client.storage.from_(self.bucket).get_public_url(filename)
            return public_url
        except Exception as e:
            logger.error(f"Supabase file upload error: {e}")
            raise  # Re-raise the exception to be handled upstream


class GroqClient:
    def __init__(self):
        self.client = Groq(api_key=settings.GROQ_API_KEY)
        self.model = settings.GROQ_MODEL

    async def generate_text_stream(self, messages, max_tokens=300):
        return self.client.chat.completions.create(messages=messages, model=self.model, stream=True, max_tokens=max_tokens)

class ElevenLabsClient:
    def __init__(self):
        self.api_key = settings.ELEVENLABS_API_KEY
        self.voice_id = settings.VOICE_ID
        self.model = settings.ELEVENLABS_MODEL
        self.base_url = settings.ELEVENLABS_API_BASE_URL

    async def stream_tts(self, text, http_client: httpx.AsyncClient):  # Inject httpx
        url = f"{self.base_url}/text-to-speech/{self.voice_id}/stream"
        headers = {
            "Accept": "audio/ulaw",
            "Content-Type": "application/json",
            "xi-api-key": self.api_key,
        }
        data = {
            "text": text,
            "model_id": self.model,
            "output_format": "ulaw_8000"
        }
        try:
            async with http_client.stream("POST", url, headers=headers, json=data) as response:
                response.raise_for_status()  # Raise HTTP errors
                async for chunk in response.aiter_bytes():
                    yield chunk
        except httpx.HTTPError as e:
            logger.error(f"ElevenLabs API error: {e}")
            raise  # Re-raise to handle upstream

class GoogleClient:
    def __init__(self):
        # Use the Vertex AI SDK for a cleaner approach

        credentials = service_account.Credentials.from_service_account_info(json.loads(settings.GOOGLE_API_KEY))
        aiplatform.init(project=credentials.project_id, credentials=credentials, location="us-central1") # Initialize client
        self.model = aiplatform.ChatModel.from_pretrained(settings.GOOGLE_MODEL)


    async def generate_text(self, messages, max_tokens=300):
        try:
            chat = self.model.start_chat(context=messages[0]['content']) #Correct
            parameters = {
                "max_output_tokens": max_tokens,
                "temperature": 0.7,
            }
            response = await chat.send_message_async(messages[-1]['content'], **parameters) # Send message
            return response.text
        except Exception as e:
            logger.error(f"Google API error: {e}")
            return ""