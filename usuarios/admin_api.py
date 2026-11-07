from django.utils.translation import gettext as translate
from decimal import Decimal

from django.db.models import Count, Sum
from django.db import transaction
from monolith.validation import StrictIntegerField
from django.utils import timezone
from rest_framework import serializers, status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAdminUser
from monolith.permissions import VerifiedAdminWrites
from rest_framework.pagination import PageNumberPagination
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
        read_only_fields = ['id', 'email', 'fecha_registro', 'pedidos_count']


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


class AdminProductoReadSerializer(ProductoListSerializer):
    class Meta(ProductoListSerializer.Meta):
        fields=ProductoListSerializer.Meta.fields+['descripcion']


def admin_page(qs,serializer,request,context=None):
    pager=PageNumberPagination();rows=pager.paginate_queryset(qs,request)
    return pager.get_paginated_response(serializer(rows,many=True,context=context or {}).data)


class AdminProductoWriteSerializer(serializers.ModelSerializer):
    motivo_stock = serializers.CharField(write_only=True, required=False, max_length=250)
    stock = StrictIntegerField(min_value=0, max_value=2147483647, required=False)
    precio = serializers.DecimalField(max_digits=10, decimal_places=2, min_value=Decimal('0.00'))
    precio_original = serializers.DecimalField(max_digits=10, decimal_places=2, min_value=Decimal('0.00'), required=False, allow_null=True)
    valoracion = serializers.DecimalField(max_digits=3, decimal_places=1, min_value=0, max_value=5, required=False)

    def validate(self, attrs):
        price = attrs.get('precio', getattr(self.instance, 'precio', None))
        original = attrs.get('precio_original', getattr(self.instance, 'precio_original', None))
        if original is not None and price is not None and original < price:
            raise serializers.ValidationError({'precio_original': translate('El precio original no puede ser menor al precio actual.')})
        if 'especificaciones' in attrs and not isinstance(attrs['especificaciones'], dict):
            raise serializers.ValidationError({'especificaciones': translate('Se requiere un objeto JSON.')})
        if self.instance and 'stock' in attrs and attrs['stock']!=self.instance.stock and not attrs.get('motivo_stock','').strip():
            from monolith.messages import message
            raise serializers.ValidationError({'motivo_stock':message('Indica el motivo del ajuste de stock.', 'Provide a reason for the stock adjustment.')})
        return attrs

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
            'valoracion', 'especificaciones', 'motivo_stock',
        ]
        read_only_fields = ['id', 'slug', 'ventas']

    def validate_precio(self, value):
        if value < 0:
            raise serializers.ValidationError(translate('El precio no puede ser negativo.'))
        return value

    def validate_stock(self, value):
        if value < 0:
            raise serializers.ValidationError(translate('El stock no puede ser negativo.'))
        return value

    def create(self, validated_data):
        reason=validated_data.pop('motivo_stock','Stock inicial / Initial stock')
        plataformas = validated_data.pop('plataformas', [])
        producto = Producto.objects.create(**validated_data)
        producto.plataformas.set(plataformas)
        from productos.inventory import record_stock
        record_stock(producto,0,'inicial',reason,self.context['request'].user)
        return producto

    def update(self, instance, validated_data):
        before=instance.stock
        reason=validated_data.pop('motivo_stock','')
        plataformas = validated_data.pop('plataformas', None)
        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        instance.save()
        from productos.inventory import record_stock
        record_stock(instance,before,'ajuste',reason,self.context['request'].user)
        if plataformas is not None:
            instance.plataformas.set(plataformas)
        return instance


def _money(value):
    return str(value or Decimal('0.00'))


def _payload_bool_false(data, field):
    """
    Detecta False aunque venga como booleano real, string o número.
    Sirve para bloquear intentos de autodesactivación desde el panel admin.
    """
    if field not in data:
        return False

    value = data.get(field)

    if value is False:
        return True
    if value in (0, '0'):
        return True
    if isinstance(value, str) and value.strip().lower() in {'false', 'no', 'off'}:
        return True

    return False


def _payload_bool_value(data, field, default=None):
    """
    Lee booleanos enviados por el frontend aunque lleguen como boolean,
    string o número. Devuelve default si el campo no llegó en el payload.
    """
    if field not in data:
        return default

    value = data.get(field)

    if isinstance(value, bool):
        return value
    if value in (1, '1'):
        return True
    if value in (0, '0'):
        return False
    if isinstance(value, str):
        normalized = value.strip().lower()
        if normalized in {'true', 'yes', 'on', 'si', 'sí'}:
            return True
        if normalized in {'false', 'no', 'off'}:
            return False

    return serializers.BooleanField().run_validation(value)


