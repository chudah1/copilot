import asyncio
from logging.config import fileConfig

from alembic import context
from alembic.script import ScriptDirectory

from app.config import settings
from app.database import Base, make_async_engine
from app.models import *  # noqa: F403
from app.sqlite_dev_compat import bootstrap_local_sqlite_alembic_head

config = context.config
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = Base.metadata


def run_migrations_offline():
    context.configure(url=settings.database_url, target_metadata=target_metadata, literal_binds=True)
    with context.begin_transaction():
        context.run_migrations()


def do_run_migrations(connection):
    script = ScriptDirectory.from_config(config)
    if bootstrap_local_sqlite_alembic_head(connection, Base.metadata, script.get_current_head()):
        return
    context.configure(connection=connection, target_metadata=target_metadata)
    with context.begin_transaction():
        context.run_migrations()


async def run_migrations_online():
    connectable = make_async_engine(settings.database_url)
    async with connectable.connect() as connection:
        await connection.run_sync(do_run_migrations)
    await connectable.dispose()


if context.is_offline_mode():
    run_migrations_offline()
else:
    asyncio.run(run_migrations_online())
