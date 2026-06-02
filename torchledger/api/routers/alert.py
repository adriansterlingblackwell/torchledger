"""Alert / webhook router — /v1/alert"""
from fastapi import APIRouter
router = APIRouter()

@router.post("/webhook")
async def register_webhook(url: str, threshold: int = 50) -> dict:
    return {"registered": True, "url": url, "threshold": threshold}
