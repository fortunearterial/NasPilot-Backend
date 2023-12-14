import importlib
from pathlib import Path
from urllib.parse import quote_plus

from alembic.config import Config as AlembicConfig
from alembic.command import revision as alembic_revision

from app.core.config import settings

# 导入模块，避免建表缺失
for module in Path(Path(__file__).parent).joinpath("app/db/models").glob("*.py"):
    importlib.import_module(f"app.db.models.{module.stem}")

db_version = input("请输入版本号：")
script_location = settings.ROOT_PATH / 'database'
alembic_cfg = AlembicConfig()
alembic_cfg.set_main_option('script_location', str(script_location))
alembic_cfg.set_main_option('sqlalchemy.url', settings.DB_URL)
alembic_revision(alembic_cfg, db_version, True)
