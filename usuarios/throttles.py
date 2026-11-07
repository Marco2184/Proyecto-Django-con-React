"""Small persistent auth limiter shared by every Django worker."""
import hashlib
from datetime import timedelta
from django.conf import settings
from django.contrib.sessions.backends.db import SessionStore
from django.contrib.sessions.models import Session
from django.db import transaction
from django.utils import timezone
from rest_framework.throttling import BaseThrottle


class AuthThrottle(BaseThrottle):
    def allow_request(self, request, view):
        # Read only REMOTE_ADDR. Do not trust client-supplied X-Forwarded-For.
        identity = request.META.get('REMOTE_ADDR', '') + ':' + view.__class__.__name__
        key = 't:' + hashlib.sha256(identity.encode()).hexdigest()[:38]
        now = timezone.now()
        store = SessionStore()
        with transaction.atomic():
            Session.objects.get_or_create(session_key=key, defaults={
                'session_data': store.encode({'count': 0}), 'expire_date': now + timedelta(seconds=60),
            })
            row = Session.objects.select_for_update().get(session_key=key)
            count = row.get_decoded().get('count', 0)
            if row.expire_date <= now:
                count = 0
                row.expire_date = now + timedelta(seconds=60)
            self.delay = max(1, (row.expire_date - now).total_seconds())
            if count >= getattr(settings, 'AUTH_RATE_LIMIT', 30):
                return False
            row.session_data = store.encode({'count': count + 1})
            row.save(update_fields=['session_data', 'expire_date'])
        return True

    def wait(self):
        return self.delay
