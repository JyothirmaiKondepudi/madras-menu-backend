import os
import sys
from logging.config import fileConfig

from sqlalchemy import engine_from_config
from sqlalchemy import pool

from alembic import context

# so `from database import Base` / `import models` resolve when alembic is
# invoked from the project root (they aren't on sys.path by default)
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from database import Base  # noqa: E402
import models  # noqa: E402, F401 — registers every ORM class on Base.metadata (Notification included)
import embeddings.model  # noqa: E402, F401 — registers MenuItemEmbedding too

# this is the Alembic Config object, which provides
# access to the values within the .ini file in use.
config = context.config

# DATABASE_URL always wins over whatever's in alembic.ini — same env var
# every other part of this app already reads it from (database.py, docker-compose.yml)
if os.environ.get("DATABASE_URL"):
    config.set_main_option("sqlalchemy.url", os.environ["DATABASE_URL"])

# Interpret the config file for Python logging.
# This line sets up loggers basically.
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# add your model's MetaData object here
# for 'autogenerate' support
target_metadata = Base.metadata

# Tables this app's Alembic migrations are actually allowed to create/alter/
# drop. Every other table in the database — madras-menu-studio's Prisma-owned
# ones (menu_items, item_relationships, tax_categories included, even though
# they have SQLAlchemy models here for querying — see models/tax_category.py
# and models/menu_item.py's own comments) plus the 11+ Prisma tables with
# no model here at all (users, events,
# occasions, price_tiers, ...) — must never be touched by autogenerate.
#
# This isn't just belt-and-suspenders: the very first autogenerate run
# against this database proposed dropping all 14 Prisma tables, because
# SQLAlchemy's metadata didn't declare them. That was caught by hand-editing
# the diff before applying it — a real near-miss, and with these two schemas
# now coexisting permanently (not just during a transition), relying on
# catching it by eye on every future autogenerate isn't a strong enough
# safety net. This allowlist makes the exclusion structural instead:
# non-owned tables are excluded from comparison entirely, so they can never
# appear in a generated diff in the first place, no matter how a future
# autogenerate pass gets reviewed (or isn't).
OWNED_TABLES = {
    "user_data", "projects", "invoices", "subprojects", "user_projects", "menu_item_embeddings",
    "permissions", "role_permissions", "notifications",
}


def include_object(object, name, type_, reflected, compare_to):
    # `include_name` looked like the right hook but isn't: it excludes a
    # table from whichever single side (reflected DB vs. target metadata)
    # is being iterated at the time, not both symmetrically — which made
    # tax_categories/menu_items/item_relationships (modeled here for
    # querying, but reflected as already existing in the real DB) show up
    # as "needs to be created", the opposite of what's needed.
    # include_object is checked per comparison pair (reflected vs.
    # metadata together), so excluding by name here actually removes the
    # table from consideration on both sides at once.
    if type_ == "table":
        return name in OWNED_TABLES
    return True

# other values from the config, defined by the needs of env.py,
# can be acquired:
# my_important_option = config.get_main_option("my_important_option")
# ... etc.


def run_migrations_offline() -> None:
    """Run migrations in 'offline' mode.

    This configures the context with just a URL
    and not an Engine, though an Engine is acceptable
    here as well.  By skipping the Engine creation
    we don't even need a DBAPI to be available.

    Calls to context.execute() here emit the given string to the
    script output.

    """
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        include_object=include_object,
    )

    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """Run migrations in 'online' mode.

    In this scenario we need to create an Engine
    and associate a connection with the context.

    """
    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    with connectable.connect() as connection:
        context.configure(
            connection=connection, target_metadata=target_metadata, include_object=include_object
        )

        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
