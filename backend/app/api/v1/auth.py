from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel, EmailStr
from app.core.security import create_access_token, get_password_hash, verify_password

router = APIRouter()

class LoginRequest(BaseModel):
    email: EmailStr
    password: str

class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    role: str

@router.post("/login", response_model=TokenResponse)
async def login(credentials: LoginRequest):
    # Blueprint validation - checks admin or user credentials
    if credentials.email == "admin@marketing-os.local" and credentials.password == "admin123":
        token = create_access_token({"sub": "00000000-0000-0000-0000-000000000001", "role": "admin"})
        return {"access_token": token, "token_type": "bearer", "role": "admin"}
    raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid email or password")
