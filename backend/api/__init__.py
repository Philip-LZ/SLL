"""Compose the public API routers."""

from fastapi import APIRouter

from . import auth, chat, longtext, records

router = APIRouter()
router.include_router(auth.router)
router.include_router(records.router)
router.include_router(chat.router)
router.include_router(longtext.router)
