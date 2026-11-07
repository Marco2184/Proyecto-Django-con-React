from xml.sax.saxutils import escape as escape_pdf_text
from django.utils.translation import gettext as translate
import uuid
from io import BytesIO
from decimal import Decimal
from django.conf import settings
from django.contrib.auth import authenticate
from django.http import HttpResponse
from django.utils.translation import activate, get_language, gettext
from django.utils import timezone
from django.db.models.functions import TruncMonth
from django.db.models import Count, Sum
from django.db import transaction
from rest_framework import serializers, status
from rest_framework.authtoken.models import Token
from rest_framework.decorators import api_view, permission_classes, throttle_classes
from .throttles import AuthThrottle
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError as DjangoValidationError
from .security import issue_email_token, consume_email_token, revoke_user
from decouple import config
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import mm
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
from .models import Usuario, DireccionEnvio, Pedido, PedidoItem, PedidoTimeline
from .mailer import send_account_mail
from productos.models import Producto
import firebase_admin
from firebase_admin import credentials, auth as firebase_auth
def _init_firebase_if_configured():
    if firebase_admin._apps:
        return True
    project_id = config("FIREBASE_PROJECT_ID", default="")
    private_key_id = config("FIREBASE_PRIVATE_KEY_ID", default="")
    private_key = config("FIREBASE_PRIVATE_KEY", default="").replace("\\\n", "\n")
    client_email = config("FIREBASE_CLIENT_EMAIL", default="")
    client_id = config("FIREBASE_CLIENT_ID", default="")
    required_values = [project_id, private_key_id, private_key, client_email, client_id]
    if not all(required_values) or "BEGIN PRIVATE KEY" not in private_key:
        print("Firebase no configurado correctamente. Se omite inicialización local.")
        return False
    try:
        cred = credentials.Certificate({
            "type": "service_account",
            "project_id": project_id,
            "private_key_id": private_key_id,
            "private_key": private_key,
            "client_email": client_email,
            "client_id": client_id,
            "auth_uri": "https://accounts.google.com/o/oauth2/auth",
            "token_uri": "https://oauth2.googleapis.com/token",
        })
        firebase_admin.initialize_app(cred)
        return True
    except Exception as e:
        print("Firebase no pudo inicializarse:", type(e).__name__)
        return False
_init_firebase_if_configured()
FRONTEND_URL = getattr(settings, "FRONTEND_URL", "http://localhost:3000")
def _send_mail_safe(subject, body, to):
    """Preserve the public anti-enumeration response on delivery failures."""
    return send_account_mail(subject, body, to)
def _user_payload(user):
    is_staff = bool(getattr(user, "is_staff", False))
    is_superuser = bool(getattr(user, "is_superuser", False))
    return {
        "id": user.id,
        "nombre": getattr(user, "nombre", ""),
        "email": getattr(user, "email", ""),
        "telefono": getattr(user, "telefono", ""),
        "email_verificado": bool(getattr(user, "email_verificado", False)),
        "fecha_registro": getattr(user, "fecha_registro", None),
        "is_active": bool(getattr(user, "is_active", False)),
        "cuenta_activa": bool(getattr(user, "cuenta_activa", False)),
        "is_staff": is_staff,
        "is_superuser": is_superuser,
        "is_admin": is_staff or is_superuser,
    }
class RegisterSerializer(serializers.ModelSerializer):
    def validate_email(self, value):
        value = value.strip().lower()
        if Usuario.objects.filter(email__iexact=value).exists():
            raise serializers.ValidationError(translate('Este correo ya esta registrado.'))
        return value

    password1 = serializers.CharField(write_only=True, min_length=8, max_length=128, trim_whitespace=False)
    password2 = serializers.CharField(write_only=True, min_length=8, max_length=128, trim_whitespace=False)
    class Meta:
        model = Usuario
        fields = ["nombre", "email", "telefono", "password1", "password2"]
    def validate(self, attrs):
        if attrs["password1"] != attrs["password2"]:
            raise serializers.ValidationError({
                "password2": translate("Las contraseñas no coinciden.")
            })
        try:
            validate_password(attrs['password1'], Usuario(email=attrs.get('email', ''), nombre=attrs.get('nombre', '')))
        except DjangoValidationError as exc:
            raise serializers.ValidationError({'password1': exc.messages})
        return attrs
    def create(self, validated_data):
        password = validated_data.pop("password1")
        validated_data.pop("password2")
        user = Usuario.objects.create_user(password=password, **validated_data)
        return user
class LoginSerializer(serializers.Serializer):
    email = serializers.EmailField()
    password = serializers.CharField(write_only=True, max_length=128, trim_whitespace=False)
    remember_me = serializers.BooleanField(required=False, default=False)
class ProfileSerializer(serializers.ModelSerializer):
    class Meta:
        model = Usuario
        fields = ["id", "nombre", "email", "telefono", "email_verificado", "fecha_registro"]
        read_only_fields = ["id", "email", "email_verificado", "fecha_registro"]
