import uuid
from django.conf import settings
from django.contrib.auth import authenticate
from django.core.mail import send_mail
from django.utils.translation import activate
from rest_framework import serializers, status
from rest_framework.authtoken.models import Token
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from .models import Usuario, DireccionEnvio, Pedido

FRONTEND_URL = getattr(settings, 'FRONTEND_URL', 'http://localhost:3000')


def _send_mail_safe(subject, body, to):
    try:
        send_mail(subject, body, settings.DEFAULT_FROM_EMAIL, [to], fail_silently=False)
    except Exception:
        # En desarrollo no detenemos el flujo si el SMTP no está configurado.
        pass


def _user_payload(user):
    return {
        'id': user.id,
        'nombre': user.nombre,
        'email': user.email,
        'telefono': user.telefono,
        'email_verificado': user.email_verificado,
        'fecha_registro': user.fecha_registro,
    }


class RegisterSerializer(serializers.ModelSerializer):
    password1 = serializers.CharField(write_only=True, min_length=8)
    password2 = serializers.CharField(write_only=True, min_length=8)

    class Meta:
        model = Usuario
        fields = ['nombre', 'email', 'telefono', 'password1', 'password2']

    def validate(self, attrs):
        if attrs['password1'] != attrs['password2']:
            raise serializers.ValidationError({'password2': 'Las contraseñas no coinciden.'})
        return attrs

    def create(self, validated_data):
        password = validated_data.pop('password1')
        validated_data.pop('password2')
        user = Usuario.objects.create_user(password=password, **validated_data)
        return user


class LoginSerializer(serializers.Serializer):
    email = serializers.EmailField()
    password = serializers.CharField(write_only=True)
    remember_me = serializers.BooleanField(required=False, default=False)


class ProfileSerializer(serializers.ModelSerializer):
    class Meta:
        model = Usuario
        fields = ['id', 'nombre', 'email', 'telefono', 'email_verificado', 'fecha_registro']
        read_only_fields = ['id', 'email', 'email_verificado', 'fecha_registro']


class PasswordChangeSerializer(serializers.Serializer):
    password_actual = serializers.CharField(write_only=True)
    password_nueva = serializers.CharField(write_only=True, min_length=8)


class ForgotPasswordSerializer(serializers.Serializer):
    email = serializers.EmailField()


class ResetPasswordSerializer(serializers.Serializer):
    password1 = serializers.CharField(write_only=True, min_length=8)
    password2 = serializers.CharField(write_only=True, min_length=8)

    def validate(self, attrs):
        if attrs['password1'] != attrs['password2']:
            raise serializers.ValidationError({'password2': 'Las contraseñas no coinciden.'})
        return attrs


class DireccionSerializer(serializers.ModelSerializer):
    class Meta:
        model = DireccionEnvio
        fields = ['id', 'calle', 'ciudad', 'departamento', 'codigo_postal', 'predeterminada', 'creado_en']
        read_only_fields = ['id', 'creado_en']


class PedidoSerializer(serializers.ModelSerializer):
    class Meta:
        model = Pedido
        fields = ['id', 'numero', 'fecha', 'monto_total', 'estado']


@api_view(['POST'])
@permission_classes([AllowAny])
def register(request):
    serializer = RegisterSerializer(data=request.data)
    serializer.is_valid(raise_exception=True)
    user = serializer.save()
    verify_url = f'{FRONTEND_URL}/verify/{user.token_verificacion}'
    _send_mail_safe(
        'Bienvenido a Monolith',
        f'Hola {user.nombre},\n\nTu cuenta fue creada correctamente. Ya puedes explorar el catálogo gaming de Monolith.\n\n— Equipo Monolith',
        user.email,
    )
    _send_mail_safe(
        'Verifica tu correo — Monolith',
        f'Hola {user.nombre},\n\nPara completar tu autenticación por correo, verifica tu cuenta aquí:\n{verify_url}\n\n— Equipo Monolith',
        user.email,
    )
    token, _ = Token.objects.get_or_create(user=user)
    return Response({
        'token': token.key,
        'user': _user_payload(user),
        'message': f'Cuenta creada. Revisa tu correo {user.email} para verificarla.'
    }, status=status.HTTP_201_CREATED)


@api_view(['POST'])
@permission_classes([AllowAny])
def login_api(request):
    serializer = LoginSerializer(data=request.data)
    serializer.is_valid(raise_exception=True)
    user = authenticate(request, username=serializer.validated_data['email'], password=serializer.validated_data['password'])
    if not user or not user.is_active or not user.cuenta_activa:
        return Response({'detail': 'Credenciales inválidas o cuenta inactiva.'}, status=status.HTTP_400_BAD_REQUEST)
    token, _ = Token.objects.get_or_create(user=user)
    return Response({'token': token.key, 'user': _user_payload(user)})


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def logout_api(request):
    Token.objects.filter(user=request.user).delete()
    return Response({'message': 'Sesión cerrada.'})


@api_view(['GET', 'PATCH'])
@permission_classes([IsAuthenticated])
def me(request):
    if request.method == 'GET':
        return Response(_user_payload(request.user))
    serializer = ProfileSerializer(request.user, data=request.data, partial=True)
    serializer.is_valid(raise_exception=True)
    serializer.save()
    return Response(_user_payload(request.user))


