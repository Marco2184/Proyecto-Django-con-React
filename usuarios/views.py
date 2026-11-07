from django.utils.translation import gettext as translate
import uuid

from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth import login, logout, update_session_auth_hash
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from .mailer import send_account_mail
from django.core.paginator import Paginator
from django.conf import settings

from .forms import (
    RegistroForm,
    LoginForm,
    EditarPerfilForm,
    CambiarPasswordForm,
    RecuperarPasswordForm,
    NuevaPasswordForm,
    DireccionForm,
    FiltroPedidosForm,
)
from .models import Usuario, DireccionEnvio, Pedido
from .security import issue_email_token, consume_email_token, email_token_user
from rest_framework.exceptions import ValidationError as TokenValidationError


def _send(subject, body, to):
    return send_account_mail(subject, body, to)


# ── H001.1 + H001.2 + H007.1 ─────────────────────────────
def registro(request):
    if request.user.is_authenticated:
        return redirect("dashboard")

    form = RegistroForm(request.POST or None)

    if request.method == "POST" and form.is_valid():
        user = form.save()

        verify_url = f"{settings.FRONTEND_URL}/verify/{issue_email_token(user, 'verify')}"

        _send(
            translate("Verifica tu correo — Monolith"),
            (
                translate("Abre este enlace de Monolith para verificar tu correo: %(url)s") % {"url": verify_url}
            ),
            user.email,
        )

        messages.success(
            request,
            translate('¡Cuenta creada! Revisa tu correo %(value0)s para verificarla.') % {'value0': user.email},
        )
        return redirect("login")

    return render(request, "usuarios/registro.html", {"form": form})


# ── H002.1 + H002.2 ──────────────────────────────────────
def iniciar_sesion(request):
    if request.user.is_authenticated:
        return redirect("dashboard")

    form = LoginForm(request, data=request.POST or None)

    if request.method == "POST" and form.is_valid():
        user = form.get_user()
        login(request, user)

        if form.cleaned_data.get("remember_me"):
            request.session.set_expiry(604800)
        else:
            request.session.set_expiry(0)

        return redirect("dashboard")

    return render(request, "usuarios/login.html", {"form": form})


# ── H003.1 + H003.2 ──────────────────────────────────────
@login_required
def cerrar_sesion(request):
    if request.method == "POST":
        logout(request)
        messages.info(request, translate("SESSION TERMINATED."))
        return redirect("login")

    return redirect("dashboard")


# ── H007.1 — Verificar correo ────────────────────────────
def verificar_correo(request, token):
    try:
        consume_email_token(token, 'verify')

        messages.success(request, translate("✓ Correo verificado. Ya puedes acceder al sistema."))

    except TokenValidationError:
        messages.error(request, translate("✗ Enlace de verificación inválido o expirado."))

    return redirect("login")


# ── H007.2 — Reenviar verificación ───────────────────────
@login_required
def reenviar_verificacion(request):
    user = request.user

    if user.email_verificado:
        messages.info(request, translate("Tu correo ya está verificado."))
        return redirect("dashboard")

    verify_url = f"{settings.FRONTEND_URL}/verify/{issue_email_token(user, 'verify')}"

    _send(
        translate("Verifica tu correo — Monolith"),
        (
            translate("Abre este enlace de Monolith para verificar tu correo: %(url)s") % {"url": verify_url}
        ),
        user.email,
    )

    messages.success(
        request,
        translate('Nuevo enlace de verificación enviado a %(value0)s.') % {'value0': user.email},
    )
    return redirect("dashboard")


# ── H004.1 — Solicitar recuperación de contraseña ────────
def recuperar_password(request):
    form = RecuperarPasswordForm(request.POST or None)

    if request.method == "POST" and form.is_valid():
        email = form.cleaned_data["email"]

        try:
            user = Usuario.objects.get(email=email, is_active=True, cuenta_activa=True)

            reset_url = f"{settings.FRONTEND_URL}/reset-password/{issue_email_token(user, 'reset')}"

            _send(
                translate("Recupera tu acceso — Monolith"),
                (
                    translate("Abre este enlace de Monolith para restablecer tu contrase\u00f1a: %(url)s") % {"url": reset_url}
                ),
                user.email,
            )

        except Usuario.DoesNotExist:
            pass

        messages.success(
            request,
            translate("Si el correo está registrado, recibirás un enlace en breve."),
        )
        return redirect("login")

    return render(request, "usuarios/recuperar_password.html", {"form": form})


# ── H004.2 — Nueva contraseña con enlace ─────────────────
def nueva_password(request, token):
    try:
        user, _ = email_token_user(token, 'reset')

    except TokenValidationError:
        messages.error(request, translate("Enlace inválido o expirado."))
        return redirect("login")

    form = NuevaPasswordForm(request.POST or None)
    form.user = user

    if request.method == "POST" and form.is_valid():
        try:
            consume_email_token(token, 'reset', form.cleaned_data['password1'])
        except TokenValidationError:
            form.add_error(None, translate('Enlace invalido o expirado.'))
            return render(request, 'usuarios/nueva_password.html', {'form': form, 'token': token})

        messages.success(request, translate("✓ Contraseña actualizada. Ya puedes iniciar sesión."))
        return redirect("login")

    return render(
        request,
        "usuarios/nueva_password.html",
        {
            "form": form,
            "token": token,
        },
    )