class PasswordChangeSerializer(serializers.Serializer):
    password_actual = serializers.CharField(write_only=True, max_length=128, trim_whitespace=False)
    password_nueva = serializers.CharField(write_only=True, min_length=8, max_length=128, trim_whitespace=False)
class ForgotPasswordSerializer(serializers.Serializer):
    email = serializers.EmailField()
class ResetPasswordSerializer(serializers.Serializer):
    password1 = serializers.CharField(write_only=True, min_length=8, max_length=128, trim_whitespace=False)
    password2 = serializers.CharField(write_only=True, min_length=8, max_length=128, trim_whitespace=False)
    def validate(self, attrs):
        if attrs["password1"] != attrs["password2"]:
            raise serializers.ValidationError({
                "password2": translate("Las contraseñas no coinciden.")
            })
        return attrs
class DireccionSerializer(serializers.ModelSerializer):
    class Meta:
        model = DireccionEnvio
        fields = [
            "id",
            "calle",
            "ciudad",
            "departamento",
            "codigo_postal",
            "predeterminada",
            "creado_en",
        ]
        read_only_fields = ["id", "creado_en"]
class PedidoItemSerializer(serializers.ModelSerializer):
    class Meta:
        model = PedidoItem
        fields = [
            "id", "producto", "producto_nombre", "producto_imagen",
            "cantidad", "precio_unitario", "subtotal",
        ]
class PedidoTimelineSerializer(serializers.ModelSerializer):
    descripcion = serializers.SerializerMethodField()

    def get_descripcion(self, obj):
        if obj.descripcion.startswith('Estado actualizado por '):
            return translate('Estado del pedido actualizado.')
        return translate(obj.descripcion)

    class Meta:
        model = PedidoTimeline
        fields = ["id", "estado", "descripcion", "creado_en"]
class PedidoSerializer(serializers.ModelSerializer):
    items_count = serializers.SerializerMethodField()
    puede_cancelar = serializers.SerializerMethodField()
    motivo_no_cancelable = serializers.SerializerMethodField()
    class Meta:
        model = Pedido
        fields = [
            "id", "numero", "fecha", "monto_total", "estado",
            "metodo_pago", "estado_pago", "referencia_pago",
            "fecha_estimada_entrega", "items_count",
            "puede_cancelar", "motivo_no_cancelable",
        ]
    def get_items_count(self, obj):
        return obj.items.count()
    def get_puede_cancelar(self, obj):
        return obj.puede_cancelar
    def get_motivo_no_cancelable(self, obj):
        return obj.motivo_no_cancelable
class PedidoDetalleSerializer(PedidoSerializer):
    items = PedidoItemSerializer(many=True, read_only=True)
    timeline = PedidoTimelineSerializer(many=True, read_only=True)
    direccion = serializers.SerializerMethodField()
    class Meta(PedidoSerializer.Meta):
        fields = PedidoSerializer.Meta.fields + [
            "direccion", "direccion_texto", "entregado_en",
            "cancelado_en", "motivo_cancelacion", "items", "timeline",
        ]
    def get_direccion(self, obj):
        if obj.direccion_envio:
            return DireccionSerializer(obj.direccion_envio).data
        return None
@api_view(["POST"])
@permission_classes([AllowAny])
@throttle_classes([AuthThrottle])
def register(request):
    serializer = RegisterSerializer(data=request.data)
    serializer.is_valid(raise_exception=True)
    user = serializer.save()
    verify_url = f"{FRONTEND_URL}/verify/{issue_email_token(user, 'verify')}"
    _send_mail_safe(
        translate('Verifica tu correo — Monolith'),
        (
            translate('Hola %(name)s,\n\nTu cuenta fue creada correctamente en Monolith Gaming Store.\n\nPara verificar tu correo entra a este enlace:\n%(url)s\n\nSi no creaste esta cuenta, ignora este mensaje.\n\n— Equipo Monolith') % {'name': user.nombre, 'url': verify_url}
        ),
        user.email,
    )
    token, _ = Token.objects.get_or_create(user=user)
    return Response({
        "token": token.key,
        "user": _user_payload(user),
        "message": translate("Cuenta creada. Revisa tu correo %(email)s para verificarla.") % {"email": user.email},
    }, status=status.HTTP_201_CREATED)
@api_view(["POST"])
@permission_classes([AllowAny])
@throttle_classes([AuthThrottle])
def login_api(request):
    serializer = LoginSerializer(data=request.data)
    serializer.is_valid(raise_exception=True)
    user = authenticate(
        request,
        username=serializer.validated_data["email"],
        password=serializer.validated_data["password"],
    )
    if not user or not user.is_active or not user.cuenta_activa:
        return Response(
            {"detail": translate("Credenciales inválidas o cuenta inactiva.")},
            status=status.HTTP_400_BAD_REQUEST,
        )
    token, _ = Token.objects.get_or_create(user=user)
    return Response({
        "token": token.key,
        "user": _user_payload(user),
    })
