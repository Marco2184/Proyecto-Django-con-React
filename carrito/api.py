from rest_framework import serializers, status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from productos.models import Producto, Categoria
from productos.serializers import ProductoListSerializer
from productos.api import exclude_adult_content
from .models import Carrito, ItemCarrito


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


def _cart_payload(carrito, mensajes=None):
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
        'items': CartItemSerializer(items, many=True).data,
        'total': str(carrito.total),
        'cantidad_items': carrito.cantidad_items,
        'vacio': carrito.vacio,
        'plataformas_mezcladas': len(plataformas) > 1,
        'plataformas_carrito': sorted(plataformas),
        'compatibilidad': _compatibilidad(items),
        'recomendados': ProductoListSerializer(recomendados, many=True).data,
        'accesorios': ProductoListSerializer(accesorios, many=True).data,
        'mensajes': mensajes or [],
    }


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def cart_detail(request):
    carrito = _get_carrito(request.user)
    mensajes = _normalize_carrito(carrito)
    return Response(_cart_payload(carrito, mensajes))


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
    return Response(_cart_payload(carrito))


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
        return Response(_cart_payload(carrito))
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
    return Response(_cart_payload(carrito))


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def cart_clear(request):
    carrito = _get_carrito(request.user)
    carrito.itemcarrito_set.all().delete()
    return Response(_cart_payload(carrito))
