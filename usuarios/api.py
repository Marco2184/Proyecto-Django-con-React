import uuid
from io import BytesIO
from decimal import Decimal

from django.conf import settings
from django.contrib.auth import authenticate
from django.core.mail import send_mail
from django.http import HttpResponse
from django.utils.translation import activate
from django.utils import timezone
from django.db.models.functions import TruncMonth
from django.db.models import Count, Sum

from rest_framework import serializers, status
from rest_framework.authtoken.models import Token
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response

from decouple import config

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import mm
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle

from .models import Usuario, DireccionEnvio, Pedido, PedidoItem, PedidoTimeline

import firebase_admin
from firebase_admin import credentials, auth as firebase_auth


def _init_firebase_if_configured():
    if firebase_admin._apps:
        return True

    project_id = config("FIREBASE_PROJECT_ID", default="")
    private_key_id = config("FIREBASE_PRIVATE_KEY_ID", default="")
    private_key = config("FIREBASE_PRIVATE_KEY", default="").replace("\\n", "\n")
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
        print("Firebase no pudo inicializarse:", repr(e))
        return False


_init_firebase_if_configured()


FRONTEND_URL = getattr(settings, "FRONTEND_URL", "http://localhost:3000")


def _send_mail_safe(subject, body, to):
    """
    Envía correos reales por SMTP.
    Si falla, imprime el error en Render Logs.
    """
    try:
        print("Intentando enviar correo a:", to)

        sent = send_mail(
            subject,
            body,
            settings.DEFAULT_FROM_EMAIL,
            [to],
            fail_silently=False,
        )

        print("Resultado send_mail:", sent)

        if sent:
            print(f"Correo enviado correctamente a {to}")
        else:
            print(f"No se pudo enviar el correo a {to}")

    except Exception as e:
        print("ERROR ENVIANDO CORREO:", repr(e))


def _user_payload(user):
    return {
        "id": user.id,
        "nombre": user.nombre,
        "email": user.email,
        "telefono": user.telefono,
        "email_verificado": user.email_verificado,
        "fecha_registro": user.fecha_registro,
    }


class RegisterSerializer(serializers.ModelSerializer):
    password1 = serializers.CharField(write_only=True, min_length=8)
    password2 = serializers.CharField(write_only=True, min_length=8)

    class Meta:
        model = Usuario
        fields = ["nombre", "email", "telefono", "password1", "password2"]

    def validate(self, attrs):
        if attrs["password1"] != attrs["password2"]:
            raise serializers.ValidationError({
                "password2": "Las contraseñas no coinciden."
            })
        return attrs

    def create(self, validated_data):
        password = validated_data.pop("password1")
        validated_data.pop("password2")
        user = Usuario.objects.create_user(password=password, **validated_data)
        return user


class LoginSerializer(serializers.Serializer):
    email = serializers.EmailField()
    password = serializers.CharField(write_only=True)
    remember_me = serializers.BooleanField(required=False, default=False)


class ProfileSerializer(serializers.ModelSerializer):
    class Meta:
        model = Usuario
        fields = ["id", "nombre", "email", "telefono", "email_verificado", "fecha_registro"]
        read_only_fields = ["id", "email", "email_verificado", "fecha_registro"]


class PasswordChangeSerializer(serializers.Serializer):
    password_actual = serializers.CharField(write_only=True)
    password_nueva = serializers.CharField(write_only=True, min_length=8)


class ForgotPasswordSerializer(serializers.Serializer):
    email = serializers.EmailField()


