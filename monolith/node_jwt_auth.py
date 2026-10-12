import jwt
from django.conf import settings
from rest_framework.authentication import BaseAuthentication
from rest_framework.exceptions import AuthenticationFailed
from django.contrib.auth import get_user_model

class NodeJWTAuthentication(BaseAuthentication):
    def authenticate(self, request):
        header = request.headers.get('Authorization', '')
        if not header.startswith('Bearer '):
            return None
        key = getattr(settings, 'JWT_SHARED_SECRET', '')
        if not key or len(key) < 32:
            raise AuthenticationFailed('JWT no configurado en Django.')
        try:
            payload = jwt.decode(header[7:], key, algorithms=['HS256'], audience='monolith-django', issuer='monolith-node', options={'require':['sub','exp','iat','iss','aud']})
            if payload.get('typ') != 'access':
                raise AuthenticationFailed('Tipo de token inválido.')
            user = get_user_model().objects.get(pk=payload['sub'])
            if not user.is_active or not getattr(user,'cuenta_activa',True):
                raise AuthenticationFailed('Cuenta inactiva.')
            return user, payload
        except (jwt.PyJWTError, ValueError, TypeError, get_user_model().DoesNotExist):
            raise AuthenticationFailed('Token inválido o expirado.')
