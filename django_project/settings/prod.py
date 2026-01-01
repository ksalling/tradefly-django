from .base import *

# Development-specific settings
DEBUG = True

# SECURITY WARNING: keep the secret key used in production secret!
SECRET_KEY = django-insecure-w#8yes#)v!3j3%-_5lzq#)ovvaw$wy8o%+orb0d68n!41b%7kb

ALLOWED_HOSTS = ${{DJANGO_ALLOWED_HOSTS}}
CSRF_TRUSTED_ORIGINS = ${{DJANGO_CSRF_TRUSTED_ORIGINS}}

DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.postgresql',
        'NAME': 'tf',
        'USER': 'tradefly',
        'PASSWORD': '6817*erxesAve',
        'HOST': 'tradefly-tradefly-6oc18b',
        'PORT': '5432',
    }
}

