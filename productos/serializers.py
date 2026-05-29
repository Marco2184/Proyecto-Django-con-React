from rest_framework import serializers
from .models import Producto, Plataforma, Categoria, ImagenProducto


class PlataformaSerializer(serializers.ModelSerializer):
    class Meta:
        model = Plataforma
        fields = ['id', 'nombre', 'slug']


class ImagenProductoSerializer(serializers.ModelSerializer):
    class Meta:
        model = ImagenProducto
        fields = ['id', 'url', 'imagen', 'orden']


class CategoriaSerializer(serializers.ModelSerializer):
    subcategorias = serializers.SerializerMethodField()

    class Meta:
        model = Categoria
        fields = ['id', 'nombre', 'slug', 'subcategorias']

    def get_subcategorias(self, obj):
        return CategoriaMiniSerializer(obj.subcategorias.all(), many=True).data


class CategoriaMiniSerializer(serializers.ModelSerializer):
    class Meta:
        model = Categoria
        fields = ['id', 'nombre', 'slug']


class ProductoListSerializer(serializers.ModelSerializer):
    plataformas = PlataformaSerializer(many=True, read_only=True)
    categoria = CategoriaMiniSerializer(read_only=True)
    disponible = serializers.SerializerMethodField()
    tiene_descuento = serializers.SerializerMethodField()
    porcentaje_descuento = serializers.SerializerMethodField()
    cantidad_en_carrito = serializers.SerializerMethodField()

    class Meta:
        model = Producto
        fields = [
            'id', 'nombre', 'slug', 'precio', 'precio_original',
            'stock', 'imagen_principal', 'imagen_url', 'categoria',
            'plataformas', 'valoracion', 'ventas', 'especificaciones',
            'disponible', 'tiene_descuento', 'porcentaje_descuento',
            'cantidad_en_carrito',
        ]

    def get_disponible(self, obj):
        return obj.disponible

    def get_tiene_descuento(self, obj):
        return obj.tiene_descuento

    def get_porcentaje_descuento(self, obj):
        return obj.porcentaje_descuento

    def get_cantidad_en_carrito(self, obj):
        request = self.context.get('request')
        user = getattr(request, 'user', None)
        if not user or not user.is_authenticated:
            return 0
        item = obj.itemcarrito_set.filter(carrito__usuario=user).first()
        return item.cantidad if item else 0


class ProductoDetailSerializer(ProductoListSerializer):
    galeria = ImagenProductoSerializer(many=True, read_only=True)
    productos_similares = serializers.SerializerMethodField()
    comprados_juntos = serializers.SerializerMethodField()

    class Meta:
        model = Producto
        fields = ProductoListSerializer.Meta.fields + [
            'descripcion', 'galeria', 'productos_similares', 'comprados_juntos'
        ]

    def _base_related_queryset(self, obj):
        qs = Producto.objects.filter(stock__gt=0).exclude(pk=obj.pk).select_related('categoria').prefetch_related('plataformas')
        adult_terms = ['erotic', 'erótico', 'erotico', 'sex', 'sexual', 'hentai', 'nsfw', 'porn', 'adult', 'nudity', 'nude', 'desnudo', '18+', '+18']
        for term in adult_terms:
            qs = qs.exclude(nombre__icontains=term).exclude(descripcion__icontains=term)
        return qs

    def get_productos_similares(self, obj):
        qs = self._base_related_queryset(obj)
        if obj.categoria_id:
            qs = qs.filter(categoria_id=obj.categoria_id)
        else:
            qs = qs.filter(plataformas__in=obj.plataformas.all()).distinct()
        qs = qs.order_by('-valoracion', '-ventas')[:4]
        return ProductoListSerializer(qs, many=True, context=self.context).data

    def get_comprados_juntos(self, obj):
        qs = self._base_related_queryset(obj)
        platform_ids = obj.plataformas.values_list('id', flat=True)
        qs = qs.filter(plataformas__id__in=platform_ids).exclude(categoria_id=obj.categoria_id).distinct().order_by('-ventas')[:4]
        return ProductoListSerializer(qs, many=True, context=self.context).data
