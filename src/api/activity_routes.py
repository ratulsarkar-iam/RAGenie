"""REST API routes for the per-user Activity Log."""
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query

from ..activity.models import ActivityEvent
from ..auth.dependencies import require_auth, require_admin
from ..auth.models import User
from ..core.logging_config import get_logger

logger = get_logger(__name__)

router = APIRouter(prefix="/api/activity", tags=["activity"])


def _store():
    from .app import app_state  # deferred import to avoid circular dependency
    store = app_state.get("activity_store")
    if store is None:
        raise HTTPException(status_code=503, detail="Activity log not initialised or disabled")
    return store


@router.get("", response_model=List[ActivityEvent])
async def list_my_activity(
    event_type: Optional[str] = Query(default=None),
    page: int = Query(default=1, ge=1),
    limit: int = Query(default=50, ge=1, le=200),
    current_user: User = Depends(require_auth),
):
    return _store().list_for_user(current_user.id, event_type=event_type, page=page, limit=limit)


@router.get("/admin", response_model=List[ActivityEvent])
async def list_all_activity(
    user_id: Optional[str] = Query(default=None),
    event_type: Optional[str] = Query(default=None),
    page: int = Query(default=1, ge=1),
    limit: int = Query(default=50, ge=1, le=200),
    _admin: User = Depends(require_admin),
):
    return _store().list_all(user_id=user_id, event_type=event_type, page=page, limit=limit)
