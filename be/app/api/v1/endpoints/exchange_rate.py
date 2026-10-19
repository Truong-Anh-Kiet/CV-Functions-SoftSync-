from fastapi import APIRouter

from app.services.exchange_rate import get_usd_vnd_rate


router = APIRouter()


@router.get("/usd-vnd")
async def get_usd_vnd_exchange_rate() -> dict:
    rate = await get_usd_vnd_rate()
    return {
        "status": "success",
        "data": {
            "rate": rate,
        },
    }
