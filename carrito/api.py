from django.utils.translation import gettext as translate
import logging
from django.conf import settings
from decimal import Decimal
from django.db import transaction
from rest_framework import serializers, status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.exceptions import APIException
from productos.models import Producto, Categoria
from usuarios.models import DireccionEnvio, Pedido, PedidoItem, PedidoTimeline
from productos.serializers import ProductoListSerializer
from productos.api import exclude_adult_content
from .models import Carrito, ItemCarrito, CouponUse
from .promotions import calculate_discount
from monolith.validation import integer, StrictIntegerField
from usuarios.api import DireccionSerializer


class SimulatedPaymentSerializer(serializers.Serializer):
    numero_tarjeta = serializers.CharField(max_length=19, required=False)
    cvv = serializers.CharField(max_length=3, required=False)
    nombre_tarjeta = serializers.CharField(max_length=100, required=False, allow_blank=True)
    vencimiento = serializers.CharField(max_length=5, required=False, allow_blank=True)
    referencia = serializers.CharField(max_length=80, required=False, allow_blank=True)


class CheckoutSerializer(serializers.Serializer):
    direccion_id = StrictIntegerField(min_value=1, required=False)
    direccion = DireccionSerializer(required=False)
    metodo_pago = serializers.ChoiceField(choices=['tarjeta', 'transferencia'], default='tarjeta')
    pago = SimulatedPaymentSerializer(required=False, default=dict)

    def validate(self, attrs):
        if not attrs.get('direccion_id') and not attrs.get('direccion'):
            raise serializers.ValidationError({'direccion': translate('Completa la dirección de envío.')})
        if attrs['metodo_pago'] == 'tarjeta':
            payment = attrs['pago']
            if payment.get('numero_tarjeta', '').replace(' ', '') != '4111111111111111' or payment.get('cvv') != '123':
                raise serializers.ValidationError({'pago': translate('Solo se admiten datos de demostración: 4111111111111111, CVV 123. No uses datos bancarios reales.')})
        return attrs

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
def _get_carrito(user, lock=False):
    carrito, _ = Carrito.objects.get_or_create(usuario=user)
    if lock:
        carrito = Carrito.objects.select_for_update().get(pk=carrito.pk)
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
                mensajes.append(translate('%(product)s fue ajustado a %(quantity)s unidades por stock.') % {'product': item.producto.nombre, 'quantity': item.producto.stock})
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
        return {'ok': True, 'mensaje': translate('Carrito vacío.'), 'plataformas_comunes': [], 'detalle': []}
    plataforma_sets = []
    detalle = []
    for item in items:
        names = {
            plataforma.nombre
            for plataforma in item.producto.plataformas.all()
        }
        if names:
            plataforma_sets.append(names)
        detalle.append({'producto': item.producto.nombre, 'plataformas': sorted(names)})
    comunes = sorted(set.intersection(*plataforma_sets)) if plataforma_sets else []
    ok = bool(comunes) or len(plataforma_sets) <= 1
    mensaje = translate('Productos compatibles entre sí.') if ok else translate('Revisa compatibilidad: no todos los productos comparten una misma plataforma.')
    return {'ok': ok, 'mensaje': mensaje, 'plataformas_comunes': comunes, 'detalle': detalle}
