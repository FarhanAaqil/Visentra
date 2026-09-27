from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from backend.db.session import get_db
from backend.db.models import Contributor

router = APIRouter(prefix="/contributors", tags=["contributors"])


class ContributorCreate(BaseModel):
    name: str


class ContributorOut(BaseModel):
    id: str
    name: str
    created_at: str

    class Config:
        from_attributes = True


@router.post("", response_model=ContributorOut, status_code=201)
async def create_contributor(body: ContributorCreate, db: AsyncSession = Depends(get_db)):
    contributor = Contributor(name=body.name)
    db.add(contributor)
    await db.commit()
    await db.refresh(contributor)
    return ContributorOut(
        id=contributor.id,
        name=contributor.name,
        created_at=contributor.created_at.isoformat(),
    )


@router.get("", response_model=list[ContributorOut])
async def list_contributors(db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Contributor).order_by(Contributor.created_at.desc()))
    rows = result.scalars().all()
    return [ContributorOut(id=r.id, name=r.name, created_at=r.created_at.isoformat()) for r in rows]


@router.get("/{contributor_id}", response_model=ContributorOut)
async def get_contributor(contributor_id: str, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Contributor).where(Contributor.id == contributor_id))
    contributor = result.scalar_one_or_none()
    if not contributor:
        raise HTTPException(status_code=404, detail="Contributor not found")
    return ContributorOut(id=contributor.id, name=contributor.name, created_at=contributor.created_at.isoformat())
