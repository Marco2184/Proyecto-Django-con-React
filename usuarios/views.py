import uuid
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth import login, logout, update_session_auth_hash
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.core.mail import send_mail
from django.core.paginator import Paginator
from django.conf import settings
from .forms import (RegistroForm, LoginForm, EditarPerfilForm,
                    CambiarPasswordForm, RecuperarPasswordForm, NuevaPasswordForm,
                    DireccionForm, FiltroPedidosForm)
from .models import Usuario, DireccionEnvio, Pedido


def _send(subject, body, to):
    """Wrapper de send_mail que no explota si el SMTP falla."""
    try:
        send_mail(subject, body, settings.DEFAULT_FROM_EMAIL, [to], fail_silently=False)
    except Exception:
        pass


# ── H001.1 + H001.2 + H007.1 ─────────────────────────────
def registro(request):
    if request.user.is_authenticated:
        return redirect('dashboard')
    form = RegistroForm(request.POST or None)
    if request.method == 'POST' and form.is_valid():
        user = form.save()
        # H001.2 — Correo bienvenida REAL
        _send(
            '¡Bienvenido a Monolith!',
            (
                f'Hola {user.nombre},\n\n'
                f'Tu cuenta fue creada exitosamente en Monolith Gaming Store.\n\n'
                f'Para verificar tu correo haz clic aquí:\n'
                f'http://localhost:8000/verificar/{user.token_verificacion}/\n\n'
                f'— Equipo Monolith'
            ),
            user.email,
        )
        messages.success(request, f'¡Cuenta creada! Revisa tu correo {user.email} para verificarla.')
        return redirect('login')
    return render(request, 'usuarios/registro.html', {'form': form})


# ── H002.1 + H002.2 ──────────────────────────────────────
def iniciar_sesion(request):
    if request.user.is_authenticated:
        return redirect('dashboard')
    form = LoginForm(request, data=request.POST or None)
    if request.method == 'POST' and form.is_valid():
        user = form.get_user()
        login(request, user)
        request.session.set_expiry(604800 if form.cleaned_data.get('remember_me') else 0)
        return redirect('dashboard')
    return render(request, 'usuarios/login.html', {'form': form})


# ── H003.1 + H003.2 ──────────────────────────────────────
@login_required
def cerrar_sesion(request):
    if request.method == 'POST':
        logout(request)
        messages.info(request, 'SESSION TERMINATED.')
        return redirect('login')
    return redirect('dashboard')


# ── H007.1 — Verificar correo ────────────────────────────
def verificar_correo(request, token):
    try:
        user = Usuario.objects.get(token_verificacion=token)
        user.email_verificado = True
        user.save()
        messages.success(request, '✓ Correo verificado. Ya puedes acceder al sistema.')
    except Usuario.DoesNotExist:
        messages.error(request, '✗ Enlace de verificación inválido o expirado.')
    return redirect('login')


# ── H007.2 — Reenviar verificación ───────────────────────
@login_required
def reenviar_verificacion(request):
    user = request.user
    if user.email_verificado:
        messages.info(request, 'Tu correo ya está verificado.')
        return redirect('dashboard')
    # Generar nuevo token
    user.token_verificacion = uuid.uuid4()
    user.save()
    _send(
        'Verifica tu correo — Monolith',
        (
            f'Hola {user.nombre},\n\n'
            f'Aquí está tu nuevo enlace de verificación:\n'
            f'http://localhost:8000/verificar/{user.token_verificacion}/\n\n'
            f'Este enlace es de uso único.\n\n— Equipo Monolith'
        ),
        user.email,
    )
    messages.success(request, f'Nuevo enlace de verificación enviado a {user.email}.')
    return redirect('dashboard')


# ── H004.1 — Solicitar recuperación de contraseña ────────
def recuperar_password(request):
    form = RecuperarPasswordForm(request.POST or None)
    if request.method == 'POST' and form.is_valid():
        email = form.cleaned_data['email']
        try:
            user = Usuario.objects.get(email=email, is_active=True)
            # Reutilizamos token_verificacion como token de reset
            user.token_verificacion = uuid.uuid4()
            user.save()
            _send(
                'Recupera tu acceso — Monolith',
                (
                    f'Hola {user.nombre},\n\n'
                    f'Haz clic aquí para restablecer tu contraseña:\n'
                    f'http://localhost:8000/nueva-password/{user.token_verificacion}/\n\n'
                    f'Si no solicitaste este cambio, ignora este correo.\n\n— Equipo Monolith'
                ),
                user.email,
            )
        except Usuario.DoesNotExist:
            pass  # No revelar si el correo existe
        messages.success(request, 'Si el correo está registrado, recibirás un enlace en breve.')
        return redirect('login')
    return render(request, 'usuarios/recuperar_password.html', {'form': form})


# ── H004.2 — Nueva contraseña con enlace ─────────────────
def nueva_password(request, token):
    try:
        user = Usuario.objects.get(token_verificacion=token)
    except Usuario.DoesNotExist:
        messages.error(request, 'Enlace inválido o expirado.')
        return redirect('login')
    form = NuevaPasswordForm(request.POST or None)
    if request.method == 'POST' and form.is_valid():
        user.set_password(form.cleaned_data['password1'])
        user.token_verificacion = uuid.uuid4()  # invalidar token
        user.save()
        messages.success(request, '✓ Contraseña actualizada. Ya puedes iniciar sesión.')
        return redirect('login')
    return render(request, 'usuarios/nueva_password.html', {'form': form, 'token': token})


