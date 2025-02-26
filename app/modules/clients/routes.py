from fastapi import APIRouter

router = APIRouter()

@router.get("/")
async def clients_root():
    return {"message": "Clients module is working"}
