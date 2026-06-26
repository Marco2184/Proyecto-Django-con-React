from decimal import Decimal

from django.db.models import Count, Sum
from django.utils import timezone
from rest_framework import serializers, status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAdminUser
from rest_framework.response import Response

from productos.models import Producto, Plataforma, Categoria
from productos.serializers import ProductoListSerializer, ProductoDetailSerializer, PlataformaSerializer, CategoriaSerializer
from usuarios.models import Usuario, Pedido, PedidoItem, PedidoTimeline, ESTADOS_PEDIDO


class AdminUsuarioSerializer(serializers.ModelSerializer):
    pedidos_count = serializers.IntegerField(read_only=True)

    class Meta:
        model = Usuario
        fields = [
            'id', 'nombre', 'email', 'telefono', 'email_verificado',
            'cuenta_activa', 'is_active', 'is_staff', 'is_superuser',
            'fecha_registro', 'pedidos_count',
        ]
        read_only_fields = ['id', 'email', 'is_superuser', 'fecha_registro', 'pedidos_count']


class AdminPedidoItemSerializer(serializers.ModelSerializer):
    class Meta:
        model = PedidoItem
        fields = [
            'id', 'producto', 'producto_nombre', 'producto_imagen',
            'cantidad', 'precio_unitario', 'subtotal',
        ]


class AdminPedidoSerializer(serializers.ModelSerializer):
    usuario_nombre = serializers.CharField(source='usuario.nombre', read_only=True)
    usuario_email = serializers.EmailField(source='usuario.email', read_only=True)
    items_count = serializers.SerializerMethodField()
    items = AdminPedidoItemSerializer(many=True, read_only=True)

    class Meta:
        model = Pedido
        fields = [
            'id', 'numero', 'fecha', 'usuario', 'usuario_nombre', 'usuario_email',
            'monto_total', 'estado', 'metodo_pago', 'estado_pago', 'referencia_pago',
            'fecha_estimada_entrega', 'direccion_texto', 'entregado_en', 'cancelado_en',
            'motivo_cancelacion', 'items_count', 'items',
        ]
        read_only_fields = [
            'id', 'numero', 'fecha', 'usuario', 'usuario_nombre', 'usuario_email',
            'monto_total', 'metodo_pago', 'estado_pago', 'referencia_pago',
            'direccion_texto', 'items_count', 'items',
        ]

    def get_items_count(self, obj):
        return obj.items.count()


class AdminProductoWriteSerializer(serializers.ModelSerializer):
    categoria_id = serializers.PrimaryKeyRelatedField(
        source='categoria', queryset=Categoria.objects.all(), required=False, allow_null=True
    )
    plataforma_ids = serializers.PrimaryKeyRelatedField(
        source='plataformas', queryset=Plataforma.objects.all(), many=True, required=False
    )

    class Meta:
        model = Producto
        fields = [
            'id', 'nombre', 'slug', 'descripcion', 'categoria_id', 'plataforma_ids',
            'precio', 'precio_original', 'stock', 'imagen_url', 'ventas',
            'valoracion', 'especificaciones',
        ]
        read_only_fields = ['id', 'slug']

    def validate_precio(self, value):
        if value < 0:
            raise serializers.ValidationError('El precio no puede ser negativo.')
        return value

    def validate_stock(self, value):
        if value < 0:
            raise serializers.ValidationError('El stock no puede ser negativo.')
        return value

    def create(self, validated_data):
        plataformas = validated_data.pop('plataformas', [])
        producto = Producto.objects.create(**validated_data)
        producto.plataformas.set(plataformas)
        return producto

    def update(self, instance, validated_data):
        plataformas = validated_data.pop('plataformas', None)
        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        instance.save()
        if plataformas is not None:
            instance.plataformas.set(plataformas)
        return instance


def _money(value):
    return str(value or Decimal('0.00'))


@api_view(['GET'])
@permission_classes([IsAdminUser])
def admin_dashboard(request):
    hoy = timezone.now().date()
    pedidos_qs = Pedido.objects.all()
    productos_qs = Producto.objects.all()

    ventas_total = pedidos_qs.exclude(estado='cancelado').aggregate(total=Sum('monto_total'))['total'] or Decimal('0.00')
    ventas_hoy = pedidos_qs.filter(fecha__date=hoy).exclude(estado='cancelado').aggregate(total=Sum('monto_total'))['total'] or Decimal('0.00')
    pedidos_por_estado = dict(pedidos_qs.values_list('estado').annotate(total=Count('id')))

    ultimos_pedidos = pedidos_qs.select_related('usuario').prefetch_related('items')[:6]
    stock_bajo = productos_qs.filter(stock__lte=5).order_by('stock', 'nombre')[:8]

    return Response({
        'ventas_total': _money(ventas_total),
        'ventas_hoy': _money(ventas_hoy),
        'pedidos_total': pedidos_qs.count(),
        'usuarios_total': Usuario.objects.count(),
        'productos_total': productos_qs.count(),
        'stock_bajo_total': productos_qs.filter(stock__lte=5).count(),
        'pedidos_por_estado': pedidos_por_estado,
        'ultimos_pedidos': AdminPedidoSerializer(ultimos_pedidos, many=True).data,
        'stock_bajo': ProductoListSerializer(stock_bajo, many=True, context={'request': request}).data,
    })


