from fastapi import APIRouter, HTTPException
from qdrant_client import QdrantClient
from config import settings

router = APIRouter(prefix="/qdrant", tags=["qdrant"])


@router.get("/ping")
async def qdrant_ping():
    try:
        client = QdrantClient(url=settings.qdrant_url, api_key=settings.qdrant_service_api_key)
        collections = client.get_collections()
        return {
            "status": "ok",
            "collections": [c.name for c in collections.collections],
        }
    except Exception as e:
        raise HTTPException(status_code=503, detail=str(e))
