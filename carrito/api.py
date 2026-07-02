import logging

from django.conf import settings
from django.db import transaction
from rest_framework import serializers, status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from productos.models import Producto, Categoria
from usuarios.models import DireccionEnvio, Pedido, PedidoItem, PedidoTimeline
from productos.serializers import ProductoListSerializer
from productos.api import exclude_adult_content
from .models import Carrito, ItemCarrito, CUPONES_DISPONIBLES


logger = logging.getLogger(__name__)


def _safe_product_image(producto):
    """Devuelve una imagen segura para PedidoItem.producto_imagen.

    Ese campo es URLField y en la BD suele tener límite de 200 caracteres.
    Algunas URLs externas de juegos son largas; si se guardan completas,
    PostgreSQL puede lanzar DataError y romper el checkout con error 500.
    """
    image = getattr(producto, 'imagen_url', '') or ''
    if not image and getattr(producto, 'imagen_principal', None):
        try:
            image = producto.imagen_principal.url or ''
        except Exception:
            image = ''
    return str(image)[:200]


def _get_carrito(user):
    carrito, _ = Carrito.objects.get_or_create(usuario=user)
    return carrito


def _normalize_carrito(carrito):
    mensajes = []
    for item in list(carrito.items):
        if item.cantidad > item.producto.stock:
            if item.producto.stock <= 0:
                mensajes.append(f'{item.producto.nombre} se quedó sin stock y fue removido.')
                item.delete()
            else:
                item.cantidad = item.producto.stock
                item.save(update_fields=['cantidad'])
                mensajes.append(f'{item.producto.nombre} fue ajustado a {item.producto.stock} unidades por stock.')
    return mensajes


class CartItemSerializer(serializers.ModelSerializer):
    producto = ProductoListSerializer(read_only=True)
    subtotal = serializers.SerializerMethodField()
    precio_cambio = serializers.SerializerMethodField()
    stock_insuficiente = serializers.SerializerMethodField()

    class Meta:
        model = ItemCarrito
        fields = ['id', 'producto', 'cantidad', 'precio_agregado', 'agregado', 'subtotal', 'precio_cambio', 'stock_insuficiente']

    def get_subtotal(self, obj):
        return str(obj.subtotal)

    def get_precio_cambio(self, obj):
        return obj.precio_cambio

    def get_stock_insuficiente(self, obj):
        return obj.stock_insuficiente


def _compatibilidad(items):
    if not items:
        return {'ok': True, 'mensaje': 'Carrito vacío.', 'plataformas_comunes': [], 'detalle': []}
    plataforma_sets = []
    detalle = []
    for item in items:
        names = set(item.producto.plataformas.values_list('nombre', flat=True))
        if names:
            plataforma_sets.append(names)
        detalle.append({'producto': item.producto.nombre, 'plataformas': sorted(names)})
    comunes = sorted(set.intersection(*plataforma_sets)) if plataforma_sets else []
    ok = bool(comunes) or len(plataforma_sets) <= 1
    mensaje = 'Productos compatibles entre sí.' if ok else 'Revisa compatibilidad: no todos los productos comparten una misma plataforma.'
    return {'ok': ok, 'mensaje': mensaje, 'plataformas_comunes': comunes, 'detalle': detalle}


def _cart_payload(carrito, mensajes=None, request=None):
    items = list(carrito.items)
    categorias_ids = [i.producto.categoria_id for i in items if i.producto.categoria_id]
    productos_ids = [i.producto_id for i in items]
    recomendados = exclude_adult_content(Producto.objects.filter(categoria_id__in=categorias_ids, stock__gt=0).exclude(id__in=productos_ids)).order_by('-ventas')[:4]
    accesorios = []
    cat_acc = Categoria.objects.filter(nombre__iexact='Accesorios').first()
    if cat_acc:
        accesorios = exclude_adult_content(Producto.objects.filter(categoria=cat_acc, stock__gt=0).exclude(id__in=productos_ids)).order_by('-ventas')[:4]
    plataformas = set()
    for item in items:
        for plataforma in item.producto.plataformas.all():
            plataformas.add(plataforma.nombre)
    return {
        'items': CartItemSerializer(items, many=True, context={'request': request}).data,
        'subtotal': str(carrito.subtotal),
        'cupon': carrito.cupon,
        'descuento': str(carrito.descuento),
        'total': str(carrito.total),
        'cantidad_items': carrito.cantidad_items,
        'vacio': carrito.vacio,
        'plataformas_mezcladas': len(plataformas) > 1,
        'plataformas_carrito': sorted(plataformas),
        'compatibilidad': _compatibilidad(items),
        'recomendados': ProductoListSerializer(recomendados, many=True, context={'request': request}).data,
        'accesorios': ProductoListSerializer(accesorios, many=True, context={'request': request}).data,
        'mensajes': mensajes or [],
    }


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def cart_detail(request):
    carrito = _get_carrito(request.user)
    mensajes = _normalize_carrito(carrito)
    return Response(_cart_payload(carrito, mensajes, request))


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def cart_add(request):
    producto_id = request.data.get('producto_id')
    cantidad = int(request.data.get('cantidad', 1) or 1)
    try:
        producto = exclude_adult_content(Producto.objects.filter(pk=producto_id)).get()
    except Producto.DoesNotExist:
        return Response({'detail': 'Producto no disponible.'}, status=status.HTTP_404_NOT_FOUND)
    if producto.stock <= 0:
        return Response({'detail': f'{producto.nombre} no tiene stock disponible.'}, status=status.HTTP_400_BAD_REQUEST)
    carrito = _get_carrito(request.user)
    item, creado = ItemCarrito.objects.get_or_create(
        carrito=carrito,
        producto=producto,
        defaults={'precio_agregado': producto.precio, 'cantidad': 0},
    )
    nueva_cantidad = item.cantidad + max(cantidad, 1)
    item.cantidad = min(nueva_cantidad, producto.stock)
    item.save()
    return Response(_cart_payload(carrito, request=request))


