from fastapi import APIRouter

router = APIRouter()

@router.get("/")
async def tenders_root():
    return {"message": "Tenders module is working"}
