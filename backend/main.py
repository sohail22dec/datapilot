import logging
from contextlib import asynccontextmanager
import uvicorn
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.endpoints import router as api_router
from app.database import warm_database_pool
from app.tools.schema_tool import get_schema_context

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Pre-warms Supabase connection pool and pre-caches minified schema on boot."""
    logger.info("Initializing DataPilot backend services...")
    warm_database_pool()
    get_schema_context()
    logger.info("Supabase pool pre-warmed & schema pre-cached in memory.")
    yield


app = FastAPI(
    title="DataPilot Backend API",
    description="FastAPI service with High-Speed Agentic Business Intelligence & Supabase Database Skills",
    version="0.1.0",
    lifespan=lifespan,
)

origins = [
    "http://localhost:3000",
    "https://datapilot.duckdns.org",
    "http://datapilot.duckdns.org",
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Mount API router
app.include_router(api_router)


if __name__ == "__main__":
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
