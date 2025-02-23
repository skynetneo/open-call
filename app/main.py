# app/main.py
import httpx
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.templating import Jinja2Templates
from app.config import settings
from app.routes import router
from app.redis_manager import RedisManager
from app.dep import get_http_client  # Import dependency functions
from app.logger import logger
# Initialize Logging
logger = logger.getLogger(__name__)

# Load templates
templates = Jinja2Templates(directory="app/templates")

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Handles startup and shutdown events."""
    # Startup logic
    await RedisManager.initialize()
    http_client = httpx.AsyncClient(timeout=httpx.Timeout(10.0))  # Create http_client
    app.state.http_client = http_client  # Store in app.state
    logger.info("Application startup complete.")

    yield  # This is where the application runs

    # Shutdown logic
    await RedisManager.close()
    await app.state.http_client.aclose()  # Close http_client
    logger.info("Application shutdown complete.")

app = FastAPI(lifespan=lifespan)  # Create FastAPI instance *once* with lifespan
app.include_router(router)  # Add routes

# Add a general exception handler
@app.exception_handler(Exception)
async def general_exception_handler(request, exc):
    logger.exception(f"Unhandled exception: {exc}")  # Log the exception
    return templates.TemplateResponse("error.html", {"request": request, "error_message": "An unexpected error occurred."})