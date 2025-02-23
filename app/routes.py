# app/routes.py
import logging
import json
import asyncio
from fastapi import APIRouter, Request, Form, WebSocket, Depends, HTTPException, WebSocketDisconnect
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from twilio.twiml.voice_response import VoiceResponse, Connect, Stream
from app.config import settings
from app.clients import TwilioClient, SupabaseClient, GroqClient, ElevenLabsClient, GoogleClient
from app.ai import generate_text_stream
from app.redis_manager import RedisManager
from app.dep import get_twilio_client, get_supabase_client, get_groq_client, get_elevenlabs_client, get_redis_client, get_google_client #get_http_client removed
from app.transcription import transcribe_audio_streaming
from app.utils import split_into_sentences
from app.logger import logger
import uuid
from datetime import datetime
import base64
from app.prompts import DEFAULT_SYSTEM_PROMPT, SMS_SYSTEM_PROMPT


router = APIRouter()
templates = Jinja2Templates(directory="app/templates")

@router.get("/", response_class=HTMLResponse)
async def index(request: Request):
    """Serves the main HTML page."""
    return templates.TemplateResponse("index.html", {
        "request": request,
        "default_system_prompt": DEFAULT_SYSTEM_PROMPT,
        "groq_model": settings.GROQ_MODEL,
        "elevenlabs_voice_id": settings.VOICE_ID,
        "elevenlabs_model": settings.ELEVENLABS_MODEL
    })

@router.get("/history", response_class=HTMLResponse)
async def call_history(request: Request, supabase_client: SupabaseClient = Depends(get_supabase_client)):
    """Displays a basic call and SMS history."""
    try:
        calls = await supabase_client.get_all("calls")
        sms_messages = await supabase_client.get_all("sms_messages")

        # Sort by creation time (newest first) - assuming you have a 'created_at' column
        calls.sort(key=lambda x: x.get('created_at', datetime.min), reverse=True)
        sms_messages.sort(key=lambda x: x.get('created_at', datetime.min), reverse=True)


        return templates.TemplateResponse("history.html", {
            "request": request,
            "calls": calls,
            "sms_messages": sms_messages
        })
    except Exception as e:
        logger.error(f"Error retrieving history: {e}")
        return templates.TemplateResponse("error.html", {"request": request, "error_message": "Could not retrieve history."})

@router.post("/make-call")
async def make_call(
    request: Request,
    phone_number: str = Form(...),
    system_prompt: str = Form(...),
    instructions: str = Form(...),
    context: str = Form(...),
    twilio_client: TwilioClient = Depends(get_twilio_client),
    supabase_client: SupabaseClient = Depends(get_supabase_client),
    redis_client: RedisManager = Depends(get_redis_client)
):
    """Handles outbound call initiation."""
    try:
        twiml_url = f"https://{request.headers['host']}/twiml"
        call = await twilio_client.make_call(phone_number, twiml_url)  # Now asynchronous

        # Insert call details into Supabase *before* storing in Redis
        inserted_call = await supabase_client.insert("calls", {
            "twilio_sid": call.sid,
            "from_number": settings.TWILIO_NUMBER,
            "to_number": phone_number,
            "status": "initiated",
            "system_prompt": system_prompt,
            "instructions": instructions,
            "context": context
        })
        call_db_id = inserted_call['id']

        # Store persistent state in Redis (using call.sid as the key)
        await redis_client.hset(f"call_state:{call.sid}", mapping={
            "call_db_id": str(call_db_id),  # Store as string
            "system_prompt": system_prompt,
            "instructions": instructions,
            "context": context,
            "human_in_loop": "false",  # Initialize human-in-loop flag
        })
        await redis_client.expire(f"call_state:{call.sid}", 86400) # Expire

        return templates.TemplateResponse("call_initiated.html", {"request": request, "call_sid": call.sid})

    except Exception as e:
        logger.error(f"Error making call: {e}")
        return templates.TemplateResponse("error.html", {"request": request, "error_message": str(e)})

@router.post("/send-sms")
async def send_sms(
    request: Request,
    phone_number: str = Form(...),
    message: str = Form(...),
    twilio_client: TwilioClient = Depends(get_twilio_client),
    supabase_client: SupabaseClient = Depends(get_supabase_client)
):
    """Handles sending SMS messages."""
    try:
        twilio_message = await twilio_client.send_sms(phone_number, message) # Now asynchronous
        await supabase_client.insert("sms_messages", {
            "twilio_sid": twilio_message.sid,
            "from_number": settings.TWILIO_NUMBER,
            "to_number": phone_number,
            "body": message,
            "direction": "outbound"
        })
        return templates.TemplateResponse("sms_sent.html", {"request": request, "message_sid": twilio_message.sid})

    except Exception as e:
        logger.error(f"Error sending SMS: {e}")
        return templates.TemplateResponse("error.html", {"request": request, "error_message": str(e)})

