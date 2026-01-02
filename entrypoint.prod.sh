#!/usr/bin/env bash

python3 manage.py collectstatic --noinput --settings=django_project.settings.prod
python3 manage.py migrate --noinput --settings=django_project.settings.prod
python3 -m gunicorn --bind 0.0.0.0:8282 --workers 3 django_project.wsgi:application