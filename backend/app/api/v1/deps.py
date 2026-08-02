"""
Shared dependency: get_current_user from JWT (MongoDB / Motor Version).
"""
from __future__ import annotations
from bson import ObjectId, errors as bson_errors
from fastapi import Depends, HTTPException, Request, status
from motor.motor_asyncio import AsyncIOMotorDatabase

from app.core.security import decode_access_token
from app.core.exceptions import AuthenticationError, TokenExpiredError
from app.db.mongo import get_mongo_db


class UserContext(dict):
    """Dictionary wrapper that allows both dot notation (user.id) and dict indexing (user['id'])."""
    def __getattr__(self, name: str):
        try:
            return self[name]
        except KeyError:
            raise AttributeError(f"'UserContext' object has no attribute '{name}'")

    def __setattr__(self, name: str, value):
        self[name] = value


async def get_current_user(
    request: Request,
    db: AsyncIOMotorDatabase = Depends(get_mongo_db)
) -> UserContext:
    """
    Extract JWT token from Authorization header and fetch current user from MongoDB.
    """
    auth_header = request.headers.get("Authorization", "")
    if not auth_header.startswith("Bearer "):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated."
        )

    token = auth_header.split(" ", 1)[1]
    try:
        payload = decode_access_token(token)
    except (AuthenticationError, TokenExpiredError) as e:
        msg = getattr(e, "message", str(e))
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=msg
        )

    user_id = payload.get("sub")
    if not user_id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token payload."
        )

    # Fetch user from MongoDB users collection
    try:
        user_doc = await db.users.find_one({"_id": ObjectId(user_id)})
    except bson_errors.InvalidId:
        user_doc = await db.users.find_one({"_id": user_id})

    if not user_doc or not user_doc.get("is_active", True):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found or inactive."
        )

    # Ensure 'id' string field exists
    user_doc["id"] = str(user_doc["_id"])
    return UserContext(user_doc)