# ── Dashboard ─────────────────────────────────────────────
@login_required
def dashboard(request):
    stats = [
        ('box',  'Pedidos',    '0',    'var(--neon)'),
        ('cart', 'En carrito', '0',    '#7b2fff'),
        ('star', 'Favoritos',  '0',    '#f7b731'),
        ('user', 'Nivel',      'LVL1', '#00ccff'),
    ]
    return render(request, 'usuarios/dashboard.html', {'stats': stats})


# ── H005.1 + H009.1 + H009.2 — Perfil ───────────────────
@login_required
def perfil(request):
    ultimos_pedidos = request.user.pedidos.all()[:5]
    return render(request, 'usuarios/perfil.html', {'ultimos_pedidos': ultimos_pedidos})


@login_required
def editar_perfil(request):
    """H005.1 — Editar nombre y teléfono"""
    form = EditarPerfilForm(request.POST or None, instance=request.user)
    if request.method == 'POST' and form.is_valid():
        form.save()
        messages.success(request, '✓ Perfil actualizado correctamente.')
        return redirect('perfil')
    return render(request, 'usuarios/editar_perfil.html', {'form': form})


@login_required
def cambiar_password(request):
    """H005.2 — Cambiar contraseña desde perfil"""
    form = CambiarPasswordForm(request.POST or None)
    if request.method == 'POST' and form.is_valid():
        user = request.user
        if not user.check_password(form.cleaned_data['password_actual']):
            form.add_error('password_actual', 'La contraseña actual es incorrecta.')
        else:
            user.set_password(form.cleaned_data['password_nueva'])
            user.save()
            update_session_auth_hash(request, user)  # no cerrar sesión
            messages.success(request, '✓ Contraseña actualizada correctamente.')
            return redirect('perfil')
    return render(request, 'usuarios/cambiar_password.html', {'form': form})


# ── H008.2 — Listar direcciones ───────────────────────────
@login_required
def listar_direcciones(request):
    direcciones = request.user.direcciones.all()
    return render(request, 'usuarios/direcciones_lista.html', {'direcciones': direcciones})


# ── H008.1 — Agregar dirección ────────────────────────────
@login_required
def agregar_direccion(request):
    form = DireccionForm(request.POST or None)
    if request.method == 'POST' and form.is_valid():
        dir_ = form.save(commit=False)
        dir_.usuario = request.user
        dir_.save()
        messages.success(request, '✓ Dirección agregada correctamente.')
        return redirect('listar_direcciones')
    return render(request, 'usuarios/direccion_form.html', {'form': form, 'modo': 'agregar'})


# ── H008.2 — Editar dirección ─────────────────────────────
@login_required
def editar_direccion(request, pk):
    direccion = get_object_or_404(DireccionEnvio, pk=pk, usuario=request.user)
    form = DireccionForm(request.POST or None, instance=direccion)
    if request.method == 'POST' and form.is_valid():
        form.save()
        messages.success(request, '✓ Dirección actualizada correctamente.')
        return redirect('listar_direcciones')
    return render(request, 'usuarios/direccion_form.html', {'form': form, 'modo': 'editar', 'direccion': direccion})


# ── H008.2 — Eliminar dirección ───────────────────────────
@login_required
def eliminar_direccion(request, pk):
    direccion = get_object_or_404(DireccionEnvio, pk=pk, usuario=request.user)
    if request.method == 'POST':
        direccion.delete()
        messages.success(request, '✓ Dirección eliminada.')
    return redirect('listar_direcciones')


# ── H010.1 + H010.2 — Historial de pedidos con filtros ───
@login_required
def historial_pedidos(request):
    pedidos_qs = request.user.pedidos.all()
    form = FiltroPedidosForm(request.GET)

    if form.is_valid():
        if form.cleaned_data.get('fecha_desde'):
            pedidos_qs = pedidos_qs.filter(fecha__date__gte=form.cleaned_data['fecha_desde'])
        if form.cleaned_data.get('fecha_hasta'):
            pedidos_qs = pedidos_qs.filter(fecha__date__lte=form.cleaned_data['fecha_hasta'])
        if form.cleaned_data.get('estado'):
            pedidos_qs = pedidos_qs.filter(estado=form.cleaned_data['estado'])

    paginator = Paginator(pedidos_qs, 10)
    pedidos   = paginator.get_page(request.GET.get('page', 1))

    params = request.GET.copy()
    params.pop('page', None)
    query_string = params.urlencode()

    return render(request, 'usuarios/historial_pedidos.html', {
        'pedidos':       pedidos,
        'form':          form,
        'query_string':  query_string,
    })


@login_required
def eliminar_cuenta(request):
    """H006.1 — Eliminar cuenta"""
    if request.method == 'POST':
        password = request.POST.get('password')
        user = request.user
        if user.check_password(password):
            # H006.2 — Desactivar y anonimizar
            user.is_active = False
            user.cuenta_activa = False
            user.nombre = 'Usuario eliminado'
            user.email  = f'deleted_{user.pk}@monolith.void'
            user.save()
            logout(request)
            messages.info(request, 'Tu cuenta ha sido eliminada del sistema.')
            return redirect('login')
        else:
            messages.error(request, '✗ Contraseña incorrecta. No se pudo eliminar la cuenta.')
    return render(request, 'usuarios/eliminar_cuenta.html')
