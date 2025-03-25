from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import uvicorn

from app.core.config import settings
from app.modules.auth.routes import router as auth_router
from app.modules.clients.routes import router as clients_router
from app.modules.tenders.routes import router as tenders_router
from app.modules.ai_tools.routes import router as ai_router
from app.modules.search.routes import router as search_router
# from app.modules.external_integration.routes import router as external_router

app = FastAPI(
    title=settings.APP_NAME,
    description="Gober AI API",
    version=settings.VERSION,
    debug=settings.DEBUG
)

# Configure CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers with API prefix
api_prefix = settings.API_PREFIX
app.include_router(auth_router, prefix=f"{api_prefix}/auth", tags=["Autenticación"])
app.include_router(clients_router, prefix=f"{api_prefix}/clients", tags=["Clientes"])
app.include_router(tenders_router, prefix=f"{api_prefix}/tenders", tags=["Licitaciones"])
app.include_router(ai_router, prefix=f"{api_prefix}/ai-tools", tags=["IA Tools"])
app.include_router(search_router, prefix=f"{api_prefix}/search", tags=["Search"])
# app.include_router(external_router, prefix=f"{api_prefix}/external", tags=["Integración Externa"])

@app.get("/")
async def root():
    return {
        "app_name": settings.APP_NAME,
        "version": settings.VERSION,
        "message": "Welcome to the API"
    }

if __name__ == "__main__":
    uvicorn.run("app.main:app", host="0.0.0.0", port=8000, reload=True)