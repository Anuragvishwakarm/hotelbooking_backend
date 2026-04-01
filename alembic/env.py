from logging.config import fileConfig
from sqlalchemy import engine_from_config, pool
from alembic import context
import sys
import os

# ✅ Project path add
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

# ✅ Import Base + Models
from app.database import Base
from app.models import user, hotel, booking, payment  # noqa: F401

# ✅ Import settings (.env से DB URL लेने के लिए)
from app.config import settings   # ⚠️ path check: config.py कहाँ है

config = context.config

# ✅ 🔥 IMPORTANT: Alembic को PostgreSQL URL दो (.env से)
config.set_main_option("sqlalchemy.url", settings.DATABASE_URL)

# Logging setup
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = Base.metadata


# ✅ OFFLINE MODE
def run_migrations_offline() -> None:
    url = config.get_main_option("sqlalchemy.url")

    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )

    with context.begin_transaction():
        context.run_migrations()


# ✅ ONLINE MODE
def run_migrations_online() -> None:
    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    with connectable.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            compare_type=True,   # 🔥 detects column changes
        )

        with context.begin_transaction():
            context.run_migrations()


# ✅ Run
if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()