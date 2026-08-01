from pathlib import Path
import os

BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = Path(os.environ.get('RAILWAY_DATA_DIR', BASE_DIR))

SECRET_KEY = os.environ.get('DJANGO_SECRET_KEY', 'django-insecure-nq^f5s+@p2h+k8-u$ht15n!9@oy=-ri8pb&9gkya6+_#2dyett')
DEBUG = os.environ.get('DJANGO_DEBUG', 'true').lower() == 'true'
ALLOWED_HOSTS = [h.strip() for h in os.environ.get('DJANGO_ALLOWED_HOSTS', '').split(',') if h.strip()]
CSRF_TRUSTED_ORIGINS = [h.strip() for h in os.environ.get('DJANGO_CSRF_TRUSTED_ORIGINS', '').split(',') if h.strip()]

INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    'accounts',
    'backingtracks',
    'chordfinder',
    'midis',
]

MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'whitenoise.middleware.WhiteNoiseMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
    'config.middleware.DevNoCacheMiddleware',
]

ROOT_URLCONF = 'config.urls'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [BASE_DIR / 'templates'],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
            ],
        },
    },
]

WSGI_APPLICATION = 'config.wsgi.application'

DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.sqlite3',
        'NAME': DATA_DIR / 'db.sqlite3',
    }
}

AUTH_PASSWORD_VALIDATORS = [
    {'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator'},
    {'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator'},
    {'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator'},
    {'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator'},
]

LANGUAGE_CODE = 'en-us'
TIME_ZONE = 'UTC'
USE_I18N = True
USE_TZ = True

STATIC_URL = 'static/'
STATICFILES_DIRS = [BASE_DIR / 'static']
STATIC_ROOT = BASE_DIR / 'staticfiles'

MEDIA_URL = 'media/'
MEDIA_ROOT = DATA_DIR / 'media'

# MuScriptor MIDI transcription model weights (local safetensors path).
MUSCRIPTOR_MODEL_PATH = os.environ.get('MUSCRIPTOR_MODEL_PATH', BASE_DIR / 'models' / 'muscriptor-small.safetensors')

LOGIN_REDIRECT_URL = '/'
LOGOUT_REDIRECT_URL = '/'
LOGIN_URL = '/login/'

EMAIL_BACKEND = 'django.core.mail.backends.console.EmailBackend'

DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'
