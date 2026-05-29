from django.contrib.auth.models import AbstractBaseUser, BaseUserManager, PermissionsMixin
from django.conf import settings
from django.db import models
import uuid


# ── H008 — Departamentos de Perú ─────────────────────────────
DEPARTAMENTOS_PERU = [
    ('Amazonas',      'Amazonas'),
    ('Áncash',        'Áncash'),
    ('Apurímac',      'Apurímac'),
    ('Arequipa',      'Arequipa'),
    ('Ayacucho',      'Ayacucho'),
    ('Cajamarca',     'Cajamarca'),
    ('Callao',        'Callao'),
    ('Cusco',         'Cusco'),
    ('Huancavelica',  'Huancavelica'),
    ('Huánuco',       'Huánuco'),
    ('Ica',           'Ica'),
    ('Junín',         'Junín'),
    ('La Libertad',   'La Libertad'),
    ('Lambayeque',    'Lambayeque'),
    ('Lima',          'Lima'),
    ('Loreto',        'Loreto'),
    ('Madre de Dios', 'Madre de Dios'),
    ('Moquegua',      'Moquegua'),
    ('Pasco',         'Pasco'),
    ('Piura',         'Piura'),
    ('Puno',          'Puno'),
    ('San Martín',    'San Martín'),
    ('Tacna',         'Tacna'),
    ('Tumbes',        'Tumbes'),
    ('Ucayali',       'Ucayali'),
]

# ── H010 — Estados de pedido ──────────────────────────────────
ESTADOS_PEDIDO = [
    ('pendiente',  'Pendiente'),
    ('procesando', 'Procesando'),
    ('enviado',    'Enviado'),
    ('entregado',  'Entregado'),
    ('cancelado',  'Cancelado'),
]


class UsuarioManager(BaseUserManager):
    def create_user(self, email, nombre, password=None, **extra):
        if not email:
            raise ValueError('El correo es obligatorio')
        email = self.normalize_email(email)
        user  = self.model(email=email, nombre=nombre, **extra)
        user.set_password(password)
        user.save(using=self._db)
        return user

    def create_superuser(self, email, nombre, password=None, **extra):
        extra.setdefault('is_staff', True)
        extra.setdefault('is_superuser', True)
        extra.setdefault('email_verificado', True)
        return self.create_user(email, nombre, password, **extra)


class Usuario(AbstractBaseUser, PermissionsMixin):
    # H001.1
    email           = models.EmailField(unique=True)
    nombre          = models.CharField(max_length=150)
    telefono        = models.CharField(max_length=20, blank=True)  # H005.1
    fecha_registro  = models.DateTimeField(auto_now_add=True)

    # H007.1 / H007.2
    email_verificado   = models.BooleanField(default=False)
    token_verificacion = models.UUIDField(default=uuid.uuid4, editable=False)

    # H006.1
    cuenta_activa   = models.BooleanField(default=True)

    is_active = models.BooleanField(default=True)
    is_staff  = models.BooleanField(default=False)

    objects = UsuarioManager()

    USERNAME_FIELD  = 'email'
    REQUIRED_FIELDS = ['nombre']

    class Meta:
        verbose_name        = 'Usuario'
        verbose_name_plural = 'Usuarios'

    def __str__(self):
        return f'{self.nombre} <{self.email}>'


# ── H008 — Dirección de envío ────────────────────────────────
class DireccionEnvio(models.Model):
    usuario        = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='direcciones')
    calle          = models.CharField(max_length=250)
    ciudad         = models.CharField(max_length=100)
    departamento   = models.CharField(max_length=50, choices=DEPARTAMENTOS_PERU)
    codigo_postal  = models.CharField(max_length=10)
    predeterminada = models.BooleanField(default=False)
    creado_en      = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name        = 'Dirección de envío'
        verbose_name_plural = 'Direcciones de envío'
        ordering            = ['-creado_en']

    def __str__(self):
        return f'{self.calle}, {self.ciudad} ({self.departamento})'


# ── H009.2 / H010 — Pedido ──────────────────────────────────
class Pedido(models.Model):
    usuario     = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='pedidos')
    numero      = models.CharField(max_length=20, unique=True, blank=True)
    fecha       = models.DateTimeField(auto_now_add=True)
    monto_total = models.DecimalField(max_digits=10, decimal_places=2)
    estado      = models.CharField(max_length=20, choices=ESTADOS_PEDIDO, default='pendiente')

    class Meta:
        verbose_name        = 'Pedido'
        verbose_name_plural = 'Pedidos'
        ordering            = ['-fecha']

    def save(self, *args, **kwargs):
        is_new = not self.pk
        super().save(*args, **kwargs)
        if is_new and not self.numero:
            from django.utils import timezone
            self.numero = f'MNL-{timezone.now().year}-{self.pk:05d}'
            Pedido.objects.filter(pk=self.pk).update(numero=self.numero)

    def __str__(self):
        return f'#{self.numero}'
