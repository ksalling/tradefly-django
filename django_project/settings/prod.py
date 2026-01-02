from .base import *

load_dotenv(BASE_DIR / '.env')

# SECURITY WARNING: keep the secret key used in production secret!
#SECRET_KEY = "django-insecure-w#8yes#)v!3j3%-_5lzq#)ovvaw$wy8o%+orb0d68n!41b%7kb"
SECRET_KEY = os.getenv('SECRET_KEY')

# Development-specific settings
DEBUG = True

ALLOWED_HOSTS = ['*.halfdine.com', '*.traefik.me']
CSRF_TRUSTED_ORIGINS = ['http://*.traefik.me/', 'http://*.halfdine.com', 'https://*.halfdine.com']

DATABASES = {
    'default': dj_database_url.parse(config('DATABASE_URL'))
}

