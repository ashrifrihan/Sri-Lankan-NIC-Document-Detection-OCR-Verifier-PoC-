from app.config import settings

bind = f"{settings.HOST}:{settings.PORT}"
workers = settings.WEB_WORKERS
worker_class = "uvicorn_worker.UvicornWorker"
timeout = 180
graceful_timeout = 120
