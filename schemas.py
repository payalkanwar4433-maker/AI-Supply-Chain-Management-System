
from pydantic import BaseModel, EmailStr, Field


class UserRegister(BaseModel):
    full_name: str
    email: EmailStr
    password: str = Field(min_length=8)


class UserResponse(BaseModel):
    id: int
    full_name: str
    email: EmailStr
    role_name: str


class UserLogin(BaseModel):
    email: EmailStr
    password: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: str
    user: UserResponse
