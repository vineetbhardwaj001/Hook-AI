"""
Auth routes — signup, login, refresh, logout, me (MongoDB Motor Version)
"""
from __future__ import annotations
from datetime import datetime, timezone, timedelta
from typing import Optional
import hashlib
from bson import ObjectId, errors as bson_errors

from fastapi import APIRouter, Depends, HTTPException, Request, status
from motor.motor_asyncio import AsyncIOMotorDatabase

from app.core.config import get_settings
from app.core.exceptions import AuthenticationError, TokenExpiredError
from app.core.security import (
    hash_password, verify_password,
    create_access_token, create_refresh_token, decode_access_token
)
from app.db.mongo import get_mongo_db
from app.schemas.auth import (
    SignupRequest, LoginRequest, RefreshRequest,
    LoginResponse, TokenResponse, UserOut
)
from app.core.logging import get_logger

logger = get_logger(__name__)
settings = get_settings()
router = APIRouter(prefix="/auth", tags=["Authentication"])


async def _get_or_create_free_plan(db: AsyncIOMotorDatabase) -> dict:
    """Fetch free plan or create default in MongoDB."""
    plan = await db.plans.find_one({"name": "free"})
    if not plan:
        plan = {
            "name": "free",
            "display_name": "Free Plan",
            "monthly_credits": 10,
            "max_video_duration_seconds": 600,
            "max_upload_size_mb": 100,
            "price_monthly": 0.0,
            "created_at": datetime.now(timezone.utc),
        }
        result = await db.plans.insert_one(plan)
        plan["_id"] = result.inserted_id
    return plan


# app/api/v1/auth.py

@router.post("/signup", response_model=LoginResponse)
@router.post("/register", response_model=LoginResponse)  # <--- Add this line!
async def signup(req: SignupRequest, db: AsyncIOMotorDatabase = Depends(get_mongo_db)):
    # ... rest of your existing signup code stays the same ...
    email_clean = req.email.strip().lower()

    # Check duplicate email in users collection
    existing = await db.users.find_one({"email": email_clean})
    if existing:
        raise HTTPException(status_code=400, detail="An account with this email already exists.")

    # Create user document
    user_doc = {
        "email": email_clean,
        "password_hash": hash_password(req.password),
        "first_name": req.first_name,
        "last_name": req.last_name,
        "is_verified": True,
        "is_active": True,
        "created_at": datetime.now(timezone.utc),
        "updated_at": datetime.now(timezone.utc),
    }
    result = await db.users.insert_one(user_doc)
    user_id_str = str(result.inserted_id)
    user_doc["id"] = user_id_str

    # Assign free plan subscription
    free_plan = await _get_or_create_free_plan(db)
    sub_doc = {
        "user_id": user_id_str,
        "plan_id": str(free_plan["_id"]),
        "credits_remaining": free_plan.get("monthly_credits", 10),
        "credits_used": 0,
        "created_at": datetime.now(timezone.utc),
    }
    await db.subscriptions.insert_one(sub_doc)

    # Create tokens & store refresh token in MongoDB
    access_token = create_access_token(user_id_str, email_clean)
    refresh_raw = create_refresh_token()
    refresh_hash = hashlib.sha256(refresh_raw.encode()).hexdigest()
    expires = datetime.now(timezone.utc) + timedelta(days=settings.refresh_token_expire_days)

    await db.refresh_tokens.insert_one({
        "user_id": user_id_str,
        "token_hash": refresh_hash,
        "expires_at": expires,
        "is_revoked": False,
        "created_at": datetime.now(timezone.utc),
    })

    return LoginResponse(
        access_token=access_token,
        refresh_token=refresh_raw,
        user=UserOut.model_validate(user_doc),
    )


