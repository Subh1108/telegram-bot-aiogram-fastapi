import logging
from aiogram import Router
from aiogram.types import ErrorEvent

logger = logging.getLogger("errors")
router = Router()


@router.errors()
async def global_error_handler(event: ErrorEvent):
    logger.error(
        f"Update caused error: {event.exception}",
        exc_info=True
    )
    return True
