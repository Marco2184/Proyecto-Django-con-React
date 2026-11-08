"""Compute Engine production settings; local, Render and Vercel configuration stays unchanged."""
from .settings import *  # noqa: F403
from urllib.parse import urlparse

ROOT_URLCONF = 'monolith.production_urls'
if (urlparse(DATABASE_URL).scheme not in ('postgres', 'postgresql')  # noqa: F405
        or not DEPLOYMENT_HTTPS):  # noqa: F405
    raise ImproperlyConfigured('Production requires PostgreSQL and HTTPS.')  # noqa: F405
if SECRET_KEY == JWT_SHARED_SECRET:  # noqa: F405
    raise ImproperlyConfigured('Django and JWT secrets must differ.')  # noqa: F405
DATABASES['default']['CONN_MAX_AGE'] = 60  # noqa: F405
DATABASES['default']['DISABLE_SERVER_SIDE_CURSORS'] = True  # Neon pooler
DATABASES['default'].setdefault('OPTIONS', {})['connect_timeout'] = 5
SESSION_COOKIE_SECURE = True
CSRF_COOKIE_SECURE = True
SECURE_CONTENT_TYPE_NOSNIFF = True
SECURE_REDIRECT_EXEMPT = [r'^health/$']  # Internal HTTP liveness only.
SECURE_HSTS_INCLUDE_SUBDOMAINS = False
SECURE_HSTS_PRELOAD = False
