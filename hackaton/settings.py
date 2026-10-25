
"""
Настройки Django для проекта «Листория».
"""

import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent

# Для локальной разработки.
# Перед публичным запуском создай постоянный секретный ключ
# в переменной окружения DJANGO_SECRET_KEY.
SECRET_KEY = os.environ.get(
    "DJANGO_SECRET_KEY",
    "local-development-only-change-before-public-release-2026",
)

DEBUG = os.environ.get("DJANGO_DEBUG", "True") == "True"

ALLOWED_HOSTS = [
    "127.0.0.1",
    "localhost",
    "172.19.174.44",
    ".trycloudflare.com",
]

INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "wibecode",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

ROOT_URLCONF = "hackaton.urls"

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

WSGI_APPLICATION = "hackaton.wsgi.application"

DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.sqlite3",
        "NAME": BASE_DIR / "db.sqlite3",
    }
}

AUTH_PASSWORD_VALIDATORS = [
    {
        "NAME": (
            "django.contrib.auth.password_validation."
            "UserAttributeSimilarityValidator"
        ),
    },
    {
        "NAME": (
            "django.contrib.auth.password_validation."
            "MinimumLengthValidator"
        ),
    },
    {
        "NAME": (
            "django.contrib.auth.password_validation."
            "CommonPasswordValidator"
        ),
    },
    {
        "NAME": (
            "django.contrib.auth.password_validation."
            "NumericPasswordValidator"
        ),
    },
]

LANGUAGE_CODE = "ru-ru"
TIME_ZONE = "Europe/Moscow"
USE_I18N = True
USE_TZ = True

# ======================================
# ИЗОБРАЖЕНИЯ
# ======================================

STATIC_URL = "/static/"

STATIC_ROOT = BASE_DIR / "staticfiles"

# Используем именно существующую папку images.
# Ничего переносить не требуется.
STATICFILES_DIRS = [
    (
        "listoria_images",
        BASE_DIR / "wibecode" / "templates" / "wibecode" / "images",
    ),
]

# ======================================
# СЕССИИ
# ======================================

SESSION_ENGINE = "django.contrib.sessions.backends.file"
SESSION_COOKIE_AGE = 60 * 60 * 24 * 7
SESSION_SAVE_EVERY_REQUEST = True
SESSION_COOKIE_HTTPONLY = True
SESSION_COOKIE_SAMESITE = "Lax"

# ======================================
# CLOUDFLARE
# ======================================

CSRF_TRUSTED_ORIGINS = [
    'http://listoria.art',
    'http://localhost:8000',
    'http://127.0.0.1:8000',
]


SECURE_PROXY_SSL_HEADER = (
    "HTTP_X_FORWARDED_PROTO",
    "https",
)

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

# ============================================================
# Настройки генерации историй
# ============================================================

# Режим работы: "local" (Ollama на ноутбуке) или "server" (Selectel Token Factory)
STORY_ENGINE = "local"   # на сервере поменять на "server"

# --- Ollama (локально) ---
OLLAMA_URL = "http://127.0.0.1:11434/api/chat"
OLLAMA_MODEL = "qwen3:4b-instruct"

# --- Selectel Token Factory (сервер) ---
SELECTEL_BASE_URL = "https://api.tf.selcloud.ru/v1"
SELECTEL_MODEL = "qwen3.8-flash-next"
SELECTEL_API_KEY = "1234512345"   # или лучше брать из os.environ