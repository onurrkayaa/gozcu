"""Celery uygulamasi. Ayarlarin tamami settings.py'deki CELERY_ onekli
degiskenlerden okunur; burada sabit adres veya sir yok."""
import os

from celery import Celery

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "gozcu_api.settings")

app = Celery("gozcu")
app.config_from_object("django.conf:settings", namespace="CELERY")
app.autodiscover_tasks()
