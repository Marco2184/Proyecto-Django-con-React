from decimal import Decimal
from django.db import models
from django.conf import settings
from productos.models import Producto


CUPONES_DISPONIBLES = {
    'MONOLITH10': {'tipo': 'porcentaje', 'valor': Decimal('10')},
    'GAMER20': {'tipo': 'porcentaje', 'valor': Decimal('20')},
    'NEON50': {'tipo': 'fijo', 'valor': Decimal('50')},
}


class Promotion(models.Model):
    codigo = models.CharField(max_length=30,unique=True)
    tipo = models.CharField(max_length=15,choices=[('porcentaje','Porcentaje'),('fijo','Monto fijo')])
    valor = models.DecimalField(max_digits=10,decimal_places=2)
    activo = models.BooleanField(default=True)
    inicio = models.DateTimeField(null=True,blank=True)
    vencimiento = models.DateTimeField(null=True,blank=True)
    limite_total = models.PositiveIntegerField(null=True,blank=True)
    limite_usuario = models.PositiveIntegerField(null=True,blank=True)
    minimo_compra = models.DecimalField(max_digits=10,decimal_places=2,default=0)
    descuento_maximo = models.DecimalField(max_digits=10,decimal_places=2,null=True,blank=True)
    usos = models.PositiveIntegerField(default=0)
    actualizado_en = models.DateTimeField(auto_now=True)

    class Meta:
        ordering=['codigo']
        constraints=[models.UniqueConstraint(models.functions.Lower('codigo'),name='promotion_code_case_unique'),
            models.CheckConstraint(condition=models.Q(valor__gt=0)&(models.Q(tipo='fijo')|models.Q(tipo='porcentaje',valor__lte=100)),name='promotion_valid_value'),
            models.CheckConstraint(condition=models.Q(minimo_compra__gte=0),name='promotion_minimum_nonnegative'),
            models.CheckConstraint(condition=models.Q(descuento_maximo__isnull=True)|models.Q(descuento_maximo__gte=0),name='promotion_maximum_nonnegative'),
            models.CheckConstraint(condition=models.Q(limite_total__isnull=True)|models.Q(limite_total__gt=0),name='promotion_positive_total_limit'),
            models.CheckConstraint(condition=models.Q(limite_usuario__isnull=True)|models.Q(limite_usuario__gt=0),name='promotion_positive_user_limit'),
            models.CheckConstraint(condition=models.Q(vencimiento__isnull=True)|models.Q(inicio__isnull=True)|models.Q(vencimiento__gt=models.F('inicio')),name='promotion_dates_ordered')]


class CouponUse(models.Model):
    promocion = models.ForeignKey(Promotion,on_delete=models.PROTECT,related_name='redenciones')
    usuario = models.ForeignKey(settings.AUTH_USER_MODEL,on_delete=models.CASCADE)
    pedido = models.OneToOneField('usuarios.Pedido',on_delete=models.CASCADE)
    descuento = models.DecimalField(max_digits=10,decimal_places=2)
    creado_en = models.DateTimeField(auto_now_add=True)
    class Meta:
        indexes=[models.Index(fields=['promocion','usuario'])]


class Carrito(models.Model):
    """Carrito de compras de un usuario."""
    usuario     = models.OneToOneField(settings.AUTH_USER_MODEL,
                                        on_delete=models.CASCADE, related_name='carrito')
    codigo_cupon = models.CharField(max_length=30, blank=True, default='')
    creado      = models.DateTimeField(auto_now_add=True)
    actualizado = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f'Carrito de {self.usuario.nombre}'

    @property
    def items(self):
        return self.itemcarrito_set.select_related('producto').all()

    @property
    def subtotal(self):
        return sum((i.subtotal for i in self.items), Decimal('0.00'))

    @property
    def cupon(self):
        codigo = (self.codigo_cupon or '').strip().upper()
        return codigo if Promotion.objects.filter(codigo=codigo).exists() else ''

    @property
    def descuento(self):
        from .promotions import calculate_discount
        return calculate_discount(self.codigo_cupon,self.usuario,self.subtotal,strict=False)[0]

    @property
    def total(self):
        return max(self.subtotal - self.descuento, Decimal('0.00')).quantize(Decimal('0.01'))

    @property
    def cantidad_items(self):
        return sum(i.cantidad for i in self.items)

    @property
    def vacio(self):
        return not self.itemcarrito_set.exists()


class ItemCarrito(models.Model):
    """Un producto dentro del carrito con su cantidad."""
    carrito   = models.ForeignKey(Carrito, on_delete=models.CASCADE)
    producto  = models.ForeignKey(Producto, on_delete=models.CASCADE)
    cantidad  = models.PositiveIntegerField(default=1)
    # H026.2 — precio al momento de agregar (para detectar cambios)
    precio_agregado = models.DecimalField(max_digits=10, decimal_places=2)
    agregado  = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ('carrito', 'producto')
        ordering = ['-agregado']

    def __str__(self):
        return f'{self.cantidad}x {self.producto.nombre}'

    @property
    def subtotal(self):
        return self.producto.precio * self.cantidad

    @property
    def precio_cambio(self):
        """H026.2 — True si el precio cambió desde que se agregó."""
        return self.producto.precio != self.precio_agregado

    @property
    def stock_insuficiente(self):
        """H027 — True si la cantidad supera el stock disponible."""
        return self.cantidad > self.producto.stock