@api_view(["POST"])
@permission_classes([IsAuthenticated])
def logout_api(request):
    revoke_user(request.user)
    from django.contrib.auth import logout
    logout(request)
    return Response({"message": translate("Sesión cerrada.")})
@api_view(["GET", "PATCH"])
@permission_classes([IsAuthenticated])
def me(request):
    if request.method == "GET":
        return Response(_user_payload(request.user))
    serializer = ProfileSerializer(request.user, data=request.data, partial=True)
    serializer.is_valid(raise_exception=True)
    serializer.save()
    return Response(_user_payload(request.user))
@api_view(["POST"])
@permission_classes([AllowAny])
@throttle_classes([AuthThrottle])
def verify_email(request, token):
    consume_email_token(token, 'verify')
    return Response({"message": translate("Correo verificado correctamente.")})
@api_view(["POST"])
@permission_classes([IsAuthenticated])
@throttle_classes([AuthThrottle])
def resend_verification(request):
    user = request.user
    if user.email_verificado:
        return Response({"message": translate("Tu correo ya está verificado.")})
    verify_url = f"{FRONTEND_URL}/verify/{issue_email_token(user, 'verify')}"
    _send_mail_safe(
        translate('Verifica tu correo — Monolith'),
        (
            translate('Hola %(name)s,\n\nAquí está tu nuevo enlace de verificación:\n%(url)s\n\nEste enlace es de uso único.\n\n— Equipo Monolith') % {'name': user.nombre, 'url': verify_url}
        ),
        user.email,
    )
    return Response({
        "message": translate("Nuevo enlace enviado a %(email)s.") % {"email": user.email},
    })
@api_view(["POST"])
@permission_classes([AllowAny])
@throttle_classes([AuthThrottle])
def forgot_password(request):
    serializer = ForgotPasswordSerializer(data=request.data)
    serializer.is_valid(raise_exception=True)
    email = serializer.validated_data["email"]
    try:
        user = Usuario.objects.get(email=email, is_active=True, cuenta_activa=True)
        reset_url = f"{FRONTEND_URL}/reset-password/{issue_email_token(user, 'reset')}"
        _send_mail_safe(
            translate('Recupera tu acceso — Monolith'),
            (
                translate('Hola %(name)s,\n\nRestablece tu contraseña aquí:\n%(url)s\n\nSi no solicitaste este cambio, ignora este correo.\n\n— Equipo Monolith') % {'name': user.nombre, 'url': reset_url}
            ),
            user.email,
        )
    except Usuario.DoesNotExist:
        pass
    return Response({
        "message": translate("Si el correo está registrado, recibirás un enlace en breve."),
    })
@api_view(["POST"])
@permission_classes([AllowAny])
@throttle_classes([AuthThrottle])
def reset_password(request, token):
    serializer = ResetPasswordSerializer(data=request.data)
    serializer.is_valid(raise_exception=True)
    consume_email_token(token, 'reset', serializer.validated_data['password1'])
    return Response({"message": translate("Contraseña actualizada.")})
@api_view(["POST"])
@permission_classes([IsAuthenticated])
def change_password(request):
    serializer = PasswordChangeSerializer(data=request.data)
    serializer.is_valid(raise_exception=True)
    user = request.user
    if not user.check_password(serializer.validated_data["password_actual"]):
        return Response(
            {"password_actual": [translate("La contraseña actual es incorrecta.")]},
            status=status.HTTP_400_BAD_REQUEST,
        )
    try:
        validate_password(serializer.validated_data['password_nueva'], user)
    except DjangoValidationError as exc:
        raise serializers.ValidationError({'password_nueva': exc.messages})
    user.set_password(serializer.validated_data["password_nueva"])
    user.save()
    Token.objects.filter(user=user).delete()
    return Response({
        "message": translate("Contraseña actualizada correctamente."),
    })
@api_view(["POST"])
@permission_classes([IsAuthenticated])
def delete_account(request):
    password = serializers.CharField(max_length=128, trim_whitespace=False).run_validation(request.data.get('password'))
    user = request.user
    if not password:
        return Response(
            {"detail": translate("Debes ingresar tu contraseña para eliminar la cuenta.")},
            status=status.HTTP_400_BAD_REQUEST,
        )
    # Reautenticación obligatoria; no aceptar cualquier texto para cuentas
    # sin contraseña Django. Dichas cuentas deben establecer contraseña primero.
    if not user.has_usable_password():
        return Response(
            {"detail": translate("Configura una contraseña Django antes de eliminar la cuenta.")},
            status=status.HTTP_400_BAD_REQUEST,
        )

    if not user.check_password(password):
        return Response(
            {"detail": translate("Contraseña incorrecta. No se pudo eliminar la cuenta.")},
            status=status.HTTP_400_BAD_REQUEST,
        )
    Token.objects.filter(user=user).delete()
    user.is_active = False
    user.cuenta_activa = False
    user.nombre = "Usuario eliminado"
    user.email = f"deleted_{user.pk}@monolith.void"
    user.telefono = ""
    user.email_verificado = False
    user.save(
        update_fields=[
            "is_active",
            "cuenta_activa",
            "nombre",
            "email",
            "telefono",
            "email_verificado",
        ]
    )
    return Response(
        {"message": translate("Cuenta eliminada correctamente.")},
        status=status.HTTP_200_OK,
    )
