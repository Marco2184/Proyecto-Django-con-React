from django.utils.translation import gettext as translate
"""Node-only callbacks authenticated by short-lived, purpose-bound JWTs."""
import jwt
import hashlib
from django.utils.crypto import constant_time_compare
from django.conf import settings
from django.contrib.auth import authenticate
from rest_framework.authentication import BaseAuthentication
from rest_framework.decorators import api_view, authentication_classes, permission_classes
from rest_framework.exceptions import AuthenticationFailed
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from .api import LoginSerializer, _user_payload
from .security import create_jwt_session, rotate_jwt_session, revoke_user, validate_jwt_session
from .models import Usuario
from django.db import transaction, IntegrityError
from django.contrib.sessions.models import Session
from django.contrib.sessions.backends.db import SessionStore
from django.utils import timezone
from datetime import timedelta
from monolith.messages import message
from rest_framework.exceptions import ValidationError
from rest_framework.decorators import throttle_classes
from .throttles import AuthThrottle


class NodeServiceAuthentication(BaseAuthentication):
    def authenticate(self, request):
        token = request.headers.get('Authorization', '').removeprefix('Bearer ')
        try:
            payload = jwt.decode(token, settings.JWT_SHARED_SECRET, algorithms=['HS256'],
                                 issuer='monolith-node', audience='monolith-internal',
                                 options={'require': ['exp', 'iat', 'typ', 'purpose']})
            if payload['typ'] != 'service' or payload['purpose'] != request.path or payload['exp'] - payload['iat'] > 30:
                raise ValueError
            if not constant_time_compare(payload.get('body_hash', ''), hashlib.sha256(request.body).hexdigest()):
                raise ValueError
        except (jwt.PyJWTError, ValueError, TypeError):
            raise AuthenticationFailed(translate('Servicio no autorizado.'))
        return None

    def authenticate_header(self, request):
        return 'Bearer'


@api_view(['POST'])
@authentication_classes([NodeServiceAuthentication])
@permission_classes([AllowAny])
def node_login(request):
    serializer = LoginSerializer(data=request.data)
    serializer.is_valid(raise_exception=True)
    user = authenticate(request, username=serializer.validated_data['email'], password=serializer.validated_data['password'])
    if not user or not user.cuenta_activa:
        raise AuthenticationFailed(translate('Credenciales inválidas o cuenta inactiva.'))
    return Response({'user': _user_payload(user), 'session': create_jwt_session(user)})


@api_view(['POST'])
@authentication_classes([NodeServiceAuthentication])
@permission_classes([AllowAny])
@throttle_classes([AuthThrottle])
def node_register(request):
    """A retry can recover its own registration with the same password/key.

    The signed session table stores only a user ID, never passwords or tokens.
    Lock ordering is receipt -> user, consistently with checkout receipts.
    """
    import uuid
    from .api import RegisterSerializer, _send_mail_safe, FRONTEND_URL
    from .security import issue_email_token
    try:
        key = str(uuid.UUID(request.data.get('request_id', '')))
    except (ValueError, TypeError, AttributeError):
        raise ValidationError({'request_id': message('Identificador de registro inválido.', 'Invalid registration identifier.')})
    email = str(request.data.get('email', '')).strip().lower()
    receipt_key = 'r:' + hashlib.sha256(key.encode()).hexdigest()[:38]
    fresh = False
    with transaction.atomic():
        Session.objects.get_or_create(session_key=receipt_key, defaults={'session_data': SessionStore().encode({}), 'expire_date': timezone.now()+timedelta(days=1)})
        receipt = Session.objects.select_for_update().get(session_key=receipt_key)
        previous = receipt.get_decoded()
        if previous:
            user = Usuario.objects.filter(pk=previous.get('uid'), email__iexact=email).first()
            password = request.data.get('password1')
            if not user or not isinstance(password, str) or not user.check_password(password):
                raise ValidationError({'detail': message('El registro no se puede repetir con otros datos.', 'Registration cannot be retried with different details.')})
        else:
            serializer = RegisterSerializer(data=request.data)
            serializer.is_valid(raise_exception=True)
            try:
                with transaction.atomic(): user = serializer.save()
            except IntegrityError:
                raise ValidationError({'email': message('Este correo ya está registrado.', 'This email is already registered.')})
            receipt.session_data = SessionStore().encode({'uid': user.pk})
            receipt.save(update_fields=['session_data'])
            fresh = True
        session = create_jwt_session(user)
        if fresh:
            verification = issue_email_token(user, 'verify')
            url = f'{FRONTEND_URL}/verify/{verification}'
            subject = message('Verifica tu correo — Monolith', 'Verify your email — Monolith')
            body = message('Verifica tu correo para completar compras: ', 'Verify your email to complete purchases: ') + url
            transaction.on_commit(lambda: _send_mail_safe(subject, body, user.email))
    return Response({'user': _user_payload(user), 'session': session}, status=201 if fresh else 200)


@api_view(['POST'])
@authentication_classes([NodeServiceAuthentication])
@permission_classes([AllowAny])
def node_refresh(request):
    return Response({'session': rotate_jwt_session(request.data)})


@api_view(['POST'])
@authentication_classes([NodeServiceAuthentication])
@permission_classes([AllowAny])
def node_logout(request):
    try:
        user = Usuario.objects.get(pk=request.data.get('sub'))
    except (Usuario.DoesNotExist, TypeError, ValueError):
        raise AuthenticationFailed(translate('Sesión inválida.'))
    validate_jwt_session(user, request.data)
    revoke_user(user)
    return Response({'message': translate('Sesiones revocadas.')})
