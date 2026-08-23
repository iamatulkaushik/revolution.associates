#!/usr/bin/env bash
set -o errexit

pip install -r requirements.txt
#python manage.py migrate Sapp zero
#python manage.py migrate Aapp zero
#python manage.py migrate Capp zero
#python manage.py migrate Cxapp zero
python manage.py collectstatic --no-input
#python manage.py makemigrations --no-input
python manage.py migrate --no-input
python manage.py create_default_superuser
