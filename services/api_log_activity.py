import logging

from database import SessionLocal
from models.api_logs import ApiLogs

logger = logging.getLogger("uvicorn.error")


def record_api_log(**fields) -> None:
    """Insert one api_logs row. Never raises: a failed log write must not break the request."""
    db = SessionLocal()  # its own session, not the route's (which may have rolled back)
    try:
        db.add(ApiLogs(**fields))
        db.commit()
    except Exception:
        db.rollback()
        logger.warning("Failed to write api_logs row", exc_info=True)
    finally:
        db.close()