@router.api_route("/incoming-sms", methods=["GET", "POST"])
async def incoming_sms(
    request: Request,
    twilio_client: TwilioClient = Depends(get_twilio_client),
    supabase_client: SupabaseClient = Depends(get_supabase_client),
    google_client: GoogleClient = Depends(get_google_client)
):
    """Handles incoming SMS messages."""
    form_data = await request.form()
    from_number = form_data.get("From")
    to_number = form_data.get("To")
    message_body = form_data.get("Body")
    twilio_sid = form_data.get("MessageSid")
    logger.info(f"Received SMS from {from_number}: {message_body}")

    # Store incoming SMS in Supabase
    await supabase_client.insert("sms_messages", {
        "twilio_sid": twilio_sid,
        "from_number": from_number,
        "to_number": to_number,
        "body": message_body,
        "direction": "inbound"
    })

    try:
        # Generate AI response using the GoogleClient
        messages = [
            {"role": "system", "content": SMS_SYSTEM_PROMPT},  # Use the correct prompt
            {"role": "user", "content": message_body},
        ]
        ai_response = await google_client.generate_text(messages=messages)
        await supabase_client.update("sms_messages", {"response_text": ai_response}, "twilio_sid", twilio_sid)
        await twilio_client.send_sms(from_number, ai_response)  # Use the async TwilioClient
        logger.info(f"Sent SMS reply to {from_number}: {ai_response}")
        return JSONResponse({"status": "Reply sent"})
    except Exception as e:
        logger.error(f"Error handling incoming SMS: {e}")
        return JSONResponse({"status": "Error"}, status_code=500)

@router.api_route("/twiml", methods=["GET", "POST"])
async def twiml(request: Request):
    """Returns TwiML to connect the call to the WebSocket stream."""
    response = VoiceResponse()
    response.say("Connecting you to our AI assistant. Please wait.")
    connect = Connect()
    connect.stream(url=f"wss://{request.headers['host']}/media-stream")
    response.append(connect)
    return HTMLResponse(str(response), media_type="application/xml")