@api_view(["GET", "POST"])
@permission_classes([IsAuthenticated])
def addresses(request):
    if request.method == "GET":
        return Response(
            DireccionSerializer(request.user.direcciones.all(), many=True).data
        )
    serializer = DireccionSerializer(data=request.data)
    serializer.is_valid(raise_exception=True)
    direccion = serializer.save(usuario=request.user)
    if direccion.predeterminada:
        request.user.direcciones.exclude(pk=direccion.pk).update(predeterminada=False)
    return Response(
        DireccionSerializer(direccion).data,
        status=status.HTTP_201_CREATED,
    )
@api_view(["PATCH", "DELETE"])
@permission_classes([IsAuthenticated])
def address_detail(request, pk):
    try:
        direccion = request.user.direcciones.get(pk=pk)
    except DireccionEnvio.DoesNotExist:
        return Response(
            {"detail": translate("Dirección no encontrada.")},
            status=status.HTTP_404_NOT_FOUND,
        )
    if request.method == "DELETE":
        direccion.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)
    serializer = DireccionSerializer(direccion, data=request.data, partial=True)
    serializer.is_valid(raise_exception=True)
    direccion = serializer.save()
    if direccion.predeterminada:
        request.user.direcciones.exclude(pk=direccion.pk).update(predeterminada=False)
    return Response(DireccionSerializer(direccion).data)
@api_view(["GET"])
@permission_classes([IsAuthenticated])
def orders(request):
    qs = request.user.pedidos.prefetch_related("items").all()
    estado = request.query_params.get("estado")
    desde = request.query_params.get("fecha_desde")
    hasta = request.query_params.get("fecha_hasta")
    search = (request.query_params.get("search") or "").strip()
    if estado:
        if estado not in dict(Pedido._meta.get_field('estado').choices):
            raise serializers.ValidationError({'estado': translate('Estado invalido.')})
        qs = qs.filter(estado=estado)
    if desde:
        desde = serializers.DateField().run_validation(desde)
        qs = qs.filter(fecha__date__gte=desde)
    if hasta:
        hasta = serializers.DateField().run_validation(hasta)
        qs = qs.filter(fecha__date__lte=hasta)
    if desde and hasta and desde > hasta:
        raise serializers.ValidationError({'fecha_hasta': translate('Debe ser posterior a fecha_desde.')})
    if search:
        qs = qs.filter(numero__icontains=search)
    resumen_mensual = list(
        qs.filter(estado_pago='aprobado').exclude(estado='cancelado').annotate(mes=TruncMonth("fecha"))
          .values("mes")
          .annotate(total=Sum("monto_total"), cantidad=Count("id"))
          .order_by("-mes")
    )
    return Response({
        "results": PedidoSerializer(qs[:80], many=True).data,
        "resumen_mensual": [
            {
                "mes": item["mes"].strftime("%Y-%m") if item["mes"] else "",
                "total": str(item["total"] or 0),
                "cantidad": item["cantidad"],
            }
            for item in resumen_mensual
        ],
    })
@api_view(["GET"])
@permission_classes([IsAuthenticated])
def order_detail(request, pk):
    try:
        pedido = request.user.pedidos.prefetch_related("items", "timeline").get(pk=pk)
    except Pedido.DoesNotExist:
        return Response({"detail": translate("Pedido no encontrado.")}, status=status.HTTP_404_NOT_FOUND)
    return Response(PedidoDetalleSerializer(pedido).data)