@api_view(['PATCH', 'DELETE'])
@permission_classes([IsAuthenticated])
def cart_item(request, item_id):
    carrito = _get_carrito(request.user)
    try:
        item = ItemCarrito.objects.get(pk=item_id, carrito=carrito)
    except ItemCarrito.DoesNotExist:
        return Response({'detail': 'Ítem no encontrado.'}, status=status.HTTP_404_NOT_FOUND)
    if request.method == 'DELETE':
        item.delete()
        return Response(_cart_payload(carrito, request=request))
    accion = request.data.get('accion')
    cantidad = request.data.get('cantidad')
    if accion == 'mas':
        item.cantidad = min(item.cantidad + 1, item.producto.stock)
    elif accion == 'menos':
        item.cantidad -= 1
    elif cantidad is not None:
        item.cantidad = min(max(int(cantidad), 1), item.producto.stock)
    if item.cantidad <= 0:
        item.delete()
    else:
        item.save(update_fields=['cantidad'])
    return Response(_cart_payload(carrito, request=request))


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def cart_clear(request):
    carrito = _get_carrito(request.user)
    carrito.itemcarrito_set.all().delete()
    carrito.codigo_cupon = ''
    carrito.save(update_fields=['codigo_cupon', 'actualizado'])
    return Response(_cart_payload(carrito, request=request))


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def cart_apply_coupon(request):
    carrito = _get_carrito(request.user)
    _normalize_carrito(carrito)

    if carrito.vacio:
        carrito.codigo_cupon = ''
        carrito.save(update_fields=['codigo_cupon', 'actualizado'])
        return Response({'detail': 'No puedes aplicar un cupón porque el carrito está vacío.'}, status=status.HTTP_400_BAD_REQUEST)

    codigo = str(request.data.get('codigo', '')).strip().upper()
    if not codigo:
        return Response({'detail': 'Ingresa un código de descuento.'}, status=status.HTTP_400_BAD_REQUEST)

    if codigo not in CUPONES_DISPONIBLES:
        return Response({'detail': 'Código de descuento inválido.'}, status=status.HTTP_400_BAD_REQUEST)

    carrito.codigo_cupon = codigo
    carrito.save(update_fields=['codigo_cupon', 'actualizado'])
    return Response(_cart_payload(carrito, mensajes=[f'Cupón {codigo} aplicado correctamente.'], request=request))


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def cart_remove_coupon(request):
    carrito = _get_carrito(request.user)
    carrito.codigo_cupon = ''
    carrito.save(update_fields=['codigo_cupon', 'actualizado'])
    return Response(_cart_payload(carrito, mensajes=['Cupón removido correctamente.'], request=request))


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def cart_checkout(request):
    try:
        carrito = _get_carrito(request.user)
        mensajes = _normalize_carrito(carrito)

        direccion_id = request.data.get('direccion_id')
        direccion_data = request.data.get('direccion') or {}
        metodo_pago = request.data.get('metodo_pago', 'tarjeta')
        pago_data = request.data.get('pago') or {}

        if metodo_pago not in ['tarjeta', 'transferencia']:
            return Response({'detail': 'Método de pago inválido.'}, status=status.HTTP_400_BAD_REQUEST)

        if metodo_pago == 'tarjeta':
            numero_tarjeta = ''.join(ch for ch in str(pago_data.get('numero_tarjeta', '')) if ch.isdigit())
            cvv = ''.join(ch for ch in str(pago_data.get('cvv', '')) if ch.isdigit())
            if len(numero_tarjeta) < 12 or len(cvv) < 3:
                return Response({'detail': 'Datos de tarjeta incompletos para el pago simulado.'}, status=status.HTTP_400_BAD_REQUEST)

        with transaction.atomic():
            direccion = None
            if direccion_id:
                try:
                    direccion = request.user.direcciones.select_for_update().get(pk=direccion_id)
                except DireccionEnvio.DoesNotExist:
                    return Response({'detail': 'Dirección de envío no encontrada.'}, status=status.HTTP_404_NOT_FOUND)
            else:
                required = ['calle', 'ciudad', 'departamento', 'codigo_postal']
                faltantes = [field for field in required if not direccion_data.get(field)]
                if faltantes:
                    return Response(
                        {'detail': 'Completa la dirección de envío antes de pagar.'},
                        status=status.HTTP_400_BAD_REQUEST,
                    )
                direccion = DireccionEnvio.objects.create(
                    usuario=request.user,
                    calle=direccion_data.get('calle', '').strip(),
                    ciudad=direccion_data.get('ciudad', '').strip(),
                    departamento=direccion_data.get('departamento', '').strip(),
                    codigo_postal=direccion_data.get('codigo_postal', '').strip(),
                    predeterminada=bool(direccion_data.get('predeterminada', False)),
                )
                if direccion.predeterminada:
                    request.user.direcciones.exclude(pk=direccion.pk).update(predeterminada=False)

            # Bloqueamos solo los registros del carrito.
            # No se debe usar select_for_update() junto con select_related('producto__categoria')
            # porque categoria puede ser nullable y PostgreSQL lanza:
            # FOR UPDATE cannot be applied to the nullable side of an outer join.
            items = list(
                carrito.itemcarrito_set
                .select_for_update(of=('self',))
                .select_related('producto')
                .prefetch_related('producto__plataformas')
            )

            if not items:
                return Response({'detail': 'El carrito está vacío.'}, status=status.HTTP_400_BAD_REQUEST)

            productos = {
                p.id: p
                for p in Producto.objects.select_for_update().filter(
                    id__in=[item.producto_id for item in items]
                )
            }

            insuficientes = []
            for item in items:
                producto = productos.get(item.producto_id)
                if not producto or producto.stock < item.cantidad or producto.stock <= 0:
                    insuficientes.append(item.producto.nombre)

            if insuficientes:
                nombres = ', '.join(insuficientes)
                return Response(
                    {'detail': f'No hay stock suficiente para completar el pedido: {nombres}.'},
                    status=status.HTTP_400_BAD_REQUEST,
                )

            subtotal_checkout = carrito.subtotal
            cupon_checkout = carrito.cupon
            descuento_checkout = carrito.descuento
            total_checkout = carrito.total

            direccion_texto = f'{direccion.calle}, {direccion.ciudad}, {direccion.departamento} - {direccion.codigo_postal}'
            referencia = f'SIM-{metodo_pago.upper()}-{request.user.id}'

            pedido = Pedido.objects.create(
                usuario=request.user,
                monto_total=total_checkout,
                estado='procesando',
                direccion_envio=direccion,
                direccion_texto=direccion_texto,
                metodo_pago=metodo_pago,
                estado_pago='aprobado',
                referencia_pago=referencia,
            )

            for item in items:
                producto = productos[item.producto_id]
                PedidoItem.objects.create(
                    pedido=pedido,
                    producto=producto,
                    producto_nombre=producto.nombre,
                    producto_imagen=_safe_product_image(producto),
                    cantidad=item.cantidad,
                    precio_unitario=producto.precio,
                    subtotal=item.subtotal,
                )
                producto.stock = max(producto.stock - item.cantidad, 0)
                producto.ventas = (producto.ventas or 0) + item.cantidad
                producto.save(update_fields=['stock', 'ventas'])

            PedidoTimeline.objects.create(
                pedido=pedido,
                estado='pendiente',
                descripcion='Pedido recibido.',
            )
            PedidoTimeline.objects.create(
                pedido=pedido,
                estado='procesando',
                descripcion='Pago simulado aprobado. Preparando entrega.',
            )

            carrito.itemcarrito_set.all().delete()
            carrito.codigo_cupon = ''
            carrito.save(update_fields=['codigo_cupon', 'actualizado'])

        return Response({
            'message': 'Pedido creado correctamente.',
            'pedido': {
                'id': pedido.id,
                'numero': pedido.numero,
                'estado': pedido.estado,
                'estado_pago': pedido.estado_pago,
                'metodo_pago': pedido.metodo_pago,
                'subtotal': str(subtotal_checkout),
                'cupon': cupon_checkout,
                'descuento': str(descuento_checkout),
                'monto_total': str(total_checkout),
                'fecha_estimada_entrega': str(pedido.fecha_estimada_entrega),
            },
            'carrito': {
                'items': [],
                'subtotal': '0.00',
                'cupon': '',
                'descuento': '0.00',
                'total': '0.00',
                'cantidad_items': 0,
                'vacio': True,
                'plataformas_mezcladas': False,
                'plataformas_carrito': [],
                'compatibilidad': {'ok': True, 'mensaje': 'Carrito vacío.', 'plataformas_comunes': [], 'detalle': []},
                'recomendados': [],
                'accesorios': [],
                'mensajes': mensajes or [],
            },
        }, status=status.HTTP_201_CREATED)
    except Exception as exc:
        logger.exception('Error interno en cart_checkout para usuario_id=%s', getattr(request.user, 'id', None))
        detail = 'No se pudo completar el checkout por un error interno del servidor.'
        if settings.DEBUG:
            detail = f'{detail} Detalle: {exc}'
        return Response({'detail': detail}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
