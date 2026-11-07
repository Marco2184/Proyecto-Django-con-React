"""Isolated CI/local verification settings. Never connects to the application DB."""
import os
from urllib.parse import urlparse
from .settings import *  # noqa: F403

test_url = os.environ.get('TEST_DATABASE_URL', '')
if test_url:
    if urlparse(test_url).hostname not in ('localhost', '127.0.0.1', 'postgres-test'):
        raise RuntimeError('TEST_DATABASE_URL must refer to an isolated local database')
    DATABASES = {'default': dj_database_url.parse(test_url, conn_max_age=0)}
else:
    DATABASES = {'default': {'ENGINE': 'django.db.backends.sqlite3', 'NAME': ':memory:'}}
if os.environ.get('MONOLITH_BROWSER_TEST')=='1':
    DATABASES = {'default': {'ENGINE':'django.db.backends.sqlite3','NAME':BASE_DIR/'.browser-test.sqlite3'}}
JWT_SHARED_SECRET = os.environ.get('TEST_JWT_SHARED_SECRET','ci-only-shared-secret-00000000000000000000000')
ALLOWED_HOSTS = ['testserver', 'localhost', '127.0.0.1']
EMAIL_BACKEND = 'django.core.mail.backends.locmem.EmailBackend'
CACHES = {'default': {'BACKEND': 'django.core.cache.backends.locmem.LocMemCache'}}
STORAGES = {'default': {'BACKEND': 'django.core.files.storage.FileSystemStorage'}, 'staticfiles': {'BACKEND': 'django.contrib.staticfiles.storage.StaticFilesStorage'}}
SECURE_SSL_REDIRECT = False
PASSWORD_HASHERS = ['django.contrib.auth.hashers.MD5PasswordHasher']