@api_view(["POST"])
@permission_classes([IsAuthenticated])
def cancel_order(request, pk):
    from .order_service import transition_order
    pedido = transition_order(pk, 'cancelado', owner_id=request.user.pk,
                              reason=request.data.get('motivo', 'Cancelado por el cliente'), source='el cliente')
    return Response(PedidoDetalleSerializer(pedido).data)


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def order_receipt(request, pk):
    try:
        pedido = request.user.pedidos.prefetch_related("items", "timeline").get(pk=pk)
    except Pedido.DoesNotExist:
        return Response({"detail": translate("Pedido no encontrado.")}, status=status.HTTP_404_NOT_FOUND)
    def money(value):
        amount = Decimal(str(value or 0))
        return f"S/ {amount:.2f}"
    def clean(value, default="-"):
        value = str(value or "").strip()
        return escape_pdf_text(value) if value else default
    def p(text, style):
        return Paragraph(clean(text), style)
    items = list(pedido.items.all())
    subtotal = sum(Decimal(str(item.subtotal or 0)) for item in items)
    total = Decimal(str(pedido.monto_total or 0))
    descuento = subtotal - total
    if descuento < 0:
        descuento = Decimal("0.00")
    # IGV referencial incluido en el total. No se suma aparte para no alterar el monto pagado.
    igv_incluido = (total * Decimal("18") / Decimal("118")) if total else Decimal("0.00")
    fecha_emision = timezone.localtime(pedido.fecha)
    fecha_vencimiento = fecha_emision.date()
    cliente = f"{request.user.nombre} <{request.user.email}>"
    numero = pedido.numero or f"MNL-{pedido.pk:05d}"
    filename = f"{'receipt' if get_language() == 'en' else 'comprobante'}-{numero}.pdf"
    buffer = BytesIO()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=A4,
        rightMargin=18 * mm,
        leftMargin=18 * mm,
        topMargin=14 * mm,
        bottomMargin=16 * mm,
        title=translate("Comprobante %(number)s") % {"number": numero},
        author="Monolith Gaming Store",
    )
    styles = getSampleStyleSheet()
    styles.add(ParagraphStyle(
        name="Brand",
        parent=styles["Title"],
        fontName="Helvetica-Bold",
        fontSize=24,
        leading=28,
        textColor=colors.HexColor("#00B936"),
        alignment=0,
        spaceAfter=4,
    ))
    styles.add(ParagraphStyle(
        name="InvoiceTitle",
        parent=styles["Title"],
        fontName="Helvetica-Bold",
        fontSize=19,
        leading=22,
        textColor=colors.HexColor("#111111"),
        alignment=2,
        spaceAfter=2,
    ))
    styles.add(ParagraphStyle(
        name="InvoiceNumber",
        parent=styles["Normal"],
        fontName="Helvetica-Bold",
        fontSize=9,
        leading=11,
        textColor=colors.HexColor("#333333"),
        alignment=2,
    ))
    styles.add(ParagraphStyle(
        name="Small",
        parent=styles["Normal"],
        fontSize=8,
        leading=10,
        textColor=colors.HexColor("#505050"),
    ))
    styles.add(ParagraphStyle(
        name="Tiny",
        parent=styles["Normal"],
        fontSize=7,
        leading=9,
        textColor=colors.HexColor("#666666"),
    ))
    styles.add(ParagraphStyle(
        name="Cell",
        parent=styles["Normal"],
        fontSize=8.5,
        leading=10.5,
        textColor=colors.HexColor("#111111"),
    ))
    styles.add(ParagraphStyle(
        name="CellBold",
        parent=styles["Normal"],
        fontName="Helvetica-Bold",
        fontSize=8.5,
        leading=10.5,
        textColor=colors.HexColor("#111111"),
    ))
    styles.add(ParagraphStyle(
        name="TableHead",
        parent=styles["Normal"],
        fontName="Helvetica-Bold",
        fontSize=8,
        leading=9,
        textColor=colors.white,
    ))
    styles.add(ParagraphStyle(
        name="GreenSection",
        parent=styles["Normal"],
        fontName="Helvetica-Bold",
        fontSize=10,
        leading=12,
        textColor=colors.HexColor("#00B936"),
        spaceBefore=8,
        spaceAfter=5,
    ))
    styles.add(ParagraphStyle(
        name="Terms",
        parent=styles["Normal"],
        fontSize=7.3,
        leading=9,
        textColor=colors.HexColor("#5A5A5A"),
    ))
    story = []
    # Encabezado similar a factura: marca a la izquierda, tipo y numero a la derecha.
    header = Table([
        [
            [
                Paragraph("MONOLITH", styles["Brand"]),
                Paragraph("Gaming Store", styles["Small"]),
                Paragraph(translate("Comprobante generado automaticamente por el sistema"), styles["Tiny"]),
            ],
            [
                Paragraph(("COMPROBANTE SIMULADO" if get_language() != "en" else translate("FACTURA")), styles["InvoiceTitle"]),
                Paragraph(f"#{pedido.pk}", styles["InvoiceNumber"]),
            ],
        ]
    ], colWidths=[102 * mm, 72 * mm])
    header.setStyle(TableStyle([
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("LEFTPADDING", (0, 0), (-1, -1), 0),
        ("RIGHTPADDING", (0, 0), (-1, -1), 0),
        ("TOPPADDING", (0, 0), (-1, -1), 0),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
    ]))
    story.append(header)
    story.append(Spacer(1, 8))
    # Datos superiores, con distribucion parecida a la referencia.
    left_info = [
        [Paragraph(translate("Cliente:"), styles["CellBold"]), Paragraph(clean(cliente), styles["Cell"])],
        [Paragraph(translate("Cobrar a:"), styles["CellBold"]), Paragraph("Monolith Gaming Store", styles["Cell"])],
        [Paragraph(translate("Pago:"), styles["CellBold"]), Paragraph(f"{gettext(pedido.metodo_pago)} / {gettext(pedido.estado_pago)}", styles["Cell"])],
        [Paragraph(translate("Referencia:"), styles["CellBold"]), Paragraph(clean(pedido.referencia_pago), styles["Cell"])],
    ]
    left_table = Table(left_info, colWidths=[24 * mm, 80 * mm])
    left_table.setStyle(TableStyle([
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("LEFTPADDING", (0, 0), (-1, -1), 0),
        ("RIGHTPADDING", (0, 0), (-1, -1), 4),
        ("TOPPADDING", (0, 0), (-1, -1), 2),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 2),
    ]))
    right_info = [
        [Paragraph(translate("Fecha:"), styles["CellBold"]), Paragraph(fecha_emision.strftime("%m/%d/%Y" if get_language() == "en" else "%d/%m/%Y"), styles["Cell"])],
        [Paragraph(translate("Condiciones de pago:"), styles["CellBold"]), Paragraph(translate("Pago simulado aprobado"), styles["Cell"])],
        [Paragraph(translate("Fecha de vencimiento:"), styles["CellBold"]), Paragraph(fecha_vencimiento.strftime("%m/%d/%Y" if get_language() == "en" else "%d/%m/%Y"), styles["Cell"])],
        [Paragraph(translate("Orden de Compra:"), styles["CellBold"]), Paragraph(numero, styles["Cell"])],
        [Paragraph(translate("Saldo Adeudado:"), styles["CellBold"]), Paragraph("S/ 0.00", styles["CellBold"])],
    ]
    right_table = Table(right_info, colWidths=[34 * mm, 36 * mm])
    right_table.setStyle(TableStyle([
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("ALIGN", (0, 0), (-1, -1), "RIGHT"),
        ("BACKGROUND", (0, 4), (-1, 4), colors.HexColor("#F2F2F2")),
        ("LEFTPADDING", (0, 0), (-1, -1), 4),
        ("RIGHTPADDING", (0, 0), (-1, -1), 0),
        ("TOPPADDING", (0, 0), (-1, -1), 2),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 2),
    ]))
    info = Table([[left_table, right_table]], colWidths=[104 * mm, 70 * mm])
    info.setStyle(TableStyle([
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("LEFTPADDING", (0, 0), (-1, -1), 0),
        ("RIGHTPADDING", (0, 0), (-1, -1), 0),
    ]))
    story.append(info)
    story.append(Spacer(1, 12))
    # Direccion y estado del pedido en una franja sobria.
    state_box = Table([
        [Paragraph(translate("Estado del pedido"), styles["CellBold"]), Paragraph(gettext(pedido.estado).upper(), styles["Cell"])],
        [Paragraph(translate("Direccion"), styles["CellBold"]), Paragraph(clean(pedido.direccion_texto), styles["Cell"])],
        [Paragraph(translate("Entrega estimada"), styles["CellBold"]), Paragraph((pedido.fecha_estimada_entrega.strftime("%m/%d/%Y" if get_language() == "en" else "%d/%m/%Y") if pedido.fecha_estimada_entrega else "-"), styles["Cell"])],
    ], colWidths=[36 * mm, 138 * mm])
    state_box.setStyle(TableStyle([
        ("BOX", (0, 0), (-1, -1), 0.6, colors.HexColor("#BDBDBD")),
        ("INNERGRID", (0, 0), (-1, -1), 0.25, colors.HexColor("#D8D8D8")),
        ("BACKGROUND", (0, 0), (0, -1), colors.HexColor("#F6F6F6")),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("LEFTPADDING", (0, 0), (-1, -1), 6),
        ("RIGHTPADDING", (0, 0), (-1, -1), 6),
        ("TOPPADDING", (0, 0), (-1, -1), 5),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
    ]))
    story.append(state_box)
    story.append(Spacer(1, 12))
    # Detalle de articulos, inspirado en la segunda referencia.
    product_rows = [[
        Paragraph(translate("Articulo"), styles["TableHead"]),
        Paragraph(translate("Cantidad"), styles["TableHead"]),
        Paragraph(translate("Precio unitario"), styles["TableHead"]),
        Paragraph(translate("Importe"), styles["TableHead"]),
    ]]
    for item in items:
        product_rows.append([
            Paragraph(clean(translate(item.producto_nombre)), styles["Cell"]),
            Paragraph(str(item.cantidad), styles["Cell"]),
            Paragraph(money(item.precio_unitario), styles["Cell"]),
            Paragraph(money(item.subtotal), styles["Cell"]),
        ])
    if len(product_rows) == 1:
        product_rows.append([
            Paragraph(translate("Sin productos"), styles["Cell"]),
            Paragraph("0", styles["Cell"]),
            Paragraph("S/ 0.00", styles["Cell"]),
            Paragraph("S/ 0.00", styles["Cell"]),
        ])
    products_table = Table(product_rows, colWidths=[100 * mm, 24 * mm, 25 * mm, 25 * mm], repeatRows=1)
    products_table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#111111")),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("BOX", (0, 0), (-1, -1), 0.6, colors.HexColor("#202020")),
        ("INNERGRID", (0, 0), (-1, -1), 0.25, colors.HexColor("#D2D2D2")),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("ALIGN", (1, 1), (-1, -1), "RIGHT"),
        ("LEFTPADDING", (0, 0), (-1, -1), 6),
        ("RIGHTPADDING", (0, 0), (-1, -1), 6),
        ("TOPPADDING", (0, 0), (-1, -1), 5),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
    ]))
    story.append(products_table)
    story.append(Spacer(1, 10))
    total_data = [
        [Paragraph("Subtotal:", styles["Cell"]), Paragraph(money(subtotal), styles["Cell"])],
    ]
    if descuento > 0:
        total_data.append([Paragraph(translate("Descuento aplicado:"), styles["Cell"]), Paragraph(f"- {money(descuento)}", styles["Cell"])])
    total_data.extend([
        [Paragraph(translate("IGV incluido (18%):"), styles["Cell"]), Paragraph(money(igv_incluido), styles["Cell"])],
        [Paragraph("Total:", styles["CellBold"]), Paragraph(money(total), styles["CellBold"])],
        [Paragraph(translate("Cantidad Pagada:"), styles["CellBold"]), Paragraph(money(total), styles["CellBold"])],
    ])
    totals_table = Table(total_data, colWidths=[45 * mm, 34 * mm], hAlign="RIGHT")
    totals_table.setStyle(TableStyle([
        ("ALIGN", (0, 0), (-1, -1), "RIGHT"),
        ("LINEABOVE", (0, -2), (-1, -2), 0.6, colors.HexColor("#111111")),
        ("BACKGROUND", (0, -1), (-1, -1), colors.HexColor("#E9FFF0")),
        ("TEXTCOLOR", (0, -1), (-1, -1), colors.HexColor("#006B22")),
        ("BOX", (0, -1), (-1, -1), 0.6, colors.HexColor("#00B936")),
        ("LEFTPADDING", (0, 0), (-1, -1), 5),
        ("RIGHTPADDING", (0, 0), (-1, -1), 5),
        ("TOPPADDING", (0, 0), (-1, -1), 3),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
    ]))
    story.append(totals_table)
    story.append(Spacer(1, 18))
    story.append(Paragraph(translate("Pago:"), styles["CellBold"]))
    story.append(Paragraph(
        translate("El pago correspondiente a esta compra ha sido completado exitosamente mediante una operacion simulada. "
        "No se requiere ninguna accion adicional por parte del cliente en relacion con este pago."),
        styles["Terms"],
    ))
    story.append(Spacer(1, 8))
    story.append(Paragraph(translate("Terminos:"), styles["CellBold"]))
    story.append(Paragraph(
        translate("Este comprobante representa una demostracion academica del flujo de compra de Monolith. "
        "Los productos, importes y estado del pago son generados por el sistema para evidenciar el proceso de comercio electronico. "
        "Para devoluciones o cambios dentro de una implementacion real, el cliente deberia presentar este comprobante y cumplir las politicas de la tienda."),
        styles["Terms"],
    ))
    def footer(canvas, doc_obj):
        canvas.saveState()
        canvas.setStrokeColor(colors.HexColor("#00B936"))
        canvas.setLineWidth(0.5)
        canvas.line(18 * mm, 12 * mm, 192 * mm, 12 * mm)
        canvas.setFont("Helvetica", 7)
        canvas.setFillColor(colors.HexColor("#555555"))
        canvas.drawString(18 * mm, 8 * mm, translate("Monolith Gaming Store - comprobante de compra"))
        canvas.drawRightString(192 * mm, 8 * mm, translate("Pagina %(page)s") % {"page": doc_obj.page})
        canvas.restoreState()
    doc.build(story, onFirstPage=footer, onLaterPages=footer)
    pdf = buffer.getvalue()
    buffer.close()
    response = HttpResponse(pdf, content_type="application/pdf")
    response["Content-Disposition"] = f'attachment; filename="{filename}"'
    return response
