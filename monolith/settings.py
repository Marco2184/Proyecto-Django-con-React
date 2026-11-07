from pathlib import Path
from decouple import config, Csv
import dj_database_url
import secrets
from django.core.exceptions import ImproperlyConfigured

BASE_DIR = Path(__file__).resolve().parent.parent

DEBUG = config('DEBUG', default=False, cast=bool)
SECRET_KEY = config('SECRET_KEY', default='')
if not SECRET_KEY:
    if not DEBUG:
        raise ImproperlyConfigured('Configura SECRET_KEY para ejecutar sin DEBUG.')
    SECRET_KEY = secrets.token_urlsafe(48)
if not DEBUG and (len(SECRET_KEY) < 32 or SECRET_KEY == 'monolith-2025-dev-key'):
    raise ImproperlyConfigured('SECRET_KEY debe ser un secreto aleatorio de al menos 32 caracteres.')

ALLOWED_HOSTS = config(
    'ALLOWED_HOSTS',
    default='localhost,127.0.0.1,django',
    cast=Csv()
)
if not DEBUG and '*' in ALLOWED_HOSTS:
    raise ImproperlyConfigured('ALLOWED_HOSTS no permite comodines en despliegue.')
AUTHENTICATION_BACKENDS = ['usuarios.backends.ActiveAccountBackend']

INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',

    'rest_framework',
    'rest_framework.authtoken',
    'corsheaders',

    'usuarios',
    'productos',
    'carrito',
]

MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'corsheaders.middleware.CorsMiddleware',

    # Necesario para servir archivos estáticos en Render
    'whitenoise.middleware.WhiteNoiseMiddleware',

    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.locale.LocaleMiddleware',
    'monolith.locale_middleware.ApiLanguageMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
]

CORS_ALLOWED_ORIGINS = config(
    'CORS_ALLOWED_ORIGINS',
    default='http://localhost:3000,http://localhost:5173,http://127.0.0.1:3000,http://127.0.0.1:5173',
    cast=Csv()
)

CSRF_TRUSTED_ORIGINS = config(
    'CSRF_TRUSTED_ORIGINS',
    default='http://localhost:3000,http://localhost:5173,http://127.0.0.1:3000,http://127.0.0.1:5173',
    cast=Csv()
)

JWT_SHARED_SECRET = config('JWT_SHARED_SECRET', default='')
if not DEBUG and len(JWT_SHARED_SECRET) < 32:
    raise ImproperlyConfigured('Configura JWT_SHARED_SECRET con al menos 32 caracteres.')

REST_FRAMEWORK = {
    'EXCEPTION_HANDLER': 'monolith.exceptions.api_exception_handler',
    'DEFAULT_PARSER_CLASSES': [
        'monolith.parsers.ObjectJSONParser',
        'rest_framework.parsers.FormParser',
        'rest_framework.parsers.MultiPartParser',
    ],
    'DEFAULT_PAGINATION_CLASS': 'rest_framework.pagination.PageNumberPagination',
    'PAGE_SIZE': 20,
    'DEFAULT_AUTHENTICATION_CLASSES': [
        'monolith.node_jwt_auth.NodeJWTAuthentication',
        'rest_framework.authentication.TokenAuthentication',
        'rest_framework.authentication.SessionAuthentication',
    ],
}

ROOT_URLCONF = 'monolith.urls'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [
            BASE_DIR / 'templates'
        ],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.debug',
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
            ]
        },
    }
]

WSGI_APPLICATION = 'monolith.wsgi.application'

DATABASE_URL = config('DATABASE_URL', default='')

if DATABASE_URL:
    DATABASES = {
        'default': dj_database_url.config(
            default=DATABASE_URL,
            conn_max_age=600,
            ssl_require=True
        )
    }
else:
    DATABASES = {
        'default': {
            'ENGINE': 'django.db.backends.sqlite3',
            'NAME': BASE_DIR / 'db.sqlite3',
        }
    }
DATABASES['default']['CONN_HEALTH_CHECKS'] = True

AUTH_PASSWORD_VALIDATORS = [
    {
        'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator'
    },
    {
        'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator'
    },
    {
        'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator'
    },
    {
        'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator'
    },
]

LANGUAGE_CODE = 'es'

