# app/modules/auth/routes.py

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from app.modules.auth import schemas, services
from app.core.database import get_db

router = APIRouter()

@router.get("/")
async def auth_root():
    return {"message": "Auth module is working"}


@router.post("/login", response_model=schemas.LoginResponse)
def login(login_req: schemas.LoginRequest, db: Session = Depends(get_db)):
    user = services.authenticate_user(db, login_req.username, login_req.password)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid credentials in login",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    access_token = services.create_access_token({"sub": user.username})
    return schemas.LoginResponse(access_token=access_token)