@router.websocket("/media-stream")
async def media_stream(
    websocket: WebSocket,
    redis_client: RedisManager = Depends(get_redis_client),
    supabase_client: SupabaseClient = Depends(get_supabase_client),
    groq_client: GroqClient = Depends(get_groq_client),
    elevenlabs_client: ElevenLabsClient = Depends(get_elevenlabs_client)
):
    """Handles the bi-directional media stream with Twilio."""
    await websocket.accept()
    logger.info("Twilio connected to media stream.")

    stream_sid = None
    call_state = {}  # Local state for *this* WebSocket connection
    active_tasks = {} # Local in-memory storage for active tasks

    try:
        async for message in websocket.iter_text():
            data = json.loads(message)
            event_type = data.get("event")

            if event_type == "start":
                stream_sid = data["start"]["streamSid"]
                logger.info(f"Stream started: {stream_sid}")

                # Retrieve ALL persistent call state from Redis
                persistent_state = await redis_client.hgetall(f"call_state:{stream_sid}")
                if not persistent_state:
                    logger.error(f"Call state for stream {stream_sid} not found in Redis.")
                    await websocket.close(code=4000) #Close
                    return

                call_state[stream_sid] = {
                    "transcription_buffer": b"",
                    "system_prompt": persistent_state["system_prompt"],
                    "human_in_loop": persistent_state.get("human_in_loop", "false") == "true", # Get human_in_loop
                }
                active_tasks[stream_sid] = { "active_generation_task": None }

            elif event_type == "media":
                audio_payload = data["media"]["payload"]
                current_state = call_state.get(stream_sid)

                if not current_state:
                    logger.warning(f"No active call state found for stream {stream_sid}")
                    continue

                # 1. Transcribe
                transcription_text = await transcribe_audio_streaming(audio_payload, websocket.app.state.http_client)  # Use http_client from app.state
                if transcription_text and transcription_text != "[ERROR]":
                    logger.info(f"Transcription: {transcription_text}")

                    # Get Call ID
                    call_db_id_str = persistent_state.get("call_db_id")
                    if not call_db_id_str:
                        logger.error(f"call_db_id not found in Redis for stream {stream_sid}")
                        continue #Skip
                    call_db_id = int(call_db_id_str)

                     # --- Store transcription in Supabase ---
                    raw_audio_data = base64.b64decode(audio_payload)
                    raw_audio_url = await supabase_client.upload_file(raw_audio_data, f"raw_audio_{stream_sid}_{uuid.uuid4()}.ulaw")
                    transcription = await supabase_client.insert("transcriptions", {
                        "call_id": call_db_id,
                        "text": transcription_text,
                        "raw_audio_path": raw_audio_url
                    })
                    transcription_id = transcription['id']

                    # Construct user prompt using retrieved system prompt and other context.
                    user_prompt = DEFAULT_SYSTEM_PROMPT.format(
                        INSTRUCTIONS=persistent_state.get("instructions", ""),
                        CONTEXT=persistent_state.get("context", ""),
                        USER_MESSAGE=transcription_text
                    )

                    # 2. Generate and stream (with human-in-loop handling)
                    if active_tasks[stream_sid]["active_generation_task"]:
                        active_tasks[stream_sid]["active_generation_task"].cancel()  # Cancel any previous task

                    human_in_loop = call_state[stream_sid]["human_in_loop"]
                    active_tasks[stream_sid]["active_generation_task"] = asyncio.create_task(
                        generate_text_stream(user_prompt, groq_client, elevenlabs_client,
                                            supabase_client, websocket, stream_sid,
                                            transcription_id, redis_client, human_in_loop)
                    )

            elif event_type == "stop":
                logger.info(f"Stream stopped: {stream_sid}")
                current_state = call_state.get(stream_sid) #Get state
                if current_state:
                    call_db_id_str = persistent_state.get("call_db_id")
                    if not call_db_id_str:
                        logger.error(f"call_db_id not found in Redis for stream {stream_sid}")
                    else:
						#Update call
                        call_db_id = int(call_db_id_str)
                        now = datetime.utcnow().isoformat()
                        await supabase_client.update("calls", {"status": "completed", "end_time": now}, "id", call_db_id)
                break

            elif event_type == "toggle_human_in_loop":
                # Toggle the human-in-the-loop flag
                if stream_sid in call_state:
                    call_state[stream_sid]["human_in_loop"] = not call_state[stream_sid]["human_in_loop"]
                    await redis_client.hset(f"call_state:{stream_sid}", {"human_in_loop": str(call_state[stream_sid]["human_in_loop"]).lower()})
                    logger.info(f"Human-in-the-loop toggled to: {call_state[stream_sid]['human_in_loop']} for stream {stream_sid}")
                else:
                    logger.warning(f"Could not toggle human-in-the-loop. No active state for stream {stream_sid}")

    except WebSocketDisconnect:
        logger.info(f"Twilio disconnected for stream: {stream_sid}")
    except Exception as e:
        logger.exception(f"Unexpected error in media stream: {e}")
        await websocket.send_json({"event": "error", "message": "An unexpected error occurred in the media stream."}) # Notify User

    finally:
        if stream_sid in active_tasks:
            if active_tasks[stream_sid]["active_generation_task"]:
                active_tasks[stream_sid]["active_generation_task"].cancel()
            del active_tasks[stream_sid]  # Clean up

        if stream_sid in call_state:
            del call_state[stream_sid]  # Clean up

        await websocket.close()

# New route to toggle human-in-the-loop (accessed via HTTP, not WebSocket)
@router.post("/toggle-human-in-loop/{call_sid}")
async def toggle_human_in_loop_http(call_sid: str, redis_client: RedisManager = Depends(get_redis_client)):
    """Toggles human-in-the-loop via an HTTP request."""
    try:
        call_state = await redis_client.hgetall(f"call_state:{call_sid}")
        if not call_state:
            raise HTTPException(status_code=404, detail="Call not found")

        current_state = call_state.get("human_in_loop", "false") == "true"
        new_state = not current_state
        await redis_client.hset(f"call_state:{call_sid}", {"human_in_loop": str(new_state).lower()})
        return {"call_sid": call_sid, "human_in_loop": new_state}
    except Exception as e:
        logger.error(f"Error toggling human-in-loop for {call_sid}: {e}")
        raise HTTPException(status_code=500, detail="Error toggling human-in-the-loop")