"""
ASGI config for django_project project.

It exposes the ASGI callable as a module-level variable named ``application``.

For more information on this file, see
https://docs.djangoproject.com/en/6.0/howto/deployment/asgi/
"""

import os
from dotenv import load_dotenv

from django.core.asgi import get_asgi_application

load_dotenv('.env')

#os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'django_project.settings')
os.environ.setdefault('DJANGO_SETTINGS_MODULE', os.getenv('DJANGO_SETTINGS_MODULE'))

application = get_asgi_application()