class ResetPasswordSerializer(serializers.Serializer):
    password1 = serializers.CharField(write_only=True, min_length=8)
    password2 = serializers.CharField(write_only=True, min_length=8)

    def validate(self, attrs):
        if attrs["password1"] != attrs["password2"]:
            raise serializers.ValidationError({
                "password2": "Las contraseñas no coinciden."
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
def register(request):
    serializer = RegisterSerializer(data=request.data)
    serializer.is_valid(raise_exception=True)

    user = serializer.save()

    verify_url = f"{FRONTEND_URL}/verify/{user.token_verificacion}"

    _send_mail_safe(
        "Verifica tu correo — Monolith",
        (
            f"Hola {user.nombre},\n\n"
            f"Tu cuenta fue creada correctamente en Monolith Gaming Store.\n\n"
            f"Para verificar tu correo entra a este enlace:\n"
            f"{verify_url}\n\n"
            f"Si no creaste esta cuenta, ignora este mensaje.\n\n"
            f"— Equipo Monolith"
        ),
        user.email,
    )

    token, _ = Token.objects.get_or_create(user=user)

    return Response({
        "token": token.key,
        "user": _user_payload(user),
        "message": f"Cuenta creada. Revisa tu correo {user.email} para verificarla.",
    }, status=status.HTTP_201_CREATED)


@api_view(["POST"])
@permission_classes([AllowAny])
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
            {"detail": "Credenciales inválidas o cuenta inactiva."},
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
    Token.objects.filter(user=request.user).delete()
    return Response({"message": "Sesión cerrada."})


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
def verify_email(request, token):
    try:
        user = Usuario.objects.get(token_verificacion=token)
    except Usuario.DoesNotExist:
        return Response(
            {"detail": "Enlace inválido o expirado."},
            status=status.HTTP_404_NOT_FOUND,
        )

    user.email_verificado = True
    user.token_verificacion = uuid.uuid4()
    user.save(update_fields=["email_verificado", "token_verificacion"])

    return Response({"message": "Correo verificado correctamente."})


@api_view(["POST"])
@permission_classes([IsAuthenticated])
def resend_verification(request):
    user = request.user

    if user.email_verificado:
        return Response({"message": "Tu correo ya está verificado."})

    user.token_verificacion = uuid.uuid4()
    user.save(update_fields=["token_verificacion"])

    verify_url = f"{FRONTEND_URL}/verify/{user.token_verificacion}"

    _send_mail_safe(
        "Verifica tu correo — Monolith",
        (
            f"Hola {user.nombre},\n\n"
            f"Aquí está tu nuevo enlace de verificación:\n"
            f"{verify_url}\n\n"
            f"Este enlace es de uso único.\n\n"
            f"— Equipo Monolith"
        ),
        user.email,
    )

    return Response({
        "message": f"Nuevo enlace enviado a {user.email}.",
    })


@api_view(["POST"])
@permission_classes([AllowAny])
def forgot_password(request):
    serializer = ForgotPasswordSerializer(data=request.data)
    serializer.is_valid(raise_exception=True)

    email = serializer.validated_data["email"]

    try:
        user = Usuario.objects.get(email=email, is_active=True)

        user.token_verificacion = uuid.uuid4()
        user.save(update_fields=["token_verificacion"])

        reset_url = f"{FRONTEND_URL}/reset-password/{user.token_verificacion}"

        _send_mail_safe(
            "Recupera tu acceso — Monolith",
            (
                f"Hola {user.nombre},\n\n"
                f"Restablece tu contraseña aquí:\n"
                f"{reset_url}\n\n"
                f"Si no solicitaste este cambio, ignora este correo.\n\n"
                f"— Equipo Monolith"
            ),
            user.email,
        )

    except Usuario.DoesNotExist:
        pass

    return Response({
        "message": "Si el correo está registrado, recibirás un enlace en breve.",
    })


@api_view(["POST"])
@permission_classes([AllowAny])
def reset_password(request, token):
    try:
        user = Usuario.objects.get(token_verificacion=token)
    except Usuario.DoesNotExist:
        return Response(
            {"detail": "Enlace inválido o expirado."},
            status=status.HTTP_404_NOT_FOUND,
        )

    serializer = ResetPasswordSerializer(data=request.data)
    serializer.is_valid(raise_exception=True)

    user.set_password(serializer.validated_data["password1"])
    user.token_verificacion = uuid.uuid4()
    user.save()

    Token.objects.filter(user=user).delete()

    return Response({"message": "Contraseña actualizada."})


@api_view(["POST"])
@permission_classes([IsAuthenticated])
def change_password(request):
    serializer = PasswordChangeSerializer(data=request.data)
    serializer.is_valid(raise_exception=True)

    user = request.user

    if not user.check_password(serializer.validated_data["password_actual"]):
        return Response(
            {"password_actual": ["La contraseña actual es incorrecta."]},
            status=status.HTTP_400_BAD_REQUEST,
        )

    user.set_password(serializer.validated_data["password_nueva"])
    user.save()

    Token.objects.filter(user=user).delete()
    token, _ = Token.objects.get_or_create(user=user)

    return Response({
        "token": token.key,
        "message": "Contraseña actualizada correctamente.",
    })

@api_view(["POST"])
@permission_classes([IsAuthenticated])
def delete_account(request):
    password = request.data.get("password", "")
    user = request.user

    if not password:
        return Response(
            {"detail": "Debes ingresar tu contraseña para eliminar la cuenta."},
            status=status.HTTP_400_BAD_REQUEST,
        )

    # Si el usuario tiene contraseña Django usable, la validamos.
    # Si viene de Firebase, normalmente no tiene contraseña Django usable.
    if user.has_usable_password() and not user.check_password(password):
        return Response(
            {"detail": "Contraseña incorrecta. No se pudo eliminar la cuenta."},
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
        {"message": "Cuenta eliminada correctamente."},
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
            {"detail": "Dirección no encontrada."},
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
        qs = qs.filter(estado=estado)

    if desde:
        qs = qs.filter(fecha__date__gte=desde)

    if hasta:
        qs = qs.filter(fecha__date__lte=hasta)

    if search:
        qs = qs.filter(numero__icontains=search)

    resumen_mensual = list(
        qs.annotate(mes=TruncMonth("fecha"))
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
        return Response({"detail": "Pedido no encontrado."}, status=status.HTTP_404_NOT_FOUND)

    return Response(PedidoDetalleSerializer(pedido).data)


@api_view(["POST"])
@permission_classes([IsAuthenticated])
def cancel_order(request, pk):
    try:
        pedido = request.user.pedidos.prefetch_related("items").get(pk=pk)
    except Pedido.DoesNotExist:
        return Response({"detail": "Pedido no encontrado."}, status=status.HTTP_404_NOT_FOUND)

    if not pedido.puede_cancelar:
        return Response(
            {"detail": pedido.motivo_no_cancelable or "El pedido ya no puede cancelarse."},
            status=status.HTTP_400_BAD_REQUEST,
        )

    motivo = request.data.get("motivo", "Cancelado por el cliente")

    for item in pedido.items.select_related("producto"):
        if item.producto_id:
            item.producto.stock = item.producto.stock + item.cantidad
            item.producto.ventas = max((item.producto.ventas or 0) - item.cantidad, 0)
            item.producto.save(update_fields=["stock", "ventas"])

    pedido.estado = "cancelado"
    pedido.cancelado_en = timezone.now()
    pedido.motivo_cancelacion = motivo[:250]
    pedido.save(update_fields=["estado", "cancelado_en", "motivo_cancelacion"])

    PedidoTimeline.objects.create(
        pedido=pedido,
        estado="cancelado",
        descripcion="Pedido cancelado por el cliente.",
    )

    return Response(PedidoDetalleSerializer(pedido).data)


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def order_receipt(request, pk):
    try:
        pedido = request.user.pedidos.prefetch_related("items", "timeline").get(pk=pk)
    except Pedido.DoesNotExist:
        return Response({"detail": "Pedido no encontrado."}, status=status.HTTP_404_NOT_FOUND)

    def money(value):
        amount = Decimal(str(value or 0))
        return f"S/ {amount:.2f}"

    buffer = BytesIO()
    filename = f"comprobante-{pedido.numero}.pdf"

    doc = SimpleDocTemplate(
        buffer,
        pagesize=A4,
        rightMargin=16 * mm,
        leftMargin=16 * mm,
        topMargin=14 * mm,
        bottomMargin=16 * mm,
        title=f"Comprobante {pedido.numero}",
        author="Monolith Gaming Store",
    )

    styles = getSampleStyleSheet()
    styles.add(ParagraphStyle(
        name="MonoTitle",
        parent=styles["Title"],
        fontName="Helvetica-Bold",
        fontSize=22,
        leading=26,
        textColor=colors.HexColor("#00B936"),
        alignment=1,
        spaceAfter=6,
    ))
    styles.add(ParagraphStyle(
        name="MonoSubtitle",
        parent=styles["Normal"],
        fontName="Helvetica-Bold",
        fontSize=11,
        leading=14,
        textColor=colors.HexColor("#1F2937"),
        alignment=1,
        spaceAfter=10,
    ))
    styles.add(ParagraphStyle(
        name="SectionTitle",
        parent=styles["Heading2"],
        fontName="Helvetica-Bold",
        fontSize=12,
        leading=15,
        textColor=colors.HexColor("#00B936"),
        spaceBefore=8,
        spaceAfter=6,
    ))
    styles.add(ParagraphStyle(
        name="SmallMuted",
        parent=styles["Normal"],
        fontSize=8,
        leading=10,
        textColor=colors.HexColor("#666666"),
    ))
    styles.add(ParagraphStyle(
        name="Cell",
        parent=styles["Normal"],
        fontSize=9,
        leading=11,
    ))
    styles.add(ParagraphStyle(
        name="CellBold",
        parent=styles["Normal"],
        fontName="Helvetica-Bold",
        fontSize=9,
        leading=11,
    ))

    story = []
    story.append(Paragraph("MONOLITH", styles["MonoTitle"]))
    story.append(Paragraph("COMPROBANTE DE COMPRA - PAGO SIMULADO", styles["MonoSubtitle"]))
    story.append(Paragraph(
        "Este documento representa el comprobante generado por la tienda virtual Monolith. "
        "El pago mostrado es simulado para fines academicos y de demostracion del flujo de compra.",
        styles["SmallMuted"],
    ))
    story.append(Spacer(1, 8))

    cliente = f"{request.user.nombre} &lt;{request.user.email}&gt;"
    datos = [
        [Paragraph("Nro. de pedido", styles["CellBold"]), Paragraph(pedido.numero or "-", styles["Cell"])],
        [Paragraph("Fecha de emision", styles["CellBold"]), Paragraph(pedido.fecha.strftime("%d/%m/%Y %H:%M"), styles["Cell"])],
        [Paragraph("Cliente", styles["CellBold"]), Paragraph(cliente, styles["Cell"])],
        [Paragraph("Estado del pedido", styles["CellBold"]), Paragraph(pedido.estado.upper(), styles["Cell"])],
        [Paragraph("Pago", styles["CellBold"]), Paragraph(f"{pedido.metodo_pago} / {pedido.estado_pago}", styles["Cell"])],
        [Paragraph("Referencia", styles["CellBold"]), Paragraph(pedido.referencia_pago or "-", styles["Cell"])],
        [Paragraph("Direccion", styles["CellBold"]), Paragraph(pedido.direccion_texto or "-", styles["Cell"])],
        [Paragraph("Entrega estimada", styles["CellBold"]), Paragraph(str(pedido.fecha_estimada_entrega or "-"), styles["Cell"])],
    ]

    datos_table = Table(datos, colWidths=[42 * mm, 120 * mm])
    datos_table.setStyle(TableStyle([
        ("BOX", (0, 0), (-1, -1), 0.8, colors.HexColor("#1F2937")),
        ("INNERGRID", (0, 0), (-1, -1), 0.25, colors.HexColor("#D1D5DB")),
        ("BACKGROUND", (0, 0), (0, -1), colors.HexColor("#F3F4F6")),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("LEFTPADDING", (0, 0), (-1, -1), 7),
        ("RIGHTPADDING", (0, 0), (-1, -1), 7),
        ("TOPPADDING", (0, 0), (-1, -1), 6),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
    ]))
    story.append(datos_table)
    story.append(Spacer(1, 10))

    story.append(Paragraph("Detalle de productos", styles["SectionTitle"]))
    productos = [[
        Paragraph("Producto", styles["CellBold"]),
        Paragraph("Cant.", styles["CellBold"]),
        Paragraph("Precio", styles["CellBold"]),
        Paragraph("Subtotal", styles["CellBold"]),
    ]]

    for item in pedido.items.all():
        productos.append([
            Paragraph(item.producto_nombre, styles["Cell"]),
            Paragraph(str(item.cantidad), styles["Cell"]),
            Paragraph(money(item.precio_unitario), styles["Cell"]),
            Paragraph(money(item.subtotal), styles["Cell"]),
        ])

    productos_table = Table(productos, colWidths=[88 * mm, 18 * mm, 28 * mm, 28 * mm], repeatRows=1)
    productos_table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#050505")),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.HexColor("#00FF41")),
        ("BOX", (0, 0), (-1, -1), 0.8, colors.HexColor("#1F2937")),
        ("INNERGRID", (0, 0), (-1, -1), 0.25, colors.HexColor("#D1D5DB")),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("ALIGN", (1, 1), (-1, -1), "RIGHT"),
        ("LEFTPADDING", (0, 0), (-1, -1), 6),
        ("RIGHTPADDING", (0, 0), (-1, -1), 6),
        ("TOPPADDING", (0, 0), (-1, -1), 6),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
    ]))
    story.append(productos_table)
    story.append(Spacer(1, 10))

    resumen = [
        [Paragraph("Total pagado", styles["CellBold"]), Paragraph(money(pedido.monto_total), styles["CellBold"])],
    ]
    resumen_table = Table(resumen, colWidths=[120 * mm, 42 * mm], hAlign="RIGHT")
    resumen_table.setStyle(TableStyle([
        ("BOX", (0, 0), (-1, -1), 0.8, colors.HexColor("#00B936")),
        ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#ECFDF3")),
        ("TEXTCOLOR", (0, 0), (-1, -1), colors.HexColor("#065F2C")),
        ("ALIGN", (1, 0), (1, -1), "RIGHT"),
        ("LEFTPADDING", (0, 0), (-1, -1), 8),
        ("RIGHTPADDING", (0, 0), (-1, -1), 8),
        ("TOPPADDING", (0, 0), (-1, -1), 7),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 7),
    ]))
    story.append(resumen_table)
    story.append(Spacer(1, 12))

    story.append(Paragraph("Gracias por comprar en Monolith Gaming Store.", styles["SmallMuted"]))
    story.append(Paragraph("Documento generado automaticamente por el sistema.", styles["SmallMuted"]))

    def footer(canvas, doc_obj):
        canvas.saveState()
        canvas.setStrokeColor(colors.HexColor("#00B936"))
        canvas.setLineWidth(0.5)
        canvas.line(16 * mm, 12 * mm, 194 * mm, 12 * mm)
        canvas.setFont("Helvetica", 7)
        canvas.setFillColor(colors.HexColor("#555555"))
        canvas.drawString(16 * mm, 8 * mm, "Monolith Gaming Store - comprobante generado por sistema")
        canvas.drawRightString(194 * mm, 8 * mm, f"Pagina {doc_obj.page}")
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
        return firebase_auth.verify_id_token(id_token)
    except Exception as e:
        print("ERROR FIREBASE TOKEN:", repr(e))
        return None