@api_view(["POST"])
@permission_classes([AllowAny])
def set_language(request):
    lang = request.data.get("language", "es")
    if lang not in ["es", "en"]:
        lang = "es"
    activate(lang)
    response = Response({"language": lang})
    response.set_cookie(settings.LANGUAGE_COOKIE_NAME, lang)
    return response
def _verify_firebase_token(request):
    if not _init_firebase_if_configured():
        return None
    auth_header = request.headers.get("Authorization", "")
    if not auth_header.startswith("Firebase "):
        return None
    id_token = auth_header.split("Firebase ")[1]
    try:
        decoded=firebase_auth.verify_id_token(id_token,check_revoked=True)
        # Never link a Django account based on an unverified Firebase email.
        return decoded if decoded.get('email_verified') is True else None
    except Exception as e:
        print("ERROR FIREBASE TOKEN:", type(e).__name__)
        return None
@api_view(["POST"])
@permission_classes([IsAuthenticated])
def firebase_sync_email(request):
    decoded = _verify_firebase_token(request)
    if not decoded:
        return Response(
            {"detail": translate("Token Firebase inválido.")},
            status=status.HTTP_401_UNAUTHORIZED,
        )
    email = decoded.get("email")
    if not email or email.lower() != request.user.email.lower():
        return Response(
            {"detail": translate("El token Firebase no corresponde al usuario autenticado.")},
            status=status.HTTP_403_FORBIDDEN,
        )
    request.user.email_verificado = bool(decoded.get("email_verified", False))
    request.user.save(update_fields=["email_verificado"])
    return Response({
        "user": _user_payload(request.user),
        "email_verificado": request.user.email_verificado,
    })
