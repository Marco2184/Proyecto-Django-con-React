from django.db import models
from django.utils.text import slugify


# ── H013/H014 — Plataforma y Categoría ───────────────────────
class Plataforma(models.Model):
    nombre = models.CharField(max_length=50, unique=True)
    slug   = models.SlugField(unique=True, blank=True)
    icono  = models.CharField(max_length=50, blank=True)  # fa class

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = slugify(self.nombre)
        super().save(*args, **kwargs)

    def __str__(self): return self.nombre
    class Meta: ordering = ['nombre']


class Categoria(models.Model):
    nombre = models.CharField(max_length=100, unique=True)
    slug   = models.SlugField(unique=True, blank=True)
    padre  = models.ForeignKey('self', null=True, blank=True,
                                on_delete=models.SET_NULL, related_name='subcategorias')

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = slugify(self.nombre)
        super().save(*args, **kwargs)

    def __str__(self): return self.nombre
    class Meta: ordering = ['nombre']
    verbose_name_plural = 'Categorías'


# ── H011–H020 — Producto ──────────────────────────────────────
class Producto(models.Model):
    nombre       = models.CharField(max_length=200)
    slug         = models.SlugField(unique=True, blank=True, max_length=250)
    descripcion  = models.TextField(blank=True)
    categoria    = models.ForeignKey(Categoria, on_delete=models.SET_NULL,
                                     null=True, blank=True, related_name='productos')
    plataformas  = models.ManyToManyField(Plataforma, blank=True, related_name='productos')

    # H016.1 / H016.2
    precio       = models.DecimalField(max_digits=10, decimal_places=2)
    precio_original = models.DecimalField(max_digits=10, decimal_places=2,
                                           null=True, blank=True,
                                           help_text='Si tiene descuento, precio antes del descuento')

    # H017
    stock        = models.PositiveIntegerField(default=0)

    # H018.1 — imagen principal
    imagen_principal = models.ImageField(upload_to='productos/', blank=True, null=True)
    imagen_url       = models.URLField(blank=True,
                                        help_text='URL externa de imagen (alternativa a subir archivo)')

    # H019/H020
    ventas       = models.PositiveIntegerField(default=0, help_text='Contador para popularidad')
    valoracion   = models.DecimalField(max_digits=3, decimal_places=1, default=0)

    # H015.2 — especificaciones técnicas (JSON)
    especificaciones = models.JSONField(default=dict, blank=True,
                                         help_text='Ej: {"RAM":"16GB","CPU":"i7"}')

    activo       = models.DateTimeField(auto_now_add=True)
    actualizado  = models.DateTimeField(auto_now=True)

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = slugify(self.nombre)
        super().save(*args, **kwargs)

    @property
    def tiene_descuento(self):
        return self.precio_original and self.precio_original > self.precio

    @property
    def porcentaje_descuento(self):
        if self.tiene_descuento:
            return int((1 - self.precio / self.precio_original) * 100)
        return 0

    @property
    def disponible(self):
        return self.stock > 0

    @property
    def imagen(self):
        if self.imagen_principal:
            return self.imagen_principal.url
        return self.imagen_url or ''

    def __str__(self): return self.nombre
    class Meta:
        ordering = ['-activo']
        verbose_name_plural = 'Productos'


# ── H018.2 — Galería de imágenes ─────────────────────────────
class ImagenProducto(models.Model):
    producto = models.ForeignKey(Producto, on_delete=models.CASCADE, related_name='galeria')
    imagen   = models.ImageField(upload_to='productos/galeria/', blank=True)
    url      = models.URLField(blank=True)
    orden    = models.PositiveIntegerField(default=0)

    def __str__(self): return f'Imagen #{self.orden} — {self.producto.nombre}'
    class Meta: ordering = ['orden']
