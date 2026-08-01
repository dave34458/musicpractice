web: gunicorn config.wsgi:application --workers 1 --threads 4 --timeout 0
release: python manage.py migrate --noinput && python manage.py collectstatic --noinput