def _active_admins_count(exclude_pk=None):
    """
    Cuenta administradores reales disponibles para operar el panel.
    En DRF IsAdminUser basta con is_staff=True; is_superuser no siempre
    representa el botón Admin del frontend.
    """
    qs = Usuario.objects.filter(
        is_active=True,
        cuenta_activa=True,
        is_staff=True,
    )
    if exclude_pk is not None:
        qs = qs.exclude(pk=exclude_pk)
    return qs.count()


def _is_deleted_user(usuario):
    """
    Detecta cuentas marcadas como eliminadas/anónimas para impedir cambios
    desde el panel administrativo. En Monolith las cuentas eliminadas suelen
    conservarse para no romper pedidos históricos.
    """
    email = (usuario.email or '').strip().lower()
    nombre = (usuario.nombre or '').strip().lower()

    return (
        email.endswith('@monolith.void')
        or email.startswith('deleted_')
        or nombre in {'usuario eliminado', 'deleted user', 'usuario_eliminado'}
    )


@api_view(['GET'])
@permission_classes([IsAdminUser,VerifiedAdminWrites])
def admin_dashboard(request):
    from .admin_extensions import analytics
    extended=analytics(request)
    hoy = timezone.localdate()
    pedidos_qs = Pedido.objects.all()
    productos_qs = Producto.objects.all()

    ventas_total = pedidos_qs.filter(estado_pago='aprobado').exclude(estado='cancelado').aggregate(total=Sum('monto_total'))['total'] or Decimal('0.00')
    ventas_hoy = pedidos_qs.filter(fecha__date=hoy, estado_pago='aprobado').exclude(estado='cancelado').aggregate(total=Sum('monto_total'))['total'] or Decimal('0.00')
    pedidos_por_estado = dict(pedidos_qs.values_list('estado').annotate(total=Count('id')))

    ultimos_pedidos = pedidos_qs.filter(fecha__date__gte=extended['desde'],fecha__date__lte=extended['hasta']).select_related('usuario').prefetch_related('items')[:6]
    stock_bajo = productos_qs.filter(stock__lte=5).order_by('stock', 'nombre')[:8]

    return Response({
        **extended,
        'ventas_total': _money(ventas_total),
        'ventas_hoy': _money(ventas_hoy),
        'pedidos_total': pedidos_qs.count(),
        'usuarios_total': Usuario.objects.count(),
        'productos_total': productos_qs.count(),
        'stock_bajo_total': productos_qs.filter(stock__lte=5).count(),
        'pedidos_por_estado': pedidos_por_estado,
        'ultimos_pedidos': AdminPedidoSerializer(ultimos_pedidos, many=True).data,
        'stock_bajo': ProductoListSerializer(stock_bajo, many=True, context={'request': request,'cart_quantities':{}}).data,
    })


@api_view(['GET', 'POST'])
@permission_classes([IsAdminUser,VerifiedAdminWrites])
@transaction.atomic
def admin_products(request):
    if request.method == 'POST':
        serializer = AdminProductoWriteSerializer(data=request.data, context={'request':request})
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

    qs = qs.order_by('-actualizado','-pk')
    return admin_page(qs,AdminProductoReadSerializer,request,{'request':request,'cart_quantities':{}})


@api_view(['GET', 'PATCH', 'DELETE'])
@permission_classes([IsAdminUser,VerifiedAdminWrites])
@transaction.atomic
def admin_product_detail(request, pk):
    try:
        producto = Producto.objects.select_for_update(of=('self',)).select_related('categoria').prefetch_related('plataformas').get(pk=pk)
    except Producto.DoesNotExist:
        return Response({'detail': translate('Producto no encontrado.')}, status=status.HTTP_404_NOT_FOUND)

    if request.method == 'DELETE':
        producto.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)

    if request.method == 'PATCH':
        serializer = AdminProductoWriteSerializer(producto, data=request.data, partial=True, context={'request':request})
        serializer.is_valid(raise_exception=True)
        producto = serializer.save()

    return Response(ProductoDetailSerializer(producto, context={'request': request}).data)


@api_view(['GET'])
@permission_classes([IsAdminUser,VerifiedAdminWrites])
def admin_catalog_options(request):
    return Response({
        'categorias': CategoriaSerializer(Categoria.objects.filter(padre__isnull=True).prefetch_related('subcategorias'), many=True).data,
        'plataformas': PlataformaSerializer(Plataforma.objects.all(), many=True).data,
    })


