# workers/arq_settings.py
import os
from arq.connections import RedisSettings

REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379")

redis_settings = RedisSettings.from_dsn(REDIS_URL)
