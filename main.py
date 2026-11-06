"""
Root entry point forwarding directly to the modernized enterprise application in app.main.
Provides 100% backward compatibility for existing startup scripts (e.g. `uvicorn main:app`).
"""
import uvicorn
from app.main import app
from app.core.config import settings

if __name__ == "__main__":
    print(f"Starting {settings.CLINIC_NAME} (FastAPI Server)...")
    uvicorn.run("app.main:app", host=settings.HOST, port=settings.PORT, reload=settings.DEBUG)