@api_view(["POST"])
@permission_classes([IsAuthenticated])
def firebase_delete_account(request):
    # No permitir eliminar la cuenta solo con un access token de Monolith.
    # Exigir un segundo comprobante Firebase del mismo correo.
    firebase_token = request.data.get("firebase_id_token")
    if not firebase_token or not _init_firebase_if_configured():
        return Response(
            {"detail": translate("Verificación Firebase no disponible.")},
            status=status.HTTP_400_BAD_REQUEST,
        )
    try:
        decoded = firebase_auth.verify_id_token(firebase_token,check_revoked=True)
        if not decoded.get('email_verified'):
            return Response({'detail':translate('Token Firebase inválido.')},status=403)
    except Exception:
        return Response(
            {"detail": translate("Token Firebase inválido.")},
            status=status.HTTP_401_UNAUTHORIZED,
        )

    email = decoded.get("email")
    if not email or email.lower() != request.user.email.lower():
        return Response(
            {"detail": translate("El token Firebase no corresponde al usuario autenticado.")},
            status=status.HTTP_403_FORBIDDEN,
        )

    user = request.user
    with transaction.atomic():
        Token.objects.filter(user=user).delete()
        user.is_active = False
        user.cuenta_activa = False
        user.nombre = "Usuario eliminado"
        user.email = f"deleted_{user.pk}@monolith.void"
        user.telefono = ""
        user.email_verificado = False
        user.save(update_fields=[
            "is_active", "cuenta_activa", "nombre", "email",
            "telefono", "email_verificado",
        ])

    return Response({"message": translate("Cuenta eliminada correctamente.")})


