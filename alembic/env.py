from logging.config import fileConfig
from sqlalchemy import engine_from_config, pool
from alembic import context

#  Import your Base from db.py
from db import Base

# Alembic config
config = context.config

# Logging
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# Set metadata from your models for autogeneration to work
target_metadata = Base.metadata