@api_view(["POST"])
@permission_classes([IsAuthenticated])

def firebase_sync_email(request):
    decoded = _verify_firebase_token(request)

    if not decoded:
        return Response(
            {"detail": "Token Firebase inválido."},
            status=status.HTTP_401_UNAUTHORIZED,
        )

    email = decoded.get("email")

    if not email or email.lower() != request.user.email.lower():
        return Response(
            {"detail": "El token Firebase no corresponde al usuario autenticado."},
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
    user = request.user

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
        {"message": "Cuenta eliminada correctamente."},
        status=status.HTTP_200_OK,
    )
    decoded = _verify_firebase_token(request)

    if not decoded:
        return Response(
            {"detail": "Token Firebase inválido."},
            status=status.HTTP_401_UNAUTHORIZED,
        )

    email = decoded.get("email")

    if not email or email.lower() != request.user.email.lower():
        return Response(
            {"detail": "El token Firebase no corresponde al usuario autenticado."},
            status=status.HTTP_403_FORBIDDEN,
        )

    user = request.user
    user.is_active = False
    user.cuenta_activa = False
    user.nombre = "Usuario eliminado"
    user.email = f"deleted_{user.pk}@monolith.void"
    user.save()

    Token.objects.filter(user=user).delete()

    return Response({"message": "Cuenta eliminada del sistema."})


