"""gozcu_api ayarlari. Tum sirlar ortam degiskenlerinden okunur."""
import os
from pathlib import Path

from django.core.exceptions import ImproperlyConfigured
from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent.parent

# Konteyner disinda calistirilirsa proje kokundeki .env dosyasini da yukle.
load_dotenv(BASE_DIR.parent / ".env")


def env(name, default=None):
    value = os.environ.get(name, default)
    if value is None:
        raise ImproperlyConfigured(f"{name} ortam degiskeni tanimli degil.")
    return value


# Gizli bir varsayilana dusmuyoruz: anahtar yoksa uygulama acilmasin.
SECRET_KEY = env("DJANGO_SECRET_KEY")
if not SECRET_KEY.strip():
    raise ImproperlyConfigured("DJANGO_SECRET_KEY bos olamaz.")

DEBUG = env("DJANGO_DEBUG", "0") == "1"
ALLOWED_HOSTS = [h.strip() for h in env("DJANGO_ALLOWED_HOSTS", "").split(",") if h.strip()]

INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "django.contrib.gis",
    "rest_framework",
    "corsheaders",
    "core",
]

MIDDLEWARE = [
    "corsheaders.middleware.CorsMiddleware",
    "django.middleware.security.SecurityMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

ROOT_URLCONF = "gozcu_api.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
            ],
        },
    },
]

WSGI_APPLICATION = "gozcu_api.wsgi.application"
ASGI_APPLICATION = "gozcu_api.asgi.application"

DATABASES = {
    "default": {
        "ENGINE": "django.contrib.gis.db.backends.postgis",
        "NAME": env("POSTGRES_DB"),
        "USER": env("POSTGRES_USER"),
        "PASSWORD": env("POSTGRES_PASSWORD"),
        "HOST": env("DB_HOST", "db"),
        "PORT": env("DB_PORT", "5432"),
    }
}

AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator"},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]

LANGUAGE_CODE = "en-us"
TIME_ZONE = "UTC"
USE_I18N = True
USE_TZ = True

STATIC_URL = "static/"
STATIC_ROOT = BASE_DIR / "staticfiles"
MEDIA_URL = "media/"
MEDIA_ROOT = BASE_DIR / "media"

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

REST_FRAMEWORK = {
    "DEFAULT_AUTHENTICATION_CLASSES": (
        "rest_framework_simplejwt.authentication.JWTAuthentication",
    ),
    "DEFAULT_PERMISSION_CLASSES": ("rest_framework.permissions.IsAuthenticated",),
    "DEFAULT_PAGINATION_CLASS": "rest_framework.pagination.PageNumberPagination",
    "PAGE_SIZE": 20,
}

CORS_ALLOW_ALL_ORIGINS = DEBUG

# --- Celery ---------------------------------------------------------------
CELERY_BROKER_URL = env("CELERY_BROKER_URL")
CELERY_RESULT_BACKEND = env("CELERY_RESULT_BACKEND")

# Yalnizca json: pickle acik birakilirsa broker'a erisebilen biri kod calistirir.
CELERY_TASK_SERIALIZER = "json"
CELERY_RESULT_SERIALIZER = "json"
CELERY_ACCEPT_CONTENT = ["json"]

CELERY_TIMEZONE = TIME_ZONE
CELERY_ENABLE_UTC = True

# Zaman asimlari acikca tanimli: asili kalan bir karo tum kuyrugu tikamasin.
# soft -> gorev SoftTimeLimitExceeded yakalayip kendini failed isaretleyebilir.
# hard -> soft'u yutan bir sey olursa surec yine de oldurulur.
CELERY_TASK_SOFT_TIME_LIMIT = 600
CELERY_TASK_TIME_LIMIT = 660

# acks_late: mesaj gorev BITTIKTEN sonra onaylanir. Isci is ortasinda olurse
# mesaj kaybolmaz, baska bir isciye yeniden dagitilir. Bedeli, gorevin iki kez
# calisabilmesidir -- bu yuzden tasks.py'deki sil-sonra-yaz idempotanslik
# ZORUNLUDUR, ikisi birbirine baglidir.
CELERY_TASK_ACKS_LATE = True
# Her isci ayni anda tek is tutsun; acks_late ile birlikte olen bir iscinin
# geri dondurdugu is miktari en aza iner.
CELERY_WORKER_PREFETCH_MULTIPLIER = 1

# visibility_timeout: Redis, onaylanmamis bir mesaji bu sure sonunda yeniden
# dagitir. Hard time limit'in (660 sn) rahatca uzerinde secildi -- boylece hala
# calisan bir gorev asla "olmus" sayilip ikinci kez dagitilmaz; yeniden dagitim
# sadece isci gercekten oldugunde devreye girer.
CELERY_BROKER_TRANSPORT_OPTIONS = {"visibility_timeout": 900}
CELERY_RESULT_BACKEND_TRANSPORT_OPTIONS = {"visibility_timeout": 900}

CELERY_BROKER_CONNECTION_RETRY_ON_STARTUP = True
CELERY_WORKER_HIJACK_ROOT_LOGGER = False

# Dedektor cikitisinin KAYIT tabani. Koşunun conf_threshold'u kayda
# pisirilmez: bir tam tarama pahalidir, tek kosudan her esigi cevaplayabilmek
# icin kutular bu sabit tabanla saklanir, esik okuma aninda uygulanir.
DETECTION_STORE_FLOOR = 0.05
