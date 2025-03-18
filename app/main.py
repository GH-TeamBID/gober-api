from fastapi import FastAPI, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import RedirectResponse, JSONResponse
from fastapi.exceptions import RequestValidationError
import uvicorn
import time
import logging
from typing import Callable
import traceback

from app.core.config import settings
from app.core.init_search import init_meilisearch
from app.modules.auth.routes import router as auth_router
from app.modules.clients.routes import router as clients_router
from app.modules.tenders.routes import router as tenders_router
from app.modules.ai_tools.routes import router as ai_router
# from app.modules.external_integration.routes import router as external_router

# Configure logging
logging.basicConfig(
    level=getattr(logging, settings.LOG_LEVEL),
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)

# Create FastAPI app
app = FastAPI(
    title=settings.APP_NAME,
    description="Gober AI API",
    version=settings.VERSION,
    debug=settings.DEBUG
)

# Startup event handlers
@app.on_event("startup")
async def startup_event():
    """Initialize services when the application starts"""
    logger.info("Application startup: Initializing services...")
    
    # Initialize Meilisearch
    try:
        meilisearch_initialized = await init_meilisearch()
        if meilisearch_initialized:
            logger.info("Meilisearch successfully initialized")
        else:
            logger.warning("Meilisearch initialization failed")
    except Exception as e:
        logger.error(f"Error initializing Meilisearch: {str(e)}")
        # Continue startup even if Meilisearch fails

# Middleware for request logging
@app.middleware("http")
async def log_requests(request: Request, call_next: Callable):
    start_time = time.time()
    
    # Process the request
    try:
        response = await call_next(request)
        process_time = time.time() - start_time
        
        # Log request details
        logger.info(
            f"Request: {request.method} {request.url.path} "
            f"Status: {response.status_code} "
            f"Duration: {process_time:.4f}s"
        )
        
        # Add custom header with processing time
        response.headers["X-Process-Time"] = str(process_time)
        return response
    except Exception as e:
        # Log the exception
        process_time = time.time() - start_time
        logger.error(
            f"Request: {request.method} {request.url.path} "
            f"Error: {str(e)} "
            f"Duration: {process_time:.4f}s"
        )
        
        # Return error response
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={"detail": "Internal server error"}
        )

# Global exception handler for validation errors
@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    # Log the validation error
    logger.warning(f"Validation error: {str(exc)}")
    
    # Return a more user-friendly error response
    return JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        content={
            "detail": "Validation error",
            "errors": exc.errors()
        }
    )

# Global exception handler for unexpected errors
@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    # Log the exception with traceback
    logger.error(f"Unexpected error: {str(exc)}")
    logger.error(traceback.format_exc())
    
    # Return a generic error response in production
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={
            "detail": "An unexpected error occurred" if not settings.DEBUG else str(exc)
        }
    )

# Configure CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Mount static files
app.mount("/static", StaticFiles(directory="app/static"), name="static")

# Include routers with API prefix
api_prefix = settings.API_PREFIX
app.include_router(auth_router, prefix=f"{api_prefix}/auth", tags=["Autenticación"])
app.include_router(clients_router, prefix=f"{api_prefix}/clients", tags=["Clientes"])
app.include_router(tenders_router, prefix=f"{api_prefix}/tenders", tags=["Licitaciones"])
app.include_router(ai_router, prefix=f"{api_prefix}/ai-tools", tags=["IA Tools"])
# app.include_router(external_router, prefix=f"{api_prefix}/external", tags=["Integración Externa"])

@app.get("/")
async def root():
    return RedirectResponse(url="/static/index.html")

@app.get("/api")
async def api_info():
    return {
        "app_name": settings.APP_NAME,
        "version": settings.VERSION,
        "message": "Welcome to the API"
    }

@app.get("/health")
async def health_check():
    """Health check endpoint for monitoring"""
    return {"status": "healthy"}

if __name__ == "__main__":
    uvicorn.run("app.main:app", host="0.0.0.0", port=8000, reload=True)