@api_view(["POST"])
@permission_classes([AllowAny])
def firebase_register(request):
    decoded = _verify_firebase_token(request)

    if not decoded:
        return Response(
            {"detail": "Token Firebase inválido."},
            status=status.HTTP_401_UNAUTHORIZED,
        )

    email = decoded.get("email")

    if not email:
        return Response(
            {"detail": "El token Firebase no contiene email."},
            status=status.HTTP_400_BAD_REQUEST,
        )

    nombre = request.data.get("nombre", "")
    telefono = request.data.get("telefono", "")

    if Usuario.objects.filter(email=email).exists():
        user = Usuario.objects.get(email=email)

        if not user.is_active or not user.cuenta_activa:
            return Response(
                {"detail": "Cuenta inactiva."},
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
        "message": "Cuenta creada correctamente.",
    }, status=status.HTTP_201_CREATED)


@api_view(["POST"])
@permission_classes([AllowAny])
def firebase_login(request):
    decoded = _verify_firebase_token(request)

    if not decoded:
        return Response(
            {"detail": "Token Firebase inválido."},
            status=status.HTTP_401_UNAUTHORIZED,
        )

    email = decoded.get("email")

    if not email:
        return Response(
            {"detail": "El token Firebase no contiene email."},
            status=status.HTTP_400_BAD_REQUEST,
        )

    try:
        user = Usuario.objects.get(email=email)
    except Usuario.DoesNotExist:
        return Response(
            {"detail": "Usuario no encontrado."},
            status=status.HTTP_404_NOT_FOUND,
        )

    if not user.is_active or not user.cuenta_activa:
        return Response(
            {"detail": "Cuenta inactiva."},
            status=status.HTTP_400_BAD_REQUEST,
        )

    user.email_verificado = bool(decoded.get("email_verified", False))
    user.save(update_fields=["email_verificado"])

    token, _ = Token.objects.get_or_create(user=user)

    return Response({
        "token": token.key,
        "user": _user_payload(user),
    })