def _cart_payload(carrito, mensajes=None, request=None):
    items = list(
        carrito.itemcarrito_set
        .select_related('producto', 'producto__categoria')
        .prefetch_related('producto__plataformas')
    )
    cantidades = {
        item.producto_id: item.cantidad
        for item in items
    }
    contexto = {
        'request': request,
        'cart_quantities': cantidades,
    }
    subtotal = sum(
        (item.subtotal for item in items),
        Decimal('0.00')
    )
    cupon = carrito.codigo_cupon
    descuento,_ = calculate_discount(cupon,carrito.usuario,subtotal,strict=False)
    total = max(
        subtotal - descuento,
        Decimal('0.00')
    ).quantize(Decimal('0.01'))
    categorias_ids = [
        item.producto.categoria_id
        for item in items
        if item.producto.categoria_id
    ]
    productos_ids = [
        item.producto_id for item in items
    ]
    recomendados = (
        exclude_adult_content(
            Producto.objects.filter(
                categoria_id__in=categorias_ids,
                stock__gt=0
            ).exclude(id__in=productos_ids)
        )
        .select_related('categoria')
        .prefetch_related('plataformas')
        .order_by('-ventas')[:4]
    )
    accesorios = []
    cat_acc = Categoria.objects.filter(
        nombre__iexact='Accesorios'
    ).first()
    if cat_acc:
        accesorios = (
            exclude_adult_content(
                Producto.objects.filter(
                    categoria=cat_acc,
                    stock__gt=0
                ).exclude(id__in=productos_ids)
            )
            .select_related('categoria')
            .prefetch_related('plataformas')
            .order_by('-ventas')[:4]
        )
    plataformas = {
        plataforma.nombre
        for item in items
        for plataforma in item.producto.plataformas.all()
    }
    return {
        'items': CartItemSerializer(
            items, many=True, context=contexto
        ).data,
        'subtotal': str(subtotal),
        'cupon': cupon,
        'descuento': str(descuento),
        'total': str(total),
        'cantidad_items': sum(
            item.cantidad for item in items
        ),
        'vacio': not bool(items),
        'plataformas_mezcladas': len(plataformas) > 1,
        'plataformas_carrito': sorted(plataformas),
        'compatibilidad': _compatibilidad(items),
        'recomendados': ProductoListSerializer(
            recomendados, many=True, context=contexto
        ).data,
        'accesorios': ProductoListSerializer(
            accesorios, many=True, context=contexto
        ).data,
        'mensajes': mensajes or [],
    }


@api_view(['GET'])
@permission_classes([IsAuthenticated])
@transaction.atomic
def cart_detail(request):
    carrito = _get_carrito(request.user, lock=True)
    mensajes = _normalize_carrito(carrito)
    return Response(_cart_payload(carrito, mensajes, request))
@api_view(['POST'])
@permission_classes([IsAuthenticated])
@transaction.atomic
def cart_add(request):
    producto_id = integer(request.data.get('producto_id'))
    cantidad = integer(request.data.get('cantidad', 1), maximum=9999)
    try:
        producto = exclude_adult_content(Producto.objects.filter(pk=producto_id)).get()
    except Producto.DoesNotExist:
        return Response({'detail': translate('Producto no disponible.')}, status=status.HTTP_404_NOT_FOUND)
    if producto.stock <= 0:
        return Response({'detail': translate('%(product)s no tiene stock disponible.') % {'product': producto.nombre}}, status=status.HTTP_400_BAD_REQUEST)
    carrito = _get_carrito(request.user, lock=True)
    item, creado = ItemCarrito.objects.get_or_create(
        carrito=carrito,
        producto=producto,
        defaults={'precio_agregado': producto.precio, 'cantidad': 0},
    )
    nueva_cantidad = item.cantidad + cantidad
    if nueva_cantidad > producto.stock:
        if creado:
            item.delete()
        raise serializers.ValidationError({'cantidad': translate('La cantidad excede el stock disponible.')})
    item.cantidad = nueva_cantidad
    item.save()
    return Response(_cart_payload(carrito, request=request))
@api_view(['PATCH', 'DELETE'])
@permission_classes([IsAuthenticated])
@transaction.atomic
def cart_item(request, item_id):
    carrito = _get_carrito(request.user, lock=True)
    try:
        item = ItemCarrito.objects.get(pk=item_id, carrito=carrito)
    except ItemCarrito.DoesNotExist:
        return Response({'detail': translate('Ítem no encontrado.')}, status=status.HTTP_404_NOT_FOUND)
    if request.method == 'DELETE':
        item.delete()
        return Response(_cart_payload(carrito, request=request))
    accion = request.data.get('accion')
    cantidad = request.data.get('cantidad')
    if accion == 'mas':
        if item.cantidad >= item.producto.stock:
            raise serializers.ValidationError({'cantidad': translate('No hay stock adicional.')})
        item.cantidad += 1
    elif accion == 'menos':
        item.cantidad -= 1
    elif cantidad is not None:
        item.cantidad = integer(cantidad, maximum=9999)
        if item.cantidad > item.producto.stock:
            raise serializers.ValidationError({'cantidad': translate('La cantidad excede el stock disponible.')})
    else:
        raise serializers.ValidationError({'accion': translate('Indica mas, menos o una cantidad entera positiva.')})
    if item.cantidad <= 0:
        item.delete()
    else:
        item.save(update_fields=['cantidad'])
    return Response(_cart_payload(carrito, request=request))
