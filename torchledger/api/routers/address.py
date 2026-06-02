"""Address router — /v1/address"""
from fastapi import APIRouter
router = APIRouter()

@router.get("/{address}")
async def get_address(address: str) -> dict:
    return {"address": address, "status": "indexed"}
