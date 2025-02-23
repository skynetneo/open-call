# app/ai.py
import asyncio
import io
import base64
import uuid
from fastapi import WebSocket
from app.clients import ElevenLabsClient, GroqClient, SupabaseClient
from app.utils import split_into_sentences
from app.redis_manager import RedisManager
from app.logger import logger  # Consistent logging

async def generate_text_stream(user_message: str, groq_client: GroqClient, elevenlabs_client: ElevenLabsClient,
                              supabase_client: SupabaseClient, websocket: WebSocket, stream_sid: str,
                              transcription_id: int, redis_client: RedisManager, human_in_loop: bool):
    """Generates text using Groq, streams to ElevenLabs, handles DB."""
    try:
        system_prompt = await redis_client.hget(f"call_state:{stream_sid}", "system_prompt")
        if system_prompt is None:
            raise ValueError(f"system_prompt not found in Redis for stream: {stream_sid}")

        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_message},
        ]
        full_response_text = ""  # Accumulate the full response
        async for chunk in await groq_client.generate_text_stream(messages):
            if chunk.choices and chunk.choices[0].delta and chunk.choices[0].delta.content:
                text_chunk = chunk.choices[0].delta.content
                full_response_text += text_chunk  # Add to the full response

                if human_in_loop:
                    await websocket.send_json({
                        "event": "partial_response",
                        "text": full_response_text,  # Send accumulated text
                        "stream_sid": stream_sid
                    })

                    # Wait for approval or modification
                    try:
                        response = await asyncio.wait_for(websocket.receive_json(), timeout=60)  # Adjust timeout as needed
                        if response.get("event") == "override":
                            full_response_text = response.get("text")  # Use the overridden text
                            # Reset to send the FULL overridden text as a single sentence.
                            await process_text_chunk(full_response_text, elevenlabs_client, supabase_client, websocket, stream_sid, transcription_id, redis_client, is_override=True)
                            return  # Exit after processing the override

                    except asyncio.TimeoutError:
                        logger.warning("Human-in-the-loop response timed out. Continuing with generated text.")
                        #Proceed
                    except Exception as e:
                        logger.error(f"Error getting human in the loop response {e}")
                        #Proceed

                await process_text_chunk(text_chunk, elevenlabs_client, supabase_client, websocket, stream_sid, transcription_id, redis_client)

    except Exception as e:
        logger.error(f"AI generation error for stream {stream_sid}: {e}")
        await websocket.send_json({"event": "error", "message": "AI generation error."})
        await websocket.close(code=1011) #Close


async def process_text_chunk(text_chunk: str, elevenlabs_client: ElevenLabsClient,
                             supabase_client: SupabaseClient, websocket: WebSocket,
                             stream_sid: str, transcription_id: int, redis_client: RedisManager, is_override: bool = False):
    """Processes a chunk of text, splitting into sentences, and streaming."""
    #If Override, send all at once, not just chunks
    if is_override:
        sentences = {"complete": [text_chunk], "remainder": ""}
    else:
        sentences = split_into_sentences(text_chunk)

    for sentence in sentences["complete"] + ([sentences["remainder"].strip()] if sentences["remainder"].strip() else []):
        logger.info(f"Sending to TTS: {sentence}")
        try:
            await stream_to_elevenlabs_and_db(sentence, elevenlabs_client, supabase_client, websocket, stream_sid, transcription_id, redis_client)
        except Exception as e:
            logger.error(f"Error in process_text_chunk: {e}")  # Log the specific error
            await websocket.send_json({"event": "error", "message": "Error processing text chunk."}) # Notify User
            await websocket.close(code=1011) # Close connection
            return  # Important: Stop processing if TTS fails

async def stream_to_elevenlabs_and_db(text: str, elevenlabs_client: ElevenLabsClient,
                                     supabase_client: SupabaseClient, websocket: WebSocket,
                                     stream_sid: str, transcription_id: int, redis_client: RedisManager):
    """Streams TTS, sends to client, saves to Supabase."""
    try:
        # Get the http_client from the app's lifespan (passed as a dependency to the route)
        audio_stream = await elevenlabs_client.stream_tts(text, http_client=websocket.app.state.http_client)  # Access http_client correctly
        audio_data = io.BytesIO()
        async for chunk in audio_stream:
            audio_data.write(chunk)
            encoded_chunk = base64.b64encode(chunk).decode("utf-8")
            await websocket.send_json({
                "event": "media",
                "streamSid": stream_sid,
                "media": {"payload": encoded_chunk},
            })

        audio_data.seek(0)  # Rewind for Supabase upload
        unique_filename = f"generated_audio_{stream_sid}_{transcription_id}_{uuid.uuid4()}.ulaw"
        audio_url = await supabase_client.upload_file(audio_data.read(), unique_filename)

        # Insert into Supabase *and* send transcription event *within* this function
        await supabase_client.insert("generated_texts", {
            "transcription_id": transcription_id,
            "text": text,
            "audio_path": audio_url
        })
        # Send after successful TTS *and* Supabase upload
        await websocket.send_json({
            "event": "transcription",
            "stream_sid": stream_sid,
            "text": text,
            "role": "ai"
        })

    except Exception as e:
        logger.error(f"ElevenLabs/Supabase error for stream {stream_sid}: {e}")
        await websocket.send_json({"event": "error", "message": "ElevenLabs/Supabase error."})
        await websocket.close(code=1011)  # Internal error.  Close the connection.