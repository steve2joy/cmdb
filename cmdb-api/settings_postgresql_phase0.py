from importlib.util import module_from_spec
from importlib.util import spec_from_file_location
from pathlib import Path

from environs import Env


def _load_settings_example():
    settings_path = Path(__file__).with_name("settings.example.py")
    spec = spec_from_file_location("settings_example", settings_path)
    module = module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


_settings_example = _load_settings_example()

for _name in dir(_settings_example):
    if _name.isupper():
        globals()[_name] = getattr(_settings_example, _name)


env = Env()
env.read_env()

PG_USER = env.str("PG_USER", default="cmdb")
PG_PASSWORD = env.str("PG_PASSWORD", default="123456")
PG_HOST = env.str("PG_HOST", default="127.0.0.1")
PG_PORT = env.int("PG_PORT", default=55432)
PG_DATABASE = env.str("PG_DATABASE", default="cmdb")

SQLALCHEMY_DATABASE_URI = (
    f"postgresql+psycopg2://{PG_USER}:{PG_PASSWORD}@{PG_HOST}:{PG_PORT}/{PG_DATABASE}"
)
SQLALCHEMY_BINDS = {
    "user": SQLALCHEMY_DATABASE_URI,
}
SQLALCHEMY_ENGINE_OPTIONS = {
    **(SQLALCHEMY_ENGINE_OPTIONS or {}),
    "pool_recycle": 300,
    "pool_pre_ping": True,
    "connect_args": {
        "connect_timeout": 10,
    },
}

CACHE_REDIS_HOST = env.str("CACHE_REDIS_HOST", default="127.0.0.1")
CACHE_REDIS_PORT = env.str("CACHE_REDIS_PORT", default="56379")

CELERY = {
    **CELERY,
    "broker_url": env.str("CELERY_BROKER_URL", default="redis://127.0.0.1:56379/2"),
    "result_backend": env.str("CELERY_RESULT_BACKEND", default="redis://127.0.0.1:56379/2"),
}

ONCE = {
    "backend": "celery_once.backends.Redis",
    "settings": {
        "url": CELERY["broker_url"],
    },
}
