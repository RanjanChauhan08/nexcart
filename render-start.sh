#!/usr/bin/env bash
# exit on error
set -o errexit

python manage.py migrate
python manage.py createsuperuser_from_env
gunicorn temp1.wsgi:application
