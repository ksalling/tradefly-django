#!/usr/bin/env bash

python3 manage.py collectstatic --noinput
python3 manage.py migrate --noinput
python3 -m gunicorn --bind 0.0.0.0:8000 --workers 3 django_project.wsgi:application
python3 echo "Server Start"