import asyncio
import logging
import sys
from pathlib import Path
from typing import Any

# Ensure backend root is on sys.path for direct script execution
backend_root = Path(__file__).resolve().parent.parent
if str(backend_root) not in sys.path:
    sys.path.insert(0, str(backend_root))

from app.core.config import settings  # noqa: E402
from app.core.security import get_password_hash  # noqa: E402
from app.db.base import Base  # noqa: E402
from app.db.models.brand import Brand  # noqa: E402
from app.db.models.user import User  # noqa: E402
from mcp_servers.brand_rag_server.tools import index_brand_document  # noqa: E402
from sqlalchemy import select  # noqa: E402
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine  # noqa: E402

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("seed_db")

# Deterministic Brand RAG guideline documents for offline & local retrieval
DETERMINISTIC_GUIDELINE_DOCS: list[dict[str, Any]] = [
    {
        "id": "doc_apex_voice_01",
        "collection": "brand_guidelines",
        "title": "Apex Horizon Brand Voice & Pillars",
        "content": (
            "Apex Horizon mandates high-agency, authoritative communication backed by verified metrics. "
            "Primary Pillars: Zero Hallucinations, Deterministic State Machine, Human Governance, Auditable Lineage. "
            "Prohibited Buzzwords: game-changer, paradigm shift, synergy, disruptive, revolutionary, deep dive."
        ),
        "score": 0.98,
    },
    {
        "id": "doc_platform_specs_01",
        "collection": "brand_guidelines",
        "title": "Multi-Platform Asset Constraints & Dimensions",
        "content": (
            "Standard platform copy limits: LinkedIn 3000 chars, X 280 chars, Threads 500 chars, YouTube title 100 chars. "
            "Supported aspect ratios: 1:1 square, 4:5 vertical portrait, 9:16 story/shorts, 16:9 landscape. "
            "All outbound assets must receive explicit human approval prior to fan-out dispatch."
        ),
        "score": 0.95,
    },
    {
        "id": "doc_historical_learnings_01",
        "collection": "historical_campaigns",
        "title": "Q3 Enterprise SaaS Conversion Win",
        "content": (
            "Campaign win_q3_saas_scale achieved 4.8% CTR and 12.5% conversion by leading with: "
            "'Stop gambling on autonomous agents without approval gates.' "
            "Carousels highlighting LangGraph state checkpoints drove 3.4x higher demo velocity."
        ),
        "score": 0.92,
    },
]


async def seed(session: AsyncSession | None = None) -> dict[str, Any]:
    """Idempotently seed admin user, demo brand, and pre-indexed guidelines.

    Can run with an existing session (e.g. unit tests) or create its own engine session.
    """
    logger.info("Initializing idempotent database seed...")

    async def _execute_seed(s: AsyncSession) -> dict[str, Any]:
        # 1. Idempotent Admin User
        user_stmt = select(User).where(User.email == "admin@marketing-os.local")
        result = await s.execute(user_stmt)
        admin = result.scalars().first()

        if not admin:
            admin = User(
                email="admin@marketing-os.local",
                hashed_password=get_password_hash("admin123"),
                full_name="Platform Administrator",
                role="admin",
                is_active=True,
            )
            s.add(admin)
            logger.info("Created default admin user: %s", admin.email)
        else:
            admin.role = "admin"
            admin.is_active = True
            logger.info("Verified existing admin user: %s", admin.email)

        # 2. Idempotent Demo Brand
        brand_stmt = select(Brand).where(Brand.slug == "apex-horizon")
        result = await s.execute(brand_stmt)
        brand = result.scalars().first()

        voice_text = (
            "Tone: High-agency, authoritative, and data-backed proof. "
            "Primary Pillars: Zero Hallucinations, Deterministic State, Human Governance. "
            "Prohibited Phrases: game-changer, paradigm shift, synergy, disruptive, deep dive."
        )
        target_segments = [
            "B2B SaaS Executives",
            "Growth & Performance Marketers",
            "Platform & DevOps Engineers",
        ]
        default_platforms = ["linkedin", "x", "youtube", "threads"]

        if not brand:
            brand = Brand(
                name="Apex Horizon",
                slug="apex-horizon",
                voice_guidelines=voice_text,
                target_segments=target_segments,
                default_platforms=default_platforms,
            )
            s.add(brand)
            logger.info("Created demo brand: %s (slug=%s)", brand.name, brand.slug)
        else:
            brand.name = "Apex Horizon"
            brand.voice_guidelines = voice_text
            brand.target_segments = target_segments
            brand.default_platforms = default_platforms
            logger.info("Updated existing demo brand: %s (slug=%s)", brand.name, brand.slug)

        await s.commit()

        # 3. Seed Deterministic Guidelines into Brand RAG Server
        indexed_count = 0
        for doc in DETERMINISTIC_GUIDELINE_DOCS:
            index_brand_document(doc)
            indexed_count += 1
        logger.info("Indexed %d deterministic guideline documents into Brand RAG knowledge base.", indexed_count)

        return {
            "admin_user": admin.email,
            "brand_id": str(brand.id),
            "brand_slug": brand.slug,
            "guidelines_indexed": indexed_count,
        }

    if session is not None:
        return await _execute_seed(session)

    engine = create_async_engine(settings.DATABASE_URL)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    session_factory = async_sessionmaker(engine, expire_on_commit=False)
    async with session_factory() as s:
        res = await _execute_seed(s)
    await engine.dispose()
    return res


if __name__ == "__main__":
    result = asyncio.run(seed())
    print(f"Seed complete: {result}")