@api_view(['POST'])
@permission_classes([IsAuthenticated])
@transaction.atomic
def cart_clear(request):
    carrito = _get_carrito(request.user, lock=True)
    carrito.itemcarrito_set.all().delete()
    carrito.codigo_cupon = ''
    carrito.save(update_fields=['codigo_cupon', 'actualizado'])
    return Response(_cart_payload(carrito, request=request))
@api_view(['POST'])
@permission_classes([IsAuthenticated])
@transaction.atomic
def cart_apply_coupon(request):
    carrito = _get_carrito(request.user, lock=True)
    _normalize_carrito(carrito)
    if carrito.vacio:
        carrito.codigo_cupon = ''
        carrito.save(update_fields=['codigo_cupon', 'actualizado'])
        return Response({'detail': translate('No puedes aplicar un cupón porque el carrito está vacío.')}, status=status.HTTP_400_BAD_REQUEST)
    codigo = str(request.data.get('codigo', '')).strip().upper()
    if not codigo:
        return Response({'detail': translate('Ingresa un código de descuento.')}, status=status.HTTP_400_BAD_REQUEST)
    calculate_discount(codigo,request.user,carrito.subtotal)
    carrito.codigo_cupon = codigo
    carrito.save(update_fields=['codigo_cupon', 'actualizado'])
    return Response(_cart_payload(carrito, mensajes=[translate('Cupón %(code)s aplicado correctamente.') % {'code': codigo}], request=request))
@api_view(['POST'])
@permission_classes([IsAuthenticated])
@transaction.atomic
def cart_remove_coupon(request):
    carrito = _get_carrito(request.user, lock=True)
    carrito.codigo_cupon = ''
    carrito.save(update_fields=['codigo_cupon', 'actualizado'])
    return Response(_cart_payload(carrito, mensajes=[translate('Cupón removido correctamente.')], request=request))
