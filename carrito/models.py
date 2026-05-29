from django.db import models
from django.conf import settings
from productos.models import Producto


class Carrito(models.Model):
    """Carrito de compras de un usuario."""
    usuario     = models.OneToOneField(settings.AUTH_USER_MODEL,
                                        on_delete=models.CASCADE, related_name='carrito')
    creado      = models.DateTimeField(auto_now_add=True)
    actualizado = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f'Carrito de {self.usuario.nombre}'

    @property
    def items(self):
        return self.itemcarrito_set.select_related('producto').all()

    @property
    def total(self):
        return sum(i.subtotal for i in self.items)

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
