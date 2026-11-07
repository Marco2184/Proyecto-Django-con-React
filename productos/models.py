from django.utils.translation import gettext_lazy as translate
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

    def __str__(self): return str(translate(self.nombre))
    class Meta: ordering = ['nombre']
    verbose_name_plural = translate('Categorías')


# ── H011–H020 — Producto ──────────────────────────────────────
class Producto(models.Model):
    def clean(self):
        from django.core.exceptions import ValidationError
        errors = {}
        if self.precio is not None and self.precio < 0:
            errors['precio'] = translate('El precio no puede ser negativo.')
        if self.precio_original is not None and self.precio is not None and self.precio_original < self.precio:
            errors['precio_original'] = translate('El precio original no puede ser menor al actual.')
        if self.valoracion is not None and not 0 <= self.valoracion <= 5:
            errors['valoracion'] = translate('La valoración debe estar entre 0 y 5.')
        if not isinstance(self.especificaciones, dict):
            errors['especificaciones'] = translate('Se requiere un objeto JSON.')
        if errors:
            raise ValidationError(errors)

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
                                           help_text=translate('Si tiene descuento, precio antes del descuento'))

    # H017
    stock        = models.PositiveIntegerField(default=0)

    # H018.1 — imagen principal
    imagen_principal = models.ImageField(upload_to='productos/', blank=True, null=True)
    imagen_url       = models.URLField(blank=True,
                                        help_text=translate('URL externa de imagen (alternativa a subir archivo)'))

    # H019/H020
    ventas       = models.PositiveIntegerField(default=0, help_text=translate('Contador para popularidad'))
    valoracion   = models.DecimalField(max_digits=3, decimal_places=1, default=0)

    # H015.2 — especificaciones técnicas (JSON)
    especificaciones = models.JSONField(default=dict, blank=True,
                                         help_text=translate('Ej: {"RAM":"16GB","CPU":"i7"}'))

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
        from .covers import catalog_cover
        cover = catalog_cover(self)
        if cover is not None:
            return cover['url']
        if self.imagen_principal:
            return self.imagen_principal.url
        return self.imagen_url or ''

    def __str__(self): return self.nombre
    class Meta:
        ordering = ['-activo']
        verbose_name_plural = translate('Productos')


# ── H018.2 — Galería de imágenes ─────────────────────────────
class Review(models.Model):
    producto = models.ForeignKey(Producto,on_delete=models.CASCADE,related_name='reviews')
    usuario = models.ForeignKey('usuarios.Usuario',on_delete=models.CASCADE,related_name='reviews')
    compra = models.ForeignKey('usuarios.PedidoItem',null=True,on_delete=models.SET_NULL)
    puntuacion = models.PositiveSmallIntegerField()
    comentario = models.TextField(max_length=2000)
    visible = models.BooleanField(default=True)
    motivo_moderacion = models.CharField(max_length=250,blank=True)
    moderador = models.ForeignKey('usuarios.Usuario',null=True,blank=True,on_delete=models.SET_NULL,related_name='moderated_reviews')
    creado_en = models.DateTimeField(auto_now_add=True)
    actualizado_en = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-creado_en','-pk']
        constraints = [models.UniqueConstraint(fields=['producto','usuario'],name='review_user_product_unique'),models.CheckConstraint(condition=models.Q(puntuacion__gte=1,puntuacion__lte=5),name='review_rating_one_to_five')]
        indexes = [models.Index(fields=['producto','visible','-creado_en'])]


class StockMovement(models.Model):
    producto = models.ForeignKey(Producto, null=True, on_delete=models.SET_NULL, related_name='stock_movements')
    producto_nombre = models.CharField(max_length=200)
    administrador = models.ForeignKey('usuarios.Usuario', null=True, blank=True, on_delete=models.SET_NULL)
    administrador_nombre = models.CharField(max_length=150, blank=True)
    pedido = models.ForeignKey('usuarios.Pedido', null=True, blank=True, on_delete=models.SET_NULL)
    tipo = models.CharField(max_length=20, choices=[('inicial','Inicial'),('ajuste','Ajuste'),('venta','Venta'),('cancelacion','Cancelación')])
    cantidad = models.IntegerField()
    stock_anterior = models.PositiveIntegerField()
    stock_posterior = models.PositiveIntegerField()
    motivo = models.CharField(max_length=250)
    creado_en = models.DateTimeField(auto_now_add=True)
    request_id = models.UUIDField(null=True, blank=True, unique=True)

    class Meta:
        ordering = ['-creado_en','-pk']
        indexes = [models.Index(fields=['producto','-creado_en'])]
        constraints = [models.CheckConstraint(condition=models.Q(stock_posterior=models.F('stock_anterior')+models.F('cantidad')),name='stock_movement_balanced')]


class ImagenProducto(models.Model):
    producto = models.ForeignKey(Producto, on_delete=models.CASCADE, related_name='galeria')
    imagen   = models.ImageField(upload_to='productos/galeria/', blank=True)
    url      = models.URLField(blank=True)
    orden    = models.PositiveIntegerField(default=0)

    def __str__(self): return f'Imagen #{self.orden} — {self.producto.nombre}'
    class Meta: ordering = ['orden']