@api_view(['POST'])
@permission_classes([IsAuthenticated])
@transaction.atomic
def cart_checkout(request):
    try:
        from monolith.permissions import VerifiedEmail
        VerifiedEmail().has_permission(request, None)
        serializer = CheckoutSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data
        import hashlib, json
        from monolith.messages import message
        key=serializers.UUIDField().run_validation(request.headers.get('Idempotency-Key'))
        fingerprint=hashlib.sha256(json.dumps(data,sort_keys=True,default=str).encode()).hexdigest()
        carrito = _get_carrito(request.user, lock=True)
        previous=Pedido.objects.filter(usuario=request.user,checkout_key=key).first()
        if previous:
            if previous.checkout_hash!=fingerprint:
                raise serializers.ValidationError({'detail':message('Esta solicitud ya fue procesada con otros datos. Revisa tus pedidos.', 'This request was already processed with different details. Check your orders.')})
            return Response(previous.checkout_response)
        mensajes = []
        direccion_id = data.get('direccion_id')
        direccion_data = data.get('direccion') or {}
        metodo_pago = data['metodo_pago']
        with transaction.atomic():
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
                return Response({'detail': translate('El carrito está vacío.')}, status=status.HTTP_400_BAD_REQUEST)
            productos = {
                p.id: p
                for p in Producto.objects.select_for_update().filter(
                    id__in=[item.producto_id for item in items]
                ).order_by('id')
            }
            insuficientes = []
            for item in items:
                producto = productos.get(item.producto_id)
                if not producto or producto.stock < item.cantidad or producto.stock <= 0:
                    insuficientes.append(item.producto.nombre)
            if insuficientes:
                nombres = ', '.join(insuficientes)
                return Response(
                    {'detail': translate('No hay stock suficiente para completar el pedido: %(products)s.') % {'products': nombres}},
                    status=status.HTTP_400_BAD_REQUEST,
                )
            direccion = None
            if direccion_id:
                try:
                    direccion = request.user.direcciones.select_for_update().get(pk=direccion_id)
                except DireccionEnvio.DoesNotExist:
                    return Response({'detail': translate('Dirección de envío no encontrada.')}, status=status.HTTP_404_NOT_FOUND)
            else:
                required = ['calle', 'ciudad', 'departamento', 'codigo_postal']
                faltantes = [field for field in required if not direccion_data.get(field)]
                if faltantes:
                    return Response(
                        {'detail': translate('Completa la dirección de envío antes de pagar.')},
                        status=status.HTTP_400_BAD_REQUEST,
                    )
                direccion = DireccionEnvio.objects.create(
                    usuario=request.user,
                    calle=direccion_data.get('calle', '').strip(),
                    ciudad=direccion_data.get('ciudad', '').strip(),
                    departamento=direccion_data.get('departamento', '').strip(),
                    codigo_postal=direccion_data.get('codigo_postal', '').strip(),
                    predeterminada=direccion_data.get('predeterminada', False),
                )
                if direccion.predeterminada:
                    request.user.direcciones.exclude(pk=direccion.pk).update(predeterminada=False)
            # Reutiliza los productos ya bloqueados: evita consultas repetidas a Neon.
            subtotal_checkout = sum(
                (productos[item.producto_id].precio * item.cantidad for item in items),
                Decimal('0.00'),
            )
            if any(item.cantidad <= 0 or item.cantidad > 9999 or productos[item.producto_id].precio < 0 or
                   productos[item.producto_id].precio * item.cantidad > Decimal('99999999.99') for item in items):
                raise serializers.ValidationError({'detail': translate('Cantidad o importe fuera de rango.')})
            cupon_checkout = carrito.codigo_cupon
            descuento_checkout,promotion = calculate_discount(cupon_checkout,request.user,subtotal_checkout,lock=True)
            total_checkout = max(subtotal_checkout - descuento_checkout, Decimal('0.00')).quantize(Decimal('0.01'))
            if total_checkout > Decimal('99999999.99'):
                raise serializers.ValidationError({'detail': translate('El total excede el importe máximo permitido.')})
            direccion_texto = f'{direccion.calle}, {direccion.ciudad}, {direccion.departamento} - {direccion.codigo_postal}'
            referencia = f'SIM-{metodo_pago.upper()}-{request.user.id}'
            pedido = Pedido.objects.create(
                usuario=request.user,
                monto_total=total_checkout,
                checkout_key=key,checkout_hash=fingerprint,
                estado='procesando',
                direccion_envio=direccion,
                direccion_texto=direccion_texto,
                metodo_pago=metodo_pago,
                estado_pago='aprobado',
                referencia_pago=referencia,
            )
            if promotion:
                CouponUse.objects.create(promocion=promotion,usuario=request.user,pedido=pedido,descuento=descuento_checkout)
                promotion.usos+=1;promotion.save(update_fields=['usos','actualizado_en'])
            # Preparar operaciones en memoria y enviarlas por lotes a PostgreSQL.
            detalles = []
            productos_actualizados = []
            for item in items:
                producto = productos[item.producto_id]
                detalles.append(PedidoItem(
                    pedido=pedido,
                    producto=producto,
                    producto_nombre=producto.nombre,
                    producto_imagen=_safe_product_image(producto),
                    cantidad=item.cantidad,
                    precio_unitario=producto.precio,
                    subtotal=producto.precio * item.cantidad,
                ))
                producto.stock -= item.cantidad
                from productos.inventory import record_stock
                record_stock(producto,producto.stock+item.cantidad,'venta','Pedido / Order',order=pedido)
                producto.ventas = (producto.ventas or 0) + item.cantidad
                productos_actualizados.append(producto)

            PedidoItem.objects.bulk_create(detalles)
            Producto.objects.bulk_update(productos_actualizados, ['stock', 'ventas'])
            PedidoTimeline.objects.bulk_create([
                PedidoTimeline(
                    pedido=pedido, estado='pendiente', descripcion='Pedido recibido.'
                ),
                PedidoTimeline(
                    pedido=pedido, estado='procesando',
                    descripcion='Pago simulado aprobado. Preparando entrega.'
                ),
            ])

            carrito.itemcarrito_set.all().delete()
            carrito.codigo_cupon = ''
            carrito.save(update_fields=['codigo_cupon', 'actualizado'])
        response = {
            'message': translate('Pedido creado correctamente.'),
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
                'compatibilidad': {'ok': True, 'mensaje': translate('Carrito vacío.'), 'plataformas_comunes': [], 'detalle': []},
                'recomendados': [],
                'accesorios': [],
                'mensajes': mensajes or [],
            },
        }
        pedido.checkout_response=response
        pedido.save(update_fields=['checkout_response'])
        return Response(response,status=status.HTTP_201_CREATED)
    except APIException:
        raise
    except Exception as exc:
        transaction.set_rollback(True)
        logger.error('Checkout failure type=%s user_id=%s',type(exc).__name__,getattr(request.user,'id',None))
        detail = translate('No se pudo completar el checkout por un error interno del servidor.')
        return Response({'detail': detail}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
