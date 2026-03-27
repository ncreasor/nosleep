from fastapi import APIRouter, HTTPException
import httpx
from config import settings

router = APIRouter(prefix="/qdrant", tags=["qdrant"])


@router.get("/ping")
async def qdrant_ping():
    try:
        headers = {}
        if settings.qdrant_service_api_key:
            headers["api-key"] = settings.qdrant_service_api_key

        url = f"{settings.qdrant_url}/health"
        async with httpx.AsyncClient(timeout=5.0) as client:
            response = await client.get(url, headers=headers)
            if response.status_code == 200:
                try:
                    return {
                        "status": "ok",
                        "qdrant_status": response.json(),
                    }
                except:
                    return {
                        "status": "ok",
                        "response": response.text,
                    }
            else:
                return {
                    "status": "ok",
                    "code": response.status_code,
                    "response": response.text,
                }
    except Exception as e:
        import traceback
        print(f"Qdrant error: {e}")
        print(traceback.format_exc())
        raise HTTPException(status_code=503, detail=str(e))