@api_view(['GET'])
@permission_classes([IsAdminUser,VerifiedAdminWrites])
def admin_orders(request):
    estado = request.query_params.get('estado') or ''
    q = (request.query_params.get('q') or '').strip()
    qs = Pedido.objects.select_related('usuario').prefetch_related('items').all()

    if estado:
        qs = qs.filter(estado=estado)
    if q:
        qs = qs.filter(numero__icontains=q) | qs.filter(usuario__email__icontains=q) | qs.filter(usuario__nombre__icontains=q)

    return admin_page(qs.order_by('-fecha','-pk'),AdminPedidoSerializer,request)


@api_view(['GET', 'PATCH'])
@permission_classes([IsAdminUser,VerifiedAdminWrites])
def admin_order_detail(request, pk):
    try:
        pedido = Pedido.objects.select_related('usuario').prefetch_related('items', 'timeline').get(pk=pk)
    except Pedido.DoesNotExist:
        return Response({'detail': translate('Pedido no encontrado.')}, status=status.HTTP_404_NOT_FOUND)

    if request.method == 'PATCH':
        from .order_service import transition_order
        pedido = transition_order(pk, request.data.get('estado'),
                                  reason=request.data.get('motivo_cancelacion', ''),actor=request.user)

    return Response(AdminPedidoSerializer(pedido).data)


@api_view(['GET', 'PATCH'])
@permission_classes([IsAdminUser,VerifiedAdminWrites])
@transaction.atomic
def admin_users(request):
    if request.method == 'PATCH':
        from monolith.validation import integer
        user_id = integer(request.data.get('id'))
        list(Usuario.objects.select_for_update().filter(is_staff=True).order_by('pk'))
        try:
            usuario = Usuario.objects.select_for_update().get(pk=user_id)
        except Usuario.DoesNotExist:
            return Response({'detail': translate('Usuario no encontrado.')}, status=status.HTTP_404_NOT_FOUND)

        if _is_deleted_user(usuario):
            return Response(
                {'detail': translate('No puedes modificar una cuenta eliminada.')},
                status=status.HTTP_400_BAD_REQUEST,
            )

        if not request.user.is_superuser and (usuario.is_superuser or any(key in request.data for key in ('is_staff', 'is_superuser'))):
            return Response({'detail': translate('Solo un superusuario puede cambiar roles o modificar superusuarios.')}, status=403)
        es_mi_usuario = usuario.pk == request.user.pk
        intenta_desactivar = _payload_bool_false(request.data, 'is_active') or _payload_bool_false(request.data, 'cuenta_activa')
        intenta_quitar_admin = _payload_bool_false(request.data, 'is_staff') or _payload_bool_false(request.data, 'is_superuser')

        if es_mi_usuario and intenta_desactivar:
            return Response(
                {'detail': translate('No puedes desactivar tu propia cuenta de administrador.')},
                status=status.HTTP_400_BAD_REQUEST,
            )

        if es_mi_usuario and intenta_quitar_admin:
            return Response(
                {'detail': translate('No puedes quitarte tus propios permisos de administrador.')},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Solo bloquea si el usuario objetivo realmente es un admin activo
        # y la modificación lo dejaría sin capacidad de administrar.
        admin_activo_actual = bool(usuario.is_active and usuario.cuenta_activa and usuario.is_staff)

        nuevo_is_active = _payload_bool_value(request.data, 'is_active', usuario.is_active)
        nueva_cuenta_activa = _payload_bool_value(request.data, 'cuenta_activa', usuario.cuenta_activa)
        nuevo_is_staff = _payload_bool_value(request.data, 'is_staff', usuario.is_staff)
        nuevo_is_superuser = _payload_bool_value(request.data, 'is_superuser', usuario.is_superuser)

        seguira_siendo_admin_activo = bool(
            nuevo_is_active and nueva_cuenta_activa and (nuevo_is_staff or nuevo_is_superuser)
        )

        if admin_activo_actual and not seguira_siendo_admin_activo:
            if _active_admins_count(exclude_pk=usuario.pk) <= 0:
                return Response(
                    {'detail': translate('No puedes dejar el sistema sin administradores activos.')},
                    status=status.HTTP_400_BAD_REQUEST,
                )

        serializer = AdminUsuarioSerializer(usuario, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        usuario = serializer.save()

        return Response(AdminUsuarioSerializer(usuario).data)

    q = (request.query_params.get('q') or '').strip()
    qs = Usuario.objects.annotate(pedidos_count=Count('pedidos')).order_by('-fecha_registro')
    if q:
        qs = qs.filter(email__icontains=q) | qs.filter(nombre__icontains=q)
    return admin_page(qs.order_by('-fecha_registro','-pk'),AdminUsuarioSerializer,request)
