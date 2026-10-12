
import jwt

from django.conf import settings
from django.contrib.auth import get_user_model
from rest_framework.authentication import BaseAuthentication
from rest_framework.exceptions import AuthenticationFailed


class NodeJWTAuthentication(BaseAuthentication):

    def authenticate(self, request):
        header = request.headers.get('Authorization', '')

        if not header:
            return None

        if not header.startswith('Bearer '):
            return None

        token = header[7:].strip()

        if not token:
            raise AuthenticationFailed(
                'Token de autenticación vacío.'
            )

        secret = getattr(
            settings,
            'JWT_SHARED_SECRET',
            ''
        )

        if not secret or len(secret) < 32:
            raise AuthenticationFailed(
                'JWT no configurado en Django.'
            )

        try:
            payload = jwt.decode(
                token,
                secret,
                algorithms=['HS256'],
                audience='monolith-django',
                issuer='monolith-node',
                options={
                    'require': [
                        'sub',
                        'exp',
                        'iat',
                        'iss',
                        'aud'
                    ]
                }
            )

            if payload.get('typ') != 'access':
                raise AuthenticationFailed(
                    'Tipo de token inválido.'
                )

            user_id = payload.get('sub')

            if (
                not isinstance(user_id, (str, int))
                or isinstance(user_id, bool)
                or not str(user_id).isdigit()
                or int(user_id) <= 0
            ):
                raise AuthenticationFailed(
                    'Identificador de usuario inválido.'
                )

            issued_at = payload.get('iat')
            expires_at = payload.get('exp')

            if (
                isinstance(issued_at, bool)
                or isinstance(expires_at, bool)
                or not isinstance(issued_at, (int, float))
                or not isinstance(expires_at, (int, float))
                or expires_at <= issued_at
            ):
                raise AuthenticationFailed(
                    'Fechas del token inválidas.'
                )

            User = get_user_model()

            try:
                user = User.objects.get(pk=int(user_id))
            except (User.DoesNotExist, ValueError, TypeError):
                raise AuthenticationFailed(
                    'Token inválido o expirado.'
                )

            if not user.is_active:
                raise AuthenticationFailed(
                    'Cuenta inactiva.'
                )

            if not getattr(user, 'cuenta_activa', True):
                raise AuthenticationFailed(
                    'Cuenta inactiva.'
                )

            return (user, payload)

        except jwt.PyJWTError:
            raise AuthenticationFailed(
                'Token inválido o expirado.'
            )

    def authenticate_header(self, request):
        return 'Bearer'