# ── Dashboard ─────────────────────────────────────────────
@login_required
def dashboard(request):
    stats = [
        ("box", translate("Pedidos"), "0", "var(--neon)"),
        ("cart", translate("En carrito"), "0", "#7b2fff"),
        ("star", translate("Favoritos"), "0", "#f7b731"),
        ("user", translate("Nivel"), "LVL1", "#00ccff"),
    ]

    return render(request, "usuarios/dashboard.html", {"stats": stats})


# ── H005.1 + H009.1 + H009.2 — Perfil ───────────────────
@login_required
def perfil(request):
    ultimos_pedidos = request.user.pedidos.all()[:5]
    return render(
        request,
        "usuarios/perfil.html",
        {
            "ultimos_pedidos": ultimos_pedidos,
        },
    )


@login_required
def editar_perfil(request):
    form = EditarPerfilForm(request.POST or None, instance=request.user)

    if request.method == "POST" and form.is_valid():
        form.save()
        messages.success(request, translate("✓ Perfil actualizado correctamente."))
        return redirect("perfil")

    return render(request, "usuarios/editar_perfil.html", {"form": form})


@login_required
def cambiar_password(request):
    form = CambiarPasswordForm(request.POST or None)
    form.user = request.user

    if request.method == "POST" and form.is_valid():
        user = request.user

        if not user.check_password(form.cleaned_data["password_actual"]):
            form.add_error("password_actual", translate("La contraseña actual es incorrecta."))
        else:
            user.set_password(form.cleaned_data["password_nueva"])
            user.save()

            logout(request)

            messages.success(request, translate("✓ Contraseña actualizada correctamente."))
            return redirect("perfil")

    return render(request, "usuarios/cambiar_password.html", {"form": form})


# ── H008.2 — Listar direcciones ───────────────────────────
@login_required
def listar_direcciones(request):
    direcciones = request.user.direcciones.all()
    return render(
        request,
        "usuarios/direcciones_lista.html",
        {
            "direcciones": direcciones,
        },
    )


# ── H008.1 — Agregar dirección ────────────────────────────
@login_required
def agregar_direccion(request):
    form = DireccionForm(request.POST or None)

    if request.method == "POST" and form.is_valid():
        dir_ = form.save(commit=False)
        dir_.usuario = request.user
        dir_.save()

        messages.success(request, translate("✓ Dirección agregada correctamente."))
        return redirect("listar_direcciones")

    return render(
        request,
        "usuarios/direccion_form.html",
        {
            "form": form,
            "modo": "agregar",
        },
    )


# ── H008.2 — Editar dirección ─────────────────────────────
@login_required
def editar_direccion(request, pk):
    direccion = get_object_or_404(DireccionEnvio, pk=pk, usuario=request.user)
    form = DireccionForm(request.POST or None, instance=direccion)

    if request.method == "POST" and form.is_valid():
        form.save()
        messages.success(request, translate("✓ Dirección actualizada correctamente."))
        return redirect("listar_direcciones")

    return render(
        request,
        "usuarios/direccion_form.html",
        {
            "form": form,
            "modo": "editar",
            "direccion": direccion,
        },
    )


# ── H008.2 — Eliminar dirección ───────────────────────────
@login_required
def eliminar_direccion(request, pk):
    direccion = get_object_or_404(DireccionEnvio, pk=pk, usuario=request.user)

    if request.method == "POST":
        direccion.delete()
        messages.success(request, translate("✓ Dirección eliminada."))

    return redirect("listar_direcciones")


# ── H010.1 + H010.2 — Historial de pedidos con filtros ───
@login_required
def historial_pedidos(request):
    pedidos_qs = request.user.pedidos.all()
    form = FiltroPedidosForm(request.GET)

    if form.is_valid():
        if form.cleaned_data.get("fecha_desde"):
            pedidos_qs = pedidos_qs.filter(
                fecha__date__gte=form.cleaned_data["fecha_desde"]
            )

        if form.cleaned_data.get("fecha_hasta"):
            pedidos_qs = pedidos_qs.filter(
                fecha__date__lte=form.cleaned_data["fecha_hasta"]
            )

        if form.cleaned_data.get("estado"):
            pedidos_qs = pedidos_qs.filter(estado=form.cleaned_data["estado"])

    paginator = Paginator(pedidos_qs, 10)
    pedidos = paginator.get_page(request.GET.get("page", 1))

    params = request.GET.copy()
    params.pop("page", None)
    query_string = params.urlencode()

    return render(
        request,
        "usuarios/historial_pedidos.html",
        {
            "pedidos": pedidos,
            "form": form,
            "query_string": query_string,
        },
    )


@login_required
def eliminar_cuenta(request):
    if request.method == "POST":
        password = request.POST.get("password")
        user = request.user

        if user.check_password(password):
            user.is_active = False
            user.cuenta_activa = False
            user.nombre = "Usuario eliminado"
            user.email = f"deleted_{user.pk}@monolith.void"
            user.save()

            logout(request)

            messages.info(request, translate("Tu cuenta ha sido eliminada del sistema."))
            return redirect("login")

        else:
            messages.error(
                request,
                translate("✗ Contraseña incorrecta. No se pudo eliminar la cuenta."),
            )

    return render(request, "usuarios/eliminar_cuenta.html")
