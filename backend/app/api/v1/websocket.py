"""
WebSocket progress streaming endpoint (100% Redis-Free / MongoDB Version).
"""
from __future__ import annotations
import asyncio
from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from bson import ObjectId, errors as bson_errors

from app.db.mongo import get_mongo_db
from app.core.logging import get_logger

logger = get_logger(__name__)
router = APIRouter(tags=["WebSocket"])


@router.websocket("/analyses/{analysis_id}/ws")
@router.websocket("/api/analyses/{analysis_id}/ws")
async def analysis_websocket(websocket: WebSocket, analysis_id: str):
    """
    Stream live progress updates from MongoDB Atlas to WebSocket clients.
    Runs 100% Redis-free.
    """
    await websocket.accept()
    logger.info(f"WebSocket client connected for analysis: {analysis_id}")

    db = get_mongo_db()

    query = {"$or": [{"_id": analysis_id}, {"id": analysis_id}]}
    try:
        query["$or"].append({"_id": ObjectId(analysis_id)})
    except bson_errors.InvalidId:
        pass

    try:
        while True:
            doc = await db.analyses.find_one(query, {
                "progress": 1, "stage": 1, "status": 1,
                "message": 1, "stage_label": 1, "error": 1
            })

            if doc:
                status = doc.get("status", "processing")
                payload = {
                    "analysis_id": analysis_id,
                    "status": status,
                    "stage": doc.get("stage", "queued"),
                    "stage_label": doc.get("stage_label", doc.get("stage", "queued")),
                    "progress": doc.get("progress", 0),
                    "message": doc.get("message", "Processing video..."),
                }
                if "error" in doc:
                    payload["error"] = doc["error"]

                await websocket.send_json(payload)

                # Stop streaming once task reaches terminal state
                if status in ("completed", "failed"):
                    logger.info(f"Analysis {analysis_id} reached '{status}'. Closing WebSocket.")
                    break

            # Poll MongoDB every 1 second
            await asyncio.sleep(1.0)

    except WebSocketDisconnect:
        logger.info(f"WebSocket client disconnected for analysis: {analysis_id}")
    except Exception as e:
        logger.warning(f"WebSocket session error for {analysis_id}: {e}")
        try:
            await websocket.close()
        except Exception:
            pass