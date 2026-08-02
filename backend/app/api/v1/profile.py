"""Profile API routes."""
from __future__ import annotations
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.api.v1.deps import get_current_user
from app.db.session import get_db
from app.models.user import User
from app.schemas.auth import UserOut

router = APIRouter(prefix="/profile", tags=["Profile"])


class ProfileUpdate(BaseModel):
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    company: Optional[str] = None
    creator_category: Optional[str] = None
    preferred_platform: Optional[str] = None
    notify_email: Optional[bool] = None
    avatar_url: Optional[str] = None


@router.get("", response_model=UserOut)
async def get_profile(current_user: User = Depends(get_current_user)):
    return UserOut.model_validate(current_user)


@router.patch("", response_model=UserOut)
async def update_profile(
    update: ProfileUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    if update.first_name is not None:
        current_user.first_name = update.first_name
    if update.last_name is not None:
        current_user.last_name = update.last_name
    if update.company is not None:
        current_user.company = update.company
    if update.creator_category is not None:
        current_user.creator_category = update.creator_category
    if update.preferred_platform is not None:
        current_user.preferred_platform = update.preferred_platform
    if update.notify_email is not None:
        current_user.notify_email = update.notify_email
    if update.avatar_url is not None:
        current_user.avatar_url = update.avatar_url
    await db.commit()
    await db.refresh(current_user)
    return UserOut.model_validate(current_user)
