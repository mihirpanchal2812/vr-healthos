import os
from pathlib import Path
from dotenv import load_dotenv
import dj_database_url

BASE_DIR = Path(__file__).resolve().parent.parent

load_dotenv(BASE_DIR / '.env')

SECRET_KEY = 'django-insecure-vr-healthos-dev-key-change-in-production'

DEBUG = True

ALLOWED_HOSTS = ['*']

INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    'core',
]

MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'whitenoise.middleware.WhiteNoiseMiddleware',  # added for production static serving
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
]

ROOT_URLCONF = 'healthos.urls'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [BASE_DIR / 'templates'],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.debug',
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
            ],
        },
    },
]

WSGI_APPLICATION = 'healthos.wsgi.application'


#-----------------------------------------------------------------------------------
# PRODUCTION DATABASE CONFIGURATION (UNCOMMENT FOR PRODUCTION DEPLOYMENT)
#-----------------------------------------------------------------------------------

DATABASES = {
    'default': dj_database_url.config(env='ON_DATABASE_URL', conn_max_age=600)
}

#-----------------------------------------------------------------------------------
# LOCAL DATABASE CONFIGURATION (UNCOMMENT FOR LOCAL DEVELOPMENT)
#-----------------------------------------------------------------------------------

# DATABASES = {
#     'default': {
#         'ENGINE': 'django.db.backends.postgresql',
#         'NAME': os.environ['DATABASE_URL'].split('/')[-1],
#         'USER': os.environ['DATABASE_URL'].split('://')[1].split(':')[0],
#         'PASSWORD': os.environ['DATABASE_URL'].split(':')[2].split('@')[0],
#         'HOST': os.environ['DATABASE_URL'].split('@')[1].split(':')[0],
#         'PORT': os.environ['DATABASE_URL'].split(':')[-1].split('/')[0],
#     }
# }

AUTH_USER_MODEL = 'core.User'

AUTH_PASSWORD_VALIDATORS = []

LANGUAGE_CODE = 'en-us'
TIME_ZONE = 'Asia/Kolkata'
USE_I18N = True
USE_TZ = True


#-----------------------------------------------------------------------------------
# STATIC FILES CONFIGURATION
#-----------------------------------------------------------------------------------

STATIC_URL = '/static/'

STATICFILES_DIRS = [
    BASE_DIR / 'static'
]

STATIC_ROOT = BASE_DIR / 'staticfiles'

STATICFILES_STORAGE = "whitenoise.storage.CompressedManifestStaticFilesStorage"


#-----------------------------------------------------------------------------------
# MEDIA FILES CONFIGURATION
#-----------------------------------------------------------------------------------

MEDIA_URL = '/media/'
MEDIA_ROOT = BASE_DIR / 'media'


DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

LOGIN_URL = '/login/'
LOGIN_REDIRECT_URL = '/'
LOGOUT_REDIRECT_URL = '/login/'