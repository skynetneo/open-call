# Open-Call

## Agentic Calling and SMS with Twilio, Groq, and Gemini

Open-Call is a minimal viable product (MVP) that enables AI-driven voice calls and SMS messaging using FastAPI, Uvicorn, Twilio, Gemini 2.5 Flash Lite Preview for instant text generation during calls, and Gemini 2.5 Pro Exp for SMS responses. This project provides a REST API for handling AI-enhanced communications.

## Features
- AI-generated responses for voice calls (Gemini 2.5 Flash Lite Preview)
- AI-driven SMS responses (Gemini 2.5 Pro Exp)
- FastAPI backend for handling API requests
- Uvicorn for ASGI server deployment
- Twilio integration for SMS and voice call routing
- HTML-based frontend (planned Tauri GUI integration)
- Dockerized environment for simplified deployment

## Installation
### Clone Repository
```sh
git clone https://github.com/skynetneo/open-call.git
cd open-call
```

### Docker Setup
Ensure you have Docker installed and running, then build and start the container:
```sh
docker-compose up --build
```
This will automatically pull dependencies and start the FastAPI server.

## Configuration
Create a `.env` file in the project root and add your Twilio credentials and API keys:
```
TWILIO_ACCOUNT_SID=your_twilio_sid
TWILIO_AUTH_TOKEN=your_twilio_auth_token
TWILIO_PHONE_NUMBER=your_twilio_phone_number
GROQ_API_KEY=your_groq_api_key
GEMINI_API_KEY=your_gemini_api_key
```

## Usage
### Running Locally (Without Docker)
You can start the FastAPI server manually:
```sh
pip install -r requirements.txt
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```

### API Endpoints
- `POST /call` – Handles incoming calls and generates AI-powered responses
- `POST /sms` – Processes incoming SMS messages and replies using Gemini 2.0 Pro Exp
- `GET /docs` – Access interactive API documentation (Swagger UI)

## Future Improvements
- **Tauri GUI Integration:** Replace the current HTML frontend with a cross-platform desktop application
- **Enhanced AI Pipelines:** Optimize response times and improve contextual understanding
- **Multi-Agent Coordination:** Allow dynamic switching between models based on context
- **Expanded Carrier Support:** Add support for more telephony providers beyond Twilio

## Contributing
Feel free to open issues or submit pull requests to improve Open-Call!

## License
This project is licensed under the MIT License.

---

**Author:** SkynetNeo

