from django.utils.translation import gettext as translate
"""The single write path for existing order state changes."""
from django.db import transaction
from django.utils import timezone
from rest_framework.exceptions import NotFound, ValidationError
from productos.models import Producto
from .models import Pedido, PedidoTimeline

TRANSITIONS = {
    'pendiente': {'procesando', 'cancelado'},
    'procesando': {'enviado', 'cancelado'},
    'enviado': {'entregado'},
    'entregado': set(),
    'cancelado': set(),
}


@transaction.atomic
def transition_order(pk, state, *, owner_id=None, reason='', source='administración',actor=None):
    if not isinstance(state, str) or state not in TRANSITIONS:
        raise ValidationError({'estado': translate('Estado de pedido inválido.')})
    if not isinstance(reason, str) or len(reason) > 250:
        raise ValidationError({'motivo_cancelacion': translate('Usa texto de hasta 250 caracteres.')})
    orders = Pedido.objects.select_for_update()
    if owner_id is not None:
        orders = orders.filter(usuario_id=owner_id)
    try:
        order = orders.get(pk=pk)
    except Pedido.DoesNotExist:
        raise NotFound(translate('Pedido no encontrado.'))
    if state == order.estado:
        return order  # Idempotent: no extra timeline, stock or sales mutations.
    if state not in TRANSITIONS.get(order.estado, set()):
        raise ValidationError({'estado': translate('Transición de pedido no permitida.')})
    if state == 'cancelado':
        if not order.puede_cancelar:
            raise ValidationError({'estado': order.motivo_no_cancelable})
        quantities = {}
        for item in order.items.all():
            if item.producto_id and order.estado_pago == 'aprobado':
                quantities[item.producto_id] = quantities.get(item.producto_id, 0) + item.cantidad
        products = list(Producto.objects.select_for_update().filter(pk__in=quantities).order_by('pk'))
        for product in products:
            before=product.stock
            product.stock += quantities[product.pk]
            from productos.inventory import record_stock
            record_stock(product,before,'cancelacion',reason or 'Cancelación / Cancellation',actor=actor,order=order)
            product.ventas = max(0, product.ventas - quantities[product.pk])
        if products:
            Producto.objects.bulk_update(products, ['stock', 'ventas'])
        order.cancelado_en = timezone.now()
        order.motivo_cancelacion = reason.strip() or f'Cancelado por {source}.'
    elif state in {'procesando', 'enviado', 'entregado'} and order.estado_pago != 'aprobado':
        raise ValidationError({'estado': translate('El pago simulado debe estar aprobado.')})
    if state == 'entregado':
        order.entregado_en = timezone.now()
    order.estado = state
    order.save(update_fields=['estado', 'entregado_en', 'cancelado_en', 'motivo_cancelacion'])
    PedidoTimeline.objects.create(pedido=order, estado=state, descripcion=f'Estado actualizado por {source}: {state}.')
    return order
