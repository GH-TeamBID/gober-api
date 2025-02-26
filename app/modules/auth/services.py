# app/modules/auth/services.py

from sqlalchemy.orm import Session
from app.modules.auth import models
from passlib.context import CryptContext
import jwt
import datetime
from app.core.config import settings

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """
    Verifica si la contraseña ingresada coincide con la contraseña hasheada almacenada.
    """
    return pwd_context.verify(plain_password, hashed_password)

def authenticate_user(db: Session, username: str, password: str):
    """
    Autentica un usuario en la base de datos.
    """
    user = db.query(models.User).filter(models.User.username == username).first()
    if not user:
        return None
    if not verify_password(password, user.hashed_password):
        return None
    return user

def create_access_token(data: dict, expires_delta: int = None):
    to_encode = data.copy()
    
    if expires_delta is None:
        expires_delta = settings.ACCESS_TOKEN_EXPIRE_MINUTES
        
    expire = datetime.datetime.now(datetime.UTC) + datetime.timedelta(minutes=expires_delta)
    to_encode.update({"exp": expire})
    
    token = jwt.encode(to_encode, settings.SECRET_KEY, algorithm=settings.ALGORITHM)
    return token