@api_view(['GET', 'POST'])
@permission_classes([IsAdminUser])
def admin_products(request):
    if request.method == 'POST':
        serializer = AdminProductoWriteSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        producto = serializer.save()
        return Response(ProductoDetailSerializer(producto, context={'request': request}).data, status=status.HTTP_201_CREATED)

    q = (request.query_params.get('q') or '').strip()
    stock = request.query_params.get('stock') or ''
    qs = Producto.objects.select_related('categoria').prefetch_related('plataformas').all()

    if q:
        qs = qs.filter(nombre__icontains=q)
    if stock == 'bajo':
        qs = qs.filter(stock__lte=5)
    elif stock == 'sin_stock':
        qs = qs.filter(stock=0)

    qs = qs.order_by('-actualizado')[:100]
    return Response(ProductoDetailSerializer(qs, many=True, context={'request': request}).data)


@api_view(['GET', 'PATCH', 'DELETE'])
@permission_classes([IsAdminUser])
def admin_product_detail(request, pk):
    try:
        producto = Producto.objects.select_related('categoria').prefetch_related('plataformas').get(pk=pk)
    except Producto.DoesNotExist:
        return Response({'detail': 'Producto no encontrado.'}, status=status.HTTP_404_NOT_FOUND)

    if request.method == 'DELETE':
        producto.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)

    if request.method == 'PATCH':
        serializer = AdminProductoWriteSerializer(producto, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        producto = serializer.save()

    return Response(ProductoDetailSerializer(producto, context={'request': request}).data)


@api_view(['GET'])
@permission_classes([IsAdminUser])
def admin_catalog_options(request):
    return Response({
        'categorias': CategoriaSerializer(Categoria.objects.filter(padre__isnull=True).prefetch_related('subcategorias'), many=True).data,
        'plataformas': PlataformaSerializer(Plataforma.objects.all(), many=True).data,
    })


@api_view(['GET'])
@permission_classes([IsAdminUser])
def admin_orders(request):
    estado = request.query_params.get('estado') or ''
    q = (request.query_params.get('q') or '').strip()
    qs = Pedido.objects.select_related('usuario').prefetch_related('items').all()

    if estado:
        qs = qs.filter(estado=estado)
    if q:
        qs = qs.filter(numero__icontains=q) | qs.filter(usuario__email__icontains=q) | qs.filter(usuario__nombre__icontains=q)

    return Response(AdminPedidoSerializer(qs[:100], many=True).data)


@api_view(['GET', 'PATCH'])
@permission_classes([IsAdminUser])
def admin_order_detail(request, pk):
    try:
        pedido = Pedido.objects.select_related('usuario').prefetch_related('items', 'timeline').get(pk=pk)
    except Pedido.DoesNotExist:
        return Response({'detail': 'Pedido no encontrado.'}, status=status.HTTP_404_NOT_FOUND)

    if request.method == 'PATCH':
        nuevo_estado = request.data.get('estado')
        motivo = (request.data.get('motivo_cancelacion') or '').strip()
        estados_validos = [estado for estado, _label in ESTADOS_PEDIDO]

        if nuevo_estado not in estados_validos:
            return Response({'detail': 'Estado de pedido inválido.'}, status=status.HTTP_400_BAD_REQUEST)

        pedido.estado = nuevo_estado
        if nuevo_estado == 'entregado' and not pedido.entregado_en:
            pedido.entregado_en = timezone.now()
        if nuevo_estado == 'cancelado':
            pedido.cancelado_en = timezone.now()
            pedido.motivo_cancelacion = motivo or 'Cancelado desde panel administrador.'
        pedido.save(update_fields=['estado', 'entregado_en', 'cancelado_en', 'motivo_cancelacion'])
        PedidoTimeline.objects.create(
            pedido=pedido,
            estado=nuevo_estado,
            descripcion=f'Estado actualizado desde administración: {nuevo_estado}.',
        )

    return Response(AdminPedidoSerializer(pedido).data)


@api_view(['GET', 'PATCH'])
@permission_classes([IsAdminUser])
def admin_users(request):
    if request.method == 'PATCH':
        user_id = request.data.get('id')
        try:
            usuario = Usuario.objects.get(pk=user_id)
        except Usuario.DoesNotExist:
            return Response({'detail': 'Usuario no encontrado.'}, status=status.HTTP_404_NOT_FOUND)

        if usuario == request.user and request.data.get('is_staff') is False:
            return Response({'detail': 'No puedes quitarte el rol administrador a ti mismo.'}, status=status.HTTP_400_BAD_REQUEST)

        serializer = AdminUsuarioSerializer(usuario, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(AdminUsuarioSerializer(usuario).data)

    q = (request.query_params.get('q') or '').strip()
    qs = Usuario.objects.annotate(pedidos_count=Count('pedidos')).order_by('-fecha_registro')
    if q:
        qs = qs.filter(email__icontains=q) | qs.filter(nombre__icontains=q)
    return Response(AdminUsuarioSerializer(qs[:100], many=True).data)
