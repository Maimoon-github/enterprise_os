import asyncio

from app.core.config import settings
from app.core.security import get_password_hash
from app.db.models.brand import Brand
from app.db.models.user import User
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine


async def seed():
    engine = create_async_engine(settings.DATABASE_URL)
    session_factory = async_sessionmaker(engine, expire_on_commit=False)

    async with session_factory() as session:
        # Seed default admin user
        admin = User(
            email="admin@marketing-os.local",
            hashed_password=get_password_hash("admin123"),
            full_name="Platform Administrator",
            role="admin",
            is_active=True,
        )
        session.add(admin)

        # Seed initial brand
        brand = Brand(
            name="Apex Horizon",
            slug="apex-horizon",
            voice_guidelines="Tone: High-agency, precise, zero buzzwords, data-backed proof.",
            target_segments=["B2B Founders", "CMOs"],
            default_platforms=["linkedin", "x", "youtube"],
        )
        session.add(brand)

        await session.commit()
        print("Database seeded with admin user and default brand.")

if __name__ == "__main__":
    asyncio.run(seed())
