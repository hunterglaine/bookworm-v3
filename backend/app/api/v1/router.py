from fastapi import APIRouter

from app.api.v1 import auth, books, health, me, shelves

api_router = APIRouter()
api_router.include_router(health.router, tags=["meta"])
api_router.include_router(auth.router, tags=["auth"])
api_router.include_router(books.router, tags=["books"])
api_router.include_router(shelves.router, tags=["shelves"])
api_router.include_router(me.router, tags=["me"])
