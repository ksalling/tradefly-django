from .base import *

# Development-specific settings
DEBUG = True

# SECURITY WARNING: keep the secret key used in production secret!
SECRET_KEY = ${{SECRET_KEY}}

ALLOWED_HOSTS = ${{DJANGO_ALLOWED_HOSTS}}
CSRF_TRUSTED_ORIGINS = ${{DJANGO_CSRF_TRUSTED_ORIGINS}}

DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.postgresql',
        'NAME': ${{DB_NAME}},
        'USER': ${{DB_USER}},
        'PASSWORD': ${{DB_PASSWORD}},
        'HOST': ${{DB_HOST}},
        'PORT': ${{DB_PORT}},
    }
}

