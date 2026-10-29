from typing import TypeVar

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

T = TypeVar("T")


async def get_or_404(db: AsyncSession, model: type[T], ident: str, label: str | None = None) -> T:
    row = (await db.execute(select(model).where(model.id == ident))).scalar_one_or_none()
    if row is None:
        raise HTTPException(status_code=404, detail=f"{label or model.__name__} not found")
    return row


def require_demo() -> None:
    from backend.config import settings

    if not settings.enable_demo:
        raise HTTPException(status_code=403, detail="Demo endpoints are disabled on this deployment")
