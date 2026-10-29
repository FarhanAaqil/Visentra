"""Shared fixtures: an isolated database and storage root per test session."""

import os
import shutil
import sys
import tempfile
from pathlib import Path

_TMP = Path(tempfile.mkdtemp(prefix="visentra-tests-"))
os.environ["DATABASE_URL"] = f"sqlite+aiosqlite:///{(_TMP / 'test.db').as_posix()}"
os.environ["STORAGE_ROOT"] = str(_TMP / "storage")
os.environ["AUTO_SEED"] = "false"
os.environ["ENABLE_DEMO"] = "true"
os.environ["CASCADE_DELAY_S"] = "0"

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import httpx  # noqa: E402
import pytest  # noqa: E402
import pytest_asyncio  # noqa: E402

from backend.db.models import Base  # noqa: E402
from backend.db.session import engine  # noqa: E402
from backend.main import app  # noqa: E402


def pytest_collection_modifyitems(items):
    # One event loop for the whole run: the async engine's pool is bound to it.
    marker = pytest.mark.asyncio(loop_scope="session")
    for item in items:
        if pytest_asyncio.is_async_test(item):
            item.add_marker(marker, append=False)


@pytest.fixture(scope="session", autouse=True)
async def _schema():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield
    await engine.dispose()
    shutil.rmtree(_TMP, ignore_errors=True)


@pytest.fixture
async def client():
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://visentra.test") as c:
        yield c


@pytest.fixture
async def contributor(client):
    r = await client.post("/contributors", json={"name": "Test Lab"})
    assert r.status_code == 201
    return r.json()
