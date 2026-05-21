from typing import Any

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, EmailStr
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from engine.auth.jwt import create_access_token, get_password_hash, verify_password
from engine.auth.models import Tenant, User
from engine.database.connection import get_db_session

router = APIRouter(prefix="/v1/auth", tags=["auth"])


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class RegisterRequest(BaseModel):
    email: EmailStr
    password: str
    tenant_name: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"


@router.post("/register", response_model=TokenResponse)
async def register(
    req: RegisterRequest, db: AsyncSession = Depends(get_db_session)
) -> Any:
    # Check if user exists
    res = await db.execute(select(User).where(User.email == req.email))
    if res.scalar_one_or_none():
        raise HTTPException(status_code=400, detail="Email already registered")

    # Create new tenant
    tenant = Tenant(name=req.tenant_name)
    db.add(tenant)
    await db.flush()

    # Create user
    user = User(
        email=req.email,
        hashed_password=get_password_hash(req.password),
        tenant_id=tenant.id,
    )
    db.add(user)
    await db.commit()

    # Create token
    access_token = create_access_token(data={"sub": user.email, "tenant_id": tenant.id})
    return {"access_token": access_token}


@router.post("/login", response_model=TokenResponse)
async def login(
    req: LoginRequest, db: AsyncSession = Depends(get_db_session)
) -> Any:
    res = await db.execute(select(User).where(User.email == req.email))
    user = res.scalar_one_or_none()

    if not user or not verify_password(req.password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password",
            headers={"WWW-Authenticate": "Bearer"},
        )

    if not user.is_active:
        raise HTTPException(status_code=400, detail="Inactive user")

    access_token = create_access_token(data={"sub": user.email, "tenant_id": user.tenant_id})
    return {"access_token": access_token}
