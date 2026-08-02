"""
MongoDB connection manager for FastAPI using Motor (async driver).
"""
from __future__ import annotations
from typing import Optional
from motor.motor_asyncio import AsyncIOMotorClient, AsyncIOMotorDatabase
from app.core.config import get_settings
from app.core.logging import get_logger

logger = get_logger(__name__)
settings = get_settings()

mongo_client: Optional[AsyncIOMotorClient] = None
mongo_db: Optional[AsyncIOMotorDatabase] = None


async def init_mongo() -> AsyncIOMotorDatabase:
    """Initialize AsyncIOMotorClient and database connection."""
    global mongo_client, mongo_db
    try:
        mongo_client = AsyncIOMotorClient(settings.mongo_uri)
        # Extract db name from URI or default to 'hook'
        db_name = "hook"
        mongo_db = mongo_client[db_name]

        # Quick ping to verify connection
        await mongo_client.admin.command('ping')
        logger.info(f"✅ Connected to MongoDB Atlas | database='{db_name}'")
        return mongo_db
    except Exception as e:
        logger.warning(f"⚠️ MongoDB connection notice: {e}")
        return mongo_db


async def close_mongo():
    """Close AsyncIOMotorClient connection."""
    global mongo_client
    if mongo_client:
        mongo_client.close()
        logger.info("MongoDB connection closed.")


def get_mongo_db() -> AsyncIOMotorDatabase:
    """Dependency / accessor for MongoDB database instance."""
    return mongo_db