@router.post("/login", response_model=LoginResponse)
async def login(req: LoginRequest, db: AsyncIOMotorDatabase = Depends(get_mongo_db)):
    email_clean = req.email.strip().lower()
    user_doc = await db.users.find_one({"email": email_clean})

    if not user_doc or not verify_password(req.password, user_doc.get("password_hash", "")):
        raise HTTPException(status_code=401, detail="Invalid email or password.")

    if not user_doc.get("is_active", True):
        raise HTTPException(status_code=403, detail="This account has been deactivated.")

    user_id_str = str(user_doc["_id"])
    user_doc["id"] = user_id_str

    login_count = user_doc.get("login_count", 0) + 1
    await db.users.update_one(
        {"_id": user_doc["_id"]},
        {"$set": {"login_count": login_count, "last_login": datetime.now(timezone.utc)}}
    )
    user_doc["login_count"] = login_count

    access_token = create_access_token(user_id_str, email_clean)
    refresh_raw = create_refresh_token()
    refresh_hash = hashlib.sha256(refresh_raw.encode()).hexdigest()
    expires = datetime.now(timezone.utc) + timedelta(days=settings.refresh_token_expire_days)

    await db.refresh_tokens.insert_one({
        "user_id": user_id_str,
        "token_hash": refresh_hash,
        "expires_at": expires,
        "is_revoked": False,
        "created_at": datetime.now(timezone.utc),
    })

    return LoginResponse(
        access_token=access_token,
        refresh_token=refresh_raw,
        user=UserOut.model_validate(user_doc),
    )


@router.post("/refresh", response_model=TokenResponse)
async def refresh_token(req: RefreshRequest, db: AsyncIOMotorDatabase = Depends(get_mongo_db)):
    token_hash = hashlib.sha256(req.refresh_token.encode()).hexdigest()
    token_rec = await db.refresh_tokens.find_one({
        "token_hash": token_hash,
        "is_revoked": False,
    })

    if not token_rec:
        raise HTTPException(status_code=401, detail="Invalid or expired refresh token.")

    expires_at = token_rec.get("expires_at")
    if expires_at and expires_at.tzinfo is None:
        expires_at = expires_at.replace(tzinfo=timezone.utc)

    if not expires_at or expires_at < datetime.now(timezone.utc):
        raise HTTPException(status_code=401, detail="Invalid or expired refresh token.")

    # Revoke old refresh token
    await db.refresh_tokens.update_one(
        {"_id": token_rec["_id"]},
        {"$set": {"is_revoked": True}}
    )

    # Fetch user
    user_id_str = token_rec["user_id"]
    try:
        user_doc = await db.users.find_one({"_id": ObjectId(user_id_str)})
    except bson_errors.InvalidId:
        user_doc = await db.users.find_one({"_id": user_id_str})

    if not user_doc:
        raise HTTPException(status_code=401, detail="User not found.")

    new_access = create_access_token(user_id_str, user_doc["email"])
    new_refresh_raw = create_refresh_token()
    new_refresh_hash = hashlib.sha256(new_refresh_raw.encode()).hexdigest()
    new_expires = datetime.now(timezone.utc) + timedelta(days=settings.refresh_token_expire_days)

    await db.refresh_tokens.insert_one({
        "user_id": user_id_str,
        "token_hash": new_refresh_hash,
        "expires_at": new_expires,
        "is_revoked": False,
        "created_at": datetime.now(timezone.utc),
    })

    return TokenResponse(access_token=new_access, refresh_token=new_refresh_raw)


@router.post("/logout")
async def logout(req: RefreshRequest, db: AsyncIOMotorDatabase = Depends(get_mongo_db)):
    token_hash = hashlib.sha256(req.refresh_token.encode()).hexdigest()
    await db.refresh_tokens.update_one(
        {"token_hash": token_hash},
        {"$set": {"is_revoked": True}}
    )
    return {"message": "Logged out successfully."}


@router.get("/me", response_model=UserOut)
async def get_me(request: Request, db: AsyncIOMotorDatabase = Depends(get_mongo_db)):
    user_doc = await _get_current_user(request, db)
    return UserOut.model_validate(user_doc)


async def _get_current_user(request: Request, db: AsyncIOMotorDatabase) -> dict:
    """Extract and validate JWT from Authorization header."""
    auth_header = request.headers.get("Authorization", "")
    if not auth_header.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Not authenticated.")

    token = auth_header.split(" ", 1)[1]
    try:
        payload = decode_access_token(token)
    except (AuthenticationError, TokenExpiredError) as e:
        raise HTTPException(status_code=401, detail=str(e))

    user_id = payload.get("sub")
    if not user_id:
        raise HTTPException(status_code=401, detail="Invalid token payload.")

    try:
        user_doc = await db.users.find_one({"_id": ObjectId(user_id)})
    except bson_errors.InvalidId:
        user_doc = await db.users.find_one({"_id": user_id})

    if not user_doc or not user_doc.get("is_active", True):
        raise HTTPException(status_code=401, detail="User not found or inactive.")

    user_doc["id"] = str(user_doc["_id"])
    return user_doc