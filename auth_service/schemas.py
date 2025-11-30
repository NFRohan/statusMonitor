from pydantic import BaseModel
from datetime import datetime
from typing import Optional

class UserBase(BaseModel):
    username: str

class UserCreate(UserBase):
    password: str

class User(UserBase):
    id: int

    class Config:
        from_attributes = True

class Token(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str

class TokenData(BaseModel):
    username: str | None = None

# Agent schemas
class AgentCreate(BaseModel):
    name: str

class AgentResponse(BaseModel):
    id: int
    name: str
    token: str
    created_at: datetime
    last_seen: Optional[datetime] = None
    is_active: bool

    class Config:
        from_attributes = True

class AgentListResponse(BaseModel):
    id: int
    name: str
    created_at: datetime
    last_seen: Optional[datetime] = None
    is_active: bool

    class Config:
        from_attributes = True

class AgentTokenValidation(BaseModel):
    valid: bool
    agent_id: Optional[int] = None
    user_id: Optional[int] = None
    agent_name: Optional[str] = None
