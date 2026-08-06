from fastapi import APIRouter

router = APIRouter()


@router.get("/health")
async def health() -> dict[str, str]:
    """Versioned health check, so clients can probe the API surface they use."""
    return {"status": "ok"}
