web: python manage.py migrate --noinput && python manage.py collectstatic --noinput && gunicorn config.wsgi:application --workers 1 --threads 4 --timeout 0
