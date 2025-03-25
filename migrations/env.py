from logging.config import fileConfig
import os
import sys
import logging
from sqlalchemy import engine_from_config, create_engine, URL
from sqlalchemy import pool
import urllib.parse

from alembic import context

# Add the project root directory to Python's path
# This allows Alembic to find the app module
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

# Import your models so Alembic can discover them
from app.core.database import Base
from app.core.config import settings
from app.modules.auth.models import User, UserRole, UserCriteria, CpvCode, Keyword, ContractType
from app.modules.tenders.models import UserTender, TenderDocuments

# this is the Alembic Config object, which provides
# access to the values within the .ini file in use.
config = context.config

# Interpret the config file for Python logging.
# This line sets up loggers basically.
if config.config_file_name is not None:
    try:
        fileConfig(config.config_file_name)
    except Exception as e:
        # Set up basic logging if fileConfig fails
        logging.basicConfig(level=logging.INFO)
        logging.info(f"Could not configure logging from file: {e}")

# add your model's MetaData object here
# for 'autogenerate' support
target_metadata = Base.metadata
# target_metadata = None

def get_url():
    # Construct a connection URL that works with your Azure SQL Database
    password = urllib.parse.quote_plus(settings.DB_PASSWORD)
    
    # Using pyodbc with specified driver
    connection_string = f"mssql+pyodbc://{settings.DB_USER}:{password}@{settings.DB_SERVER}/{settings.DB_NAME}?driver=ODBC+Driver+18+for+SQL+Server&encrypt=yes&TrustServerCertificate=yes"
    
    return connection_string

def run_migrations_offline() -> None:
    """Run migrations in 'offline' mode.

    This configures the context with just a URL
    and not an Engine, though an Engine is acceptable
    here as well.  By skipping the Engine creation
    we don't even need a DBAPI to be available.

    Calls to context.execute() here emit the given string to the
    script output.

    """
    url = get_url()
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )

    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """Run migrations in 'online' mode.

    In this scenario we need to create an Engine
    and associate a connection with the context.

    """
    # Create a connection URL using pyodbc
    connection_url = get_url()
    
    # Create the engine with the proper connection parameters
    engine = create_engine(connection_url)

    with engine.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata
        )

        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
