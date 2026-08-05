"""
Shared dependencies for FastAPI routes (MongoDB / Motor Version).
"""
from __future__ import annotations
from typing import Optional, Dict, Any
from bson import ObjectId, errors as bson_errors
from fastapi import Depends, HTTPException, Request, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from motor.motor_asyncio import AsyncIOMotorDatabase

from app.core.config import get_settings
from app.core.security import decode_access_token
from app.core.exceptions import AuthenticationError, TokenExpiredError
from app.db.mongo import get_mongo_db

settings = get_settings()
security_scheme = HTTPBearer(auto_error=False)


class UserContext(dict):
    """
    Dictionary wrapper allowing both attribute dot notation (`user.id`, `user.email`) 
    and dictionary indexing (`user['id']`, `user['email']`).
    """
    def __getattr__(self, name: str) -> Any:
        try:
            return self[name]
        except KeyError:
            raise AttributeError(f"'UserContext' object has no attribute '{name}'")

    def __setattr__(self, name: str, value: Any) -> None:
        self[name] = value


async def get_current_user(
    request: Request,
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(security_scheme),
    db: AsyncIOMotorDatabase = Depends(get_mongo_db)
) -> UserContext:
    """
    Extracts JWT from the Authorization header, validates the payload, 
    and returns the authenticated user document from MongoDB.
    """
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials.",
        headers={"WWW-Authenticate": "Bearer"},
    )

    # 1. Extract Bearer Token
    token: Optional[str] = None
    if credentials and credentials.credentials:
        token = credentials.credentials
    else:
        # Fallback manual header check
        auth_header = request.headers.get("Authorization", "")
        if auth_header.startswith("Bearer "):
            token = auth_header.split(" ", 1)[1]

    if not token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    # 2. Decode & Verify JWT Token
    try:
        payload = decode_access_token(token)
    except TokenExpiredError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token has expired.",
            headers={"WWW-Authenticate": "Bearer"},
        )
    except (AuthenticationError, Exception) as e:
        msg = getattr(e, "message", str(e)) or "Invalid authentication token."
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=msg,
            headers={"WWW-Authenticate": "Bearer"},
        )

    user_id: Optional[str] = payload.get("sub") or payload.get("user_id")
    if not user_id:
        raise credentials_exception

    # 3. Query User Document from MongoDB
    user_doc = None
    try:
        if ObjectId.is_valid(user_id):
            user_doc = await db.users.find_one({"$or": [{"_id": ObjectId(user_id)}, {"id": user_id}]})
        else:
            user_doc = await db.users.find_one({"$or": [{"_id": user_id}, {"id": user_id}]})
    except (bson_errors.InvalidId, Exception):
        user_doc = await db.users.find_one({"id": user_id})

    # 4. Check Activity & Existence
    if not user_doc or not user_doc.get("is_active", True):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User account not found or deactivated.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    # 5. Normalize Identifiers & Apply VIP Unlimited Tier
    user_doc["id"] = str(user_doc.get("_id") or user_doc.get("id"))
    user_doc["_id"] = str(user_doc["_id"])

    # Grant unlimited analysis privileges to bhardwajvineet990@gmail.com
    from app.core.security import is_vip_unlimited
    user_email = user_doc.get("email") or payload.get("email") or ""
    if is_vip_unlimited(user_email):
        user_doc["plan"] = "unlimited_pro"
        user_doc["is_unlimited"] = True
        user_doc["credits_remaining"] = 999999
        user_doc["monthly_credits"] = 999999
        user_doc["credits_used"] = 0
        user_doc["is_admin"] = True

    return UserContext(user_doc)


async def get_current_active_user(
    current_user: UserContext = Depends(get_current_user)
) -> UserContext:
    """Dependency helper to verify active user status."""
    if not current_user.get("is_active", True):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Inactive user account."
        )
    return current_user