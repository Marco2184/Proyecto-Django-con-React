from .models import StockMovement
from django.db import transaction


def record_stock(product, before, kind, reason, actor=None, order=None):
    delta = product.stock-before
    if not delta: return None
    return StockMovement.objects.create(producto=product,producto_nombre=product.nombre,
        stock_anterior=before,stock_posterior=product.stock,cantidad=delta,tipo=kind,motivo=reason,
        administrador=actor,administrador_nombre=actor.nombre if actor else '',pedido=order)


@transaction.atomic
def create_imported_product(**data):
    from .models import Producto
    product=Producto.objects.create(**data)
    record_stock(product,0,'inicial','Importación / Import')
    return product
