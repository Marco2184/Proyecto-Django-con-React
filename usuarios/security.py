from django.utils.translation import gettext as translate
"""Persistent security state in Django's existing signed session table.

No raw passwords, bearer tokens or email tokens are persisted here.
Row locks serialize consumption/rotation across processes.
"""
import hashlib
import secrets
import uuid
from datetime import timedelta

from django.conf import settings
from django.contrib.sessions.backends.db import SessionStore
from django.contrib.sessions.models import Session
from django.core import signing
from django.db import transaction
from django.utils import timezone
from django.utils.crypto import constant_time_compare
from rest_framework.exceptions import AuthenticationFailed, ValidationError

from .models import Usuario

EMAIL_TTLS = {'verify': 86400, 'reset': 1800}


def _write(key, data, expires):
    Session.objects.update_or_create(session_key=key, defaults={
        'session_data': SessionStore().encode(data), 'expire_date': expires,
    })


def _email_key(uid, purpose):
    return 'e:' + hashlib.sha256(f'{uid}:{purpose}'.encode()).hexdigest()[:38]


def issue_email_token(user, purpose):
    ttl = EMAIL_TTLS[purpose]
    token = signing.dumps({'uid': user.pk, 'purpose': purpose, 'nonce': secrets.token_urlsafe(24)}, salt='monolith.email.' + purpose)
    _write(_email_key(user.pk, purpose), {
        'digest': hashlib.sha256(token.encode()).hexdigest(),
        'epoch': str(user.token_verificacion), 'email': user.email,
    }, timezone.now() + timedelta(seconds=ttl))
    return token


def email_token_user(token, purpose, lock=False):
    try:
        payload = signing.loads(token, salt='monolith.email.' + purpose, max_age=EMAIL_TTLS[purpose])
        if payload.get('purpose') != purpose:
            raise ValueError
        users = Usuario.objects.select_for_update() if lock else Usuario.objects
        user = users.get(pk=payload['uid'], is_active=True, cuenta_activa=True)
        rows = Session.objects.select_for_update() if lock else Session.objects
        row = rows.get(session_key=_email_key(user.pk, purpose), expire_date__gt=timezone.now())
        data = row.get_decoded()
        if not (constant_time_compare(data.get('digest', ''), hashlib.sha256(token.encode()).hexdigest())
                and data.get('epoch') == str(user.token_verificacion) and data.get('email') == user.email):
            raise ValueError
        return user, row
    except (signing.BadSignature, ValueError, TypeError, KeyError, Usuario.DoesNotExist, Session.DoesNotExist):
        raise ValidationError({'detail': translate('Enlace inválido o expirado.')})


@transaction.atomic
def consume_email_token(token, purpose, password=None):
    user, row = email_token_user(token, purpose, lock=True)
    if purpose == 'verify':
        user.email_verificado = True
        user.save(update_fields=['email_verificado'])
    else:
        from django.contrib.auth.password_validation import validate_password
        from django.core.exceptions import ValidationError as DjangoValidationError
        try:
            validate_password(password, user)
        except DjangoValidationError as exc:
            raise ValidationError({'password1': exc.messages})
        user.set_password(password)
        user.save(update_fields=['password'])
    row.delete()
    return user


def revoke_user(user):
    user.token_verificacion = uuid.uuid4()
    user.save(update_fields=['token_verificacion'])
    from rest_framework.authtoken.models import Token
    Token.objects.filter(user=user).delete()


def _session_key(sid):
    try:
        return 'j:' + uuid.UUID(sid).hex
    except (ValueError, TypeError, AttributeError):
        raise AuthenticationFailed(translate('Sesión inválida o revocada.'))


def session_claims(user, sid, jti):
    return {'id': user.pk, 'sid': sid, 'token_version': str(user.token_verificacion), 'jti': jti}


@transaction.atomic
def create_jwt_session(user):
    user = Usuario.objects.select_for_update().get(pk=user.pk)
    if not user.is_active or not user.cuenta_activa:
        raise AuthenticationFailed(translate('Cuenta inactiva.'))
    sid, jti = str(uuid.uuid4()), secrets.token_urlsafe(32)
    _write(_session_key(sid), {
        'uid': user.pk, 'epoch': str(user.token_verificacion),
        'jti_hash': hashlib.sha256(jti.encode()).hexdigest(),
    }, timezone.now() + timedelta(days=7))
    return session_claims(user, sid, jti)


def validate_jwt_session(user, payload, lock=False):
    if (not user.is_active or not user.cuenta_activa or
            payload.get('token_version') != str(user.token_verificacion)):
        raise AuthenticationFailed(translate('Sesión inválida o revocada.'))
    rows = Session.objects.select_for_update() if lock else Session.objects
    try:
        row = rows.get(session_key=_session_key(payload.get('sid')), expire_date__gt=timezone.now())
    except Session.DoesNotExist:
        raise AuthenticationFailed(translate('Sesión inválida o revocada.'))
    data = row.get_decoded()
    if data.get('uid') != user.pk or data.get('epoch') != str(user.token_verificacion):
        raise AuthenticationFailed(translate('Sesión inválida o revocada.'))
    return row, data


def rotate_jwt_session(payload):
    # Do not raise until after commit: replay must persist revocation.
    invalid = False
    with transaction.atomic():
        try:
            user = Usuario.objects.select_for_update().get(pk=payload.get('sub'))
        except (Usuario.DoesNotExist, ValueError, TypeError):
            raise AuthenticationFailed(translate('Sesión inválida o revocada.'))
        row, data = validate_jwt_session(user, payload, lock=True)
        if not isinstance(payload.get('jti'), str) or not constant_time_compare(
                data.get('jti_hash', ''), hashlib.sha256(payload['jti'].encode()).hexdigest()):
            row.delete()
            invalid = True
        else:
            jti = secrets.token_urlsafe(32)
            data['jti_hash'] = hashlib.sha256(jti.encode()).hexdigest()
            row.session_data = SessionStore().encode(data)
            row.save(update_fields=['session_data'])
            result = session_claims(user, payload['sid'], jti)
    if invalid:
        raise AuthenticationFailed(translate('Refresh reutilizado; sesión revocada.'))
    return result