@api_view(['POST'])
@permission_classes([AllowAny])
def verify_email(request, token):
    try:
        user = Usuario.objects.get(token_verificacion=token)
    except Usuario.DoesNotExist:
        return Response({'detail': 'Enlace inválido o expirado.'}, status=status.HTTP_404_NOT_FOUND)
    user.email_verificado = True
    user.token_verificacion = uuid.uuid4()
    user.save(update_fields=['email_verificado', 'token_verificacion'])
    return Response({'message': 'Correo verificado correctamente. Ya puedes iniciar sesión.'})


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def resend_verification(request):
    user = request.user
    if user.email_verificado:
        return Response({'message': 'Tu correo ya está verificado.'})
    user.token_verificacion = uuid.uuid4()
    user.save(update_fields=['token_verificacion'])
    verify_url = f'{FRONTEND_URL}/verify/{user.token_verificacion}'
    _send_mail_safe('Verifica tu correo — Monolith', f'Hola {user.nombre},\n\nNuevo enlace:\n{verify_url}\n\n— Equipo Monolith', user.email)
    return Response({'message': f'Nuevo enlace enviado a {user.email}.'})


@api_view(['POST'])
@permission_classes([AllowAny])
def forgot_password(request):
    serializer = ForgotPasswordSerializer(data=request.data)
    serializer.is_valid(raise_exception=True)
    email = serializer.validated_data['email']
    try:
        user = Usuario.objects.get(email=email, is_active=True)
        user.token_verificacion = uuid.uuid4()
        user.save(update_fields=['token_verificacion'])
        reset_url = f'{FRONTEND_URL}/reset-password/{user.token_verificacion}'
        _send_mail_safe('Recupera tu acceso — Monolith', f'Hola {user.nombre},\n\nRestablece tu contraseña aquí:\n{reset_url}\n\n— Equipo Monolith', user.email)
    except Usuario.DoesNotExist:
        pass
    return Response({'message': 'Si el correo está registrado, recibirás un enlace en breve.'})


@api_view(['POST'])
@permission_classes([AllowAny])
def reset_password(request, token):
    try:
        user = Usuario.objects.get(token_verificacion=token)
    except Usuario.DoesNotExist:
        return Response({'detail': 'Enlace inválido o expirado.'}, status=status.HTTP_404_NOT_FOUND)
    serializer = ResetPasswordSerializer(data=request.data)
    serializer.is_valid(raise_exception=True)
    user.set_password(serializer.validated_data['password1'])
    user.token_verificacion = uuid.uuid4()
    user.save()
    Token.objects.filter(user=user).delete()
    return Response({'message': 'Contraseña actualizada. Ya puedes iniciar sesión.'})


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def change_password(request):
    serializer = PasswordChangeSerializer(data=request.data)
    serializer.is_valid(raise_exception=True)
    user = request.user
    if not user.check_password(serializer.validated_data['password_actual']):
        return Response({'password_actual': ['La contraseña actual es incorrecta.']}, status=status.HTTP_400_BAD_REQUEST)
    user.set_password(serializer.validated_data['password_nueva'])
    user.save()
    Token.objects.filter(user=user).delete()
    token, _ = Token.objects.get_or_create(user=user)
    return Response({'token': token.key, 'message': 'Contraseña actualizada correctamente.'})


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def delete_account(request):
    password = request.data.get('password', '')
    user = request.user
    if not user.check_password(password):
        return Response({'detail': 'Contraseña incorrecta.'}, status=status.HTTP_400_BAD_REQUEST)
    user.is_active = False
    user.cuenta_activa = False
    user.nombre = 'Usuario eliminado'
    user.email = f'deleted_{user.pk}@monolith.void'
    user.save()
    Token.objects.filter(user=user).delete()
    return Response({'message': 'Cuenta eliminada del sistema.'})


@api_view(['GET', 'POST'])
@permission_classes([IsAuthenticated])
def addresses(request):
    if request.method == 'GET':
        return Response(DireccionSerializer(request.user.direcciones.all(), many=True).data)
    serializer = DireccionSerializer(data=request.data)
    serializer.is_valid(raise_exception=True)
    direccion = serializer.save(usuario=request.user)
    if direccion.predeterminada:
        request.user.direcciones.exclude(pk=direccion.pk).update(predeterminada=False)
    return Response(DireccionSerializer(direccion).data, status=status.HTTP_201_CREATED)


@api_view(['PATCH', 'DELETE'])
@permission_classes([IsAuthenticated])
def address_detail(request, pk):
    try:
        direccion = request.user.direcciones.get(pk=pk)
    except DireccionEnvio.DoesNotExist:
        return Response({'detail': 'Dirección no encontrada.'}, status=status.HTTP_404_NOT_FOUND)
    if request.method == 'DELETE':
        direccion.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)
    serializer = DireccionSerializer(direccion, data=request.data, partial=True)
    serializer.is_valid(raise_exception=True)
    direccion = serializer.save()
    if direccion.predeterminada:
        request.user.direcciones.exclude(pk=direccion.pk).update(predeterminada=False)
    return Response(DireccionSerializer(direccion).data)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def orders(request):
    qs = request.user.pedidos.all()
    estado = request.query_params.get('estado')
    desde = request.query_params.get('fecha_desde')
    hasta = request.query_params.get('fecha_hasta')
    if estado:
        qs = qs.filter(estado=estado)
    if desde:
        qs = qs.filter(fecha__date__gte=desde)
    if hasta:
        qs = qs.filter(fecha__date__lte=hasta)
    return Response(PedidoSerializer(qs[:50], many=True).data)


@api_view(['POST'])
@permission_classes([AllowAny])
def set_language(request):
    lang = request.data.get('language', 'es')
    if lang not in ['es', 'en']:
        lang = 'es'
    activate(lang)
    response = Response({'language': lang})
    response.set_cookie(settings.LANGUAGE_COOKIE_NAME, lang)
    return response
