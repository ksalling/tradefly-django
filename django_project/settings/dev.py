from .base import *

load_dotenv(BASE_DIR / '.env.dev')

# SECURITY WARNING: keep the secret key used in production secret!
SECRET_KEY = os.getenv('SECRET_KEY')

# Development-specific settings
DEBUG = True

#ALLOWED_HOSTS = os.getenv('DJANGO_ALLOWED_HOSTS','127.0.0.1').split(' ')
#CSRF_TRUSTED_ORIGINS = os.getenv('DJANGO_CSRF_TRUSTED_ORIGINS','https://127.0.0.1').split(' ')

DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.postgresql',
        'NAME': os.getenv('DB_NAME'),
        'USER': os.getenv('DB_USER'),
        'PASSWORD': os.getenv('DB_PASSWORD'),
        'HOST': os.getenv('DB_HOST'),
        'PORT': os.getenv('DB_PORT', ''),
    }
}

