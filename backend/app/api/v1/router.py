from fastapi import APIRouter

from app.api.v1 import auth, books, health

api_router = APIRouter()
api_router.include_router(health.router, tags=["meta"])
api_router.include_router(auth.router, tags=["auth"])
api_router.include_router(books.router, tags=["books"])

# Registered as each phase lands:
#   shelves.router  -> /shelves   CRUD + add/remove books
#   me.router       -> /me        reading status, ratings, reviews
