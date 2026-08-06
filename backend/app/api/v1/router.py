from fastapi import APIRouter

from app.api.v1 import health

api_router = APIRouter()
api_router.include_router(health.router, tags=["meta"])

# Registered as each phase lands:
#   auth.router     -> /auth      register, login, refresh, logout
#   books.router    -> /books     search, detail
#   shelves.router  -> /shelves   CRUD + add/remove books
#   me.router       -> /me        reading status, ratings, reviews
