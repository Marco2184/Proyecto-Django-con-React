import uuid
import threading
from django.conf import settings
from django.contrib.auth import authenticate
from django.core.mail import send_mail
from django.utils.translation import activate
from rest_framework import serializers, status
from rest_framework.authtoken.models import Token
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from decouple import config
from .models import Usuario, DireccionEnvio, Pedido

import firebase_admin
from firebase_admin import credentials, auth as firebase_auth

# Inicializar Firebase Admin (solo una vez)
if not firebase_admin._apps:
    cred = credentials.Certificate({
        "type": "service_account",
        "project_id": config('FIREBASE_PROJECT_ID', default=''),
        "private_key_id": config('FIREBASE_PRIVATE_KEY_ID', default=''),
        "private_key": config('FIREBASE_PRIVATE_KEY', default='').replace('\\n', '\n'),
        "client_email": config('FIREBASE_CLIENT_EMAIL', default=''),
        "client_id": config('FIREBASE_CLIENT_ID', default=''),
        "auth_uri": "https://accounts.google.com/o/oauth2/auth",
        "token_uri": "https://oauth2.googleapis.com/token",
    })
    firebase_admin.initialize_app(cred)


def _verify_firebase_token(request):
    auth_header = request.headers.get('Authorization', '')
    if not auth_header.startswith('Firebase '):
        return None
    id_token = auth_header.split('Firebase ')[1]
    try:
        return firebase_auth.verify_id_token(id_token)
    except Exception:
        return None


@api_view(['POST'])
@permission_classes([AllowAny])
def firebase_register(request):
    decoded = _verify_firebase_token(request)
    if not decoded:
        return Response({'detail': 'Token Firebase inválido.'}, status=status.HTTP_401_UNAUTHORIZED)
    
    email = decoded.get('email')
    firebase_uid = decoded.get('uid')
    nombre = request.data.get('nombre', '')
    telefono = request.data.get('telefono', '')

    if Usuario.objects.filter(email=email).exists():
        user = Usuario.objects.get(email=email)
    else:
        user = Usuario.objects.create_user(
            email=email,
            password=None,
            nombre=nombre,
            telefono=telefono,
        )
        user.email_verificado = True
        user.firebase_uid = firebase_uid
        user.save()

    token, _ = Token.objects.get_or_create(user=user)
    return Response({
        'token': token.key,
        'user': _user_payload(user),
        'message': 'Cuenta creada correctamente.'
    }, status=status.HTTP_201_CREATED)


@api_view(['POST'])
@permission_classes([AllowAny])
def firebase_login(request):
    decoded = _verify_firebase_token(request)
    if not decoded:
        return Response({'detail': 'Token Firebase inválido.'}, status=status.HTTP_401_UNAUTHORIZED)
    
    email = decoded.get('email')
    try:
        user = Usuario.objects.get(email=email)
    except Usuario.DoesNotExist:
        return Response({'detail': 'Usuario no encontrado.'}, status=status.HTTP_404_NOT_FOUND)
    
    token, _ = Token.objects.get_or_create(user=user)
    return Response({'token': token.key, 'user': _user_payload(user)})