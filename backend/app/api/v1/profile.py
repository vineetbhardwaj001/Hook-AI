"""Profile API route — Async MongoDB (Motor) implementation."""
from __future__ import annotations
from typing import Dict, Any, Optional
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, EmailStr

from app.api.v1.deps import get_current_user
from app.db.mongo import get_mongo_db

router = APIRouter(prefix="/profile", tags=["Profile"])


class ProfileUpdateRequest(BaseModel):
    full_name: Optional[str] = None
    email: Optional[EmailStr] = None


@router.get("")
async def get_profile(current_user: dict = Depends(get_current_user)) -> Dict[str, Any]:
    """Fetch profile data for the authenticated user."""
    user_id = str(current_user.get("_id") or current_user.get("id"))
    
    return {
        "id": user_id,
        "email": current_user.get("email", ""),
        "full_name": current_user.get("full_name", ""),
        "role": current_user.get("role", "user"),
        "created_at": current_user.get("created_at"),
    }


@router.put("")
async def update_profile(
    payload: ProfileUpdateRequest,
    current_user: dict = Depends(get_current_user)
) -> Dict[str, Any]:
    """Update profile details in MongoDB."""
    db = get_mongo_db()
    user_id = str(current_user.get("_id") or current_user.get("id"))

    update_fields = {k: v for k, v in payload.model_dump().items() if v is not None}
    if not update_fields:
        raise HTTPException(status_code=400, detail="No fields provided to update.")

    await db.users.update_one(
        {"$or": [{"_id": user_id}, {"id": user_id}]},
        {"$set": update_fields}
    )

    updated_user = await db.users.find_one({"$or": [{"_id": user_id}, {"id": user_id}]}) or {}

    return {
        "id": user_id,
        "email": updated_user.get("email", ""),
        "full_name": updated_user.get("full_name", ""),
        "message": "Profile updated successfully.",
    }