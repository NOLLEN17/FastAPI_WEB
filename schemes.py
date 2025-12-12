from pydantic import BaseModel, EmailStr, Field
from typing import Optional, List
from datetime import datetime,timedelta

class UserRegister(BaseModel):
    username: str = Field(..., min_length=3, max_length=50)
    password: str = Field(..., min_length=6, max_length=50)
    email: Optional[EmailStr] = None
    full_name: Optional[str] = None


class UserUpdate(BaseModel):
    email: Optional[EmailStr] = None
    full_name: Optional[str] = None
    password: Optional[str] = Field(None, min_length=6)


class BookCreate(BaseModel):
    title: str = Field(..., min_length=1, max_length=200)
    author: str = Field(..., min_length=1, max_length=100)
    year: Optional[int] = Field(None, ge=1000, le=2100)
    description: Optional[str] = None


class BookResponse(BaseModel):
    id: int
    title: str
    author: str
    year: Optional[int]
    description: Optional[str]
    created_at: datetime

    class Config:
        from_attributes = True


class UserResponse(BaseModel):
    id: int
    username: str
    email: Optional[str]
    full_name: Optional[str]
    created_at: datetime

    class Config:
        from_attributes = True


class UserProfileResponse(UserResponse):
    books_count: int
    books: List[BookResponse]


class TokenResponse(BaseModel):
    access_token: str
    token_type: str


