"""Opt-in Docker-only verification configuration, never the Neon database."""
import os
from urllib.parse import urlparse
from django.core.exceptions import ImproperlyConfigured

if os.environ.get('MONOLITH_DOCKER_VERIFICATION') != '1':
    raise ImproperlyConfigured('Explicit Docker verification mode is required.')
target = urlparse(os.environ.get('TEST_DATABASE_URL', ''))
if target.hostname != 'postgres-test' or target.path != '/monolith_verification':
    raise ImproperlyConfigured('Only the isolated PostgreSQL verification service is permitted.')

from monolith.test_settings import *  # noqa: E402,F403

if DATABASES['default']['ENGINE'] != 'django.db.backends.postgresql':
    raise ImproperlyConfigured('Verification requires PostgreSQL, never a fallback database.')
ROOT_URLCONF = 'docker.verification_urls'
ALLOWED_HOSTS = ['127.0.0.1', 'localhost', 'django', 'testserver']
FRONTEND_URL = 'http://127.0.0.1:13001'
CORS_ALLOWED_ORIGINS = ['http://127.0.0.1:13001', 'http://localhost:13001']
CSRF_TRUSTED_ORIGINS = CORS_ALLOWED_ORIGINS
