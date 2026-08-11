from fastapi import APIRouter

from app.api.v1 import auth, health

api_router = APIRouter()
api_router.include_router(health.router, tags=["meta"])
api_router.include_router(auth.router, tags=["auth"])

# Registered as each phase lands:
#   books.router    -> /books     search, detail
#   shelves.router  -> /shelves   CRUD + add/remove books
#   me.router       -> /me        reading status, ratings, reviews
