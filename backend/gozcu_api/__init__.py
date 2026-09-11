# Django acilirken Celery uygulamasi da kayitlansin; @shared_task bunu bekler.
from .celery import app as celery_app

__all__ = ("celery_app",)