LANGUAGES = [
    ('es', 'Español'),
    ('en', 'English'),
]

LOCALE_PATHS = [
    BASE_DIR / 'locale'
]

TIME_ZONE = 'America/Lima'

USE_I18N = True

USE_TZ = True

STATIC_URL = '/static/'

# Esto corrige el error de Render:
# "STATIC_ROOT setting to a filesystem path"
STATIC_ROOT = BASE_DIR / 'staticfiles'

# Solo agrega STATICFILES_DIRS si la carpeta static existe
STATIC_DIR = BASE_DIR / 'static'

if STATIC_DIR.exists():
    STATICFILES_DIRS = [
        STATIC_DIR
    ]

STORAGES = {
    'default': {'BACKEND': 'django.core.files.storage.FileSystemStorage'},
    'staticfiles': {'BACKEND': 'whitenoise.storage.CompressedManifestStaticFilesStorage'},
}

CORS_ALLOW_CREDENTIALS = True
from corsheaders.defaults import default_headers
CORS_ALLOW_HEADERS = [*default_headers, 'idempotency-key']
DEPLOYMENT_HTTPS = config('DEPLOYMENT_HTTPS', default=False, cast=bool)
SESSION_COOKIE_SECURE = config('SESSION_COOKIE_SECURE', default=DEPLOYMENT_HTTPS, cast=bool)
CSRF_COOKIE_SECURE = config('CSRF_COOKIE_SECURE', default=DEPLOYMENT_HTTPS, cast=bool)
SECURE_SSL_REDIRECT = DEPLOYMENT_HTTPS
SECURE_HSTS_SECONDS = 31536000 if DEPLOYMENT_HTTPS else 0
SECURE_REFERRER_POLICY = 'same-origin'
if DEPLOYMENT_HTTPS:
    SECURE_PROXY_SSL_HEADER = ('HTTP_X_FORWARDED_PROTO', 'https')
SESSION_COOKIE_SAMESITE = 'Lax'
CSRF_COOKIE_SAMESITE = 'Lax'

MEDIA_URL = '/media/'

MEDIA_ROOT = BASE_DIR / 'media'

DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

AUTH_USER_MODEL = 'usuarios.Usuario'

LOGIN_URL = '/login/'

LOGIN_REDIRECT_URL = '/dashboard/'

LOGOUT_REDIRECT_URL = '/login/'

# Email para verificación, recuperación y bienvenida.
# Soporta dos formatos:
# 1. EMAIL_HOST_USER / EMAIL_HOST_PASSWORD
# 2. MONOLITH_EMAIL / MONOLITH_PASSWORD
EMAIL_BACKEND = "django.core.mail.backends.smtp.EmailBackend"

EMAIL_HOST = config("EMAIL_HOST", default="smtp.gmail.com")
EMAIL_PORT = config("EMAIL_PORT", default=587, cast=int)

EMAIL_USE_TLS = config("EMAIL_USE_TLS", default=True, cast=bool)
EMAIL_USE_SSL = config("EMAIL_USE_SSL", default=False, cast=bool)

EMAIL_TIMEOUT = config("EMAIL_TIMEOUT", default=30, cast=int)

EMAIL_HOST_USER = config("EMAIL_HOST_USER", default="") or config("MONOLITH_EMAIL", default="")
EMAIL_HOST_PASSWORD = config("EMAIL_HOST_PASSWORD", default="") or config("MONOLITH_PASSWORD", default="")

# Auto conserva OAuth cuando está completo y permite reutilizar SMTP existente.
MONOLITH_EMAIL_PROVIDER = config('MONOLITH_EMAIL_PROVIDER', default='auto')
GMAIL_CLIENT_ID = config('GMAIL_CLIENT_ID', default='')
GMAIL_CLIENT_SECRET = config('GMAIL_CLIENT_SECRET', default='')
GMAIL_REFRESH_TOKEN = config('GMAIL_REFRESH_TOKEN', default='')
GMAIL_SENDER_EMAIL = config('GMAIL_SENDER_EMAIL', default='')

DEFAULT_FROM_EMAIL = config(
    "DEFAULT_FROM_EMAIL",
    default=f"Monolith <{EMAIL_HOST_USER}>"
)

FRONTEND_URL = config("FRONTEND_URL", default="http://localhost:3000")
