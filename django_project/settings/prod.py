from .base import *

# Development-specific settings
DEBUG = True

# SECURITY WARNING: keep the secret key used in production secret!
SECRET_KEY = "django-insecure-w#8yes#)v!3j3%-_5lzq#)ovvaw$wy8o%+orb0d68n!41b%7kb"

ALLOWED_HOSTS = ["localhost"]
CSRF_TRUSTED_ORIGINS = "http://localhost:8000"

DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.postgresql',
        'NAME': 'tf',
        'USER': 'tradefly',
        'PASSWORD': '6817*erxesAve',
        'HOST': 'mg0wss80kg8c0cks4skckc44:5432/postgres',
        'PORT': '5432',
    }
}

