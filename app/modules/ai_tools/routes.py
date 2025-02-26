from fastapi import APIRouter

router = APIRouter()

@router.get("/")
async def ai_tools_root():
    return {"message": "AI Tools module is working"}
