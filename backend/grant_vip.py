import asyncio
import sys
sys.path.insert(0, '.')
from app.db.mongo import init_mongo, close_mongo

async def grant_unlimited():
    db = await init_mongo()
    if db is not None:
        target_email = "bhardwajvineet990@gmail.com"
        u_res = await db.users.update_many(
            {"email": target_email},
            {"$set": {
                "plan": "unlimited_pro",
                "is_unlimited": True,
                "credits_remaining": 999999,
                "monthly_credits": 999999,
                "credits_used": 0,
                "is_admin": True,
            }}
        )
        print("Updated user documents count:", u_res.modified_count)

        s_res = await db.subscriptions.update_many(
            {"email": target_email},
            {"$set": {
                "plan_id": "unlimited_pro",
                "credits_remaining": 999999,
                "monthly_credits": 999999,
                "credits_used": 0,
                "is_unlimited": True,
            }}
        )
        print("Updated subscription documents count:", s_res.modified_count)
    await close_mongo()

if __name__ == "__main__":
    asyncio.run(grant_unlimited())