@api_view(["POST"])
@permission_classes([AllowAny])
@throttle_classes([AuthThrottle])
def firebase_register(request):
    decoded = _verify_firebase_token(request)
    if not decoded:
        return Response(
            {"detail": translate("Token Firebase inválido.")},
            status=status.HTTP_401_UNAUTHORIZED,
        )
    email = decoded.get("email")
    if not email:
        return Response(
            {"detail": translate("El token Firebase no contiene email.")},
            status=status.HTTP_400_BAD_REQUEST,
        )
    nombre = request.data.get("nombre", "")
    telefono = request.data.get("telefono", "")
    if Usuario.objects.filter(email__iexact=email).exists():
        user = Usuario.objects.get(email__iexact=email)
        if not user.is_active or not user.cuenta_activa:
            return Response(
                {"detail": translate("Cuenta inactiva.")},
                status=status.HTTP_400_BAD_REQUEST,
            )
    else:
        user = Usuario.objects.create_user(
            email=email,
            password=None,
            nombre=nombre,
            telefono=telefono,
        )
        user.email_verificado = bool(decoded.get("email_verified", False))
        user.save(update_fields=["email_verificado"])
    user.email_verificado = bool(decoded.get("email_verified", False))
    user.save(update_fields=["email_verificado"])
    token, _ = Token.objects.get_or_create(user=user)
    return Response({
        "token": token.key,
        "user": _user_payload(user),
        "message": translate("Cuenta creada correctamente."),
    }, status=status.HTTP_201_CREATED)
@api_view(["POST"])
@permission_classes([AllowAny])
@throttle_classes([AuthThrottle])
def firebase_login(request):
    decoded = _verify_firebase_token(request)
    if not decoded:
        return Response(
            {"detail": translate("Token Firebase inválido.")},
            status=status.HTTP_401_UNAUTHORIZED,
        )
    email = decoded.get("email")
    if not email:
        return Response(
            {"detail": translate("El token Firebase no contiene email.")},
            status=status.HTTP_400_BAD_REQUEST,
        )
    try:
        user = Usuario.objects.get(email__iexact=email)
    except Usuario.DoesNotExist:
        return Response(
            {"detail": translate("Usuario no encontrado.")},
            status=status.HTTP_404_NOT_FOUND,
        )
    if not user.is_active or not user.cuenta_activa:
        return Response(
            {"detail": translate("Cuenta inactiva.")},
            status=status.HTTP_400_BAD_REQUEST,
        )
    user.email_verificado = bool(decoded.get("email_verified", False))
    user.save(update_fields=["email_verificado"])
    token, _ = Token.objects.get_or_create(user=user)
    return Response({
        "token": token.key,
        "user": _user_payload(user),
    })
