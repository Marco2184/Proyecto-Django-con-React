from django.utils.translation import gettext as translate
import re
import unicodedata
from django.db.models import TextField
from django.db.models.functions import Cast, Lower, Replace
from rest_framework import viewsets, filters
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.pagination import PageNumberPagination
from django.db.models import Q, Case, When, IntegerField, Value
from decimal import Decimal
from rest_framework import serializers
from .models import Producto, Plataforma, Categoria
from .serializers import (
    ProductoListSerializer, ProductoDetailSerializer,
    PlataformaSerializer, CategoriaSerializer
)

# Filtro conservador para que Monolith no muestre ni importe juegos eróticos/adultos.
ADULT_BLOCKLIST = [
    'erotic', 'erótico', 'erotico', 'sex', 'sexual', 'sexual-content', 'hentai', 'nsfw',
    'porn', 'porno', 'pornographic', 'adult only', 'adult-only', 'adults only',
    'ao rated', 'mature sexual', 'explicit', 'nudity', 'nude', 'naked', 'desnudo',
    'strip', 'stripper', 'seduce', 'seduction', 'succubus', 'brothel', 'waifu',
    'dating sim', 'visual novel adult', '18+', '+18', 'r18', 'uncensored',
]


def _normalize(text):
    text = str(text or '').lower()
    return ''.join(c for c in unicodedata.normalize('NFD', text) if unicodedata.category(c) != 'Mn')


def _tokens(text):
    return re.findall(r'[a-z0-9]+', _normalize(text))


def _adult_query():
    query = Q()
    for term in ADULT_BLOCKLIST:
        query |= Q(nombre__icontains=term) | Q(descripcion__icontains=term) | Q(categoria__nombre__icontains=term)
    return query


def is_adult_product(producto):
    parts = [producto.nombre, producto.descripcion, getattr(producto.categoria, 'nombre', '')]
    try:
        parts += [str(v) for v in (producto.especificaciones or {}).values()]
    except Exception:
        pass
    text = _normalize(' '.join(parts))
    return any(_normalize(term) in text for term in ADULT_BLOCKLIST)


def exclude_adult_content(qs):
    qs = qs.annotate(
        especificaciones_texto=Cast(
            'especificaciones',
            output_field=TextField()
        )
    )

    condiciones = _adult_query()

    for term in ADULT_BLOCKLIST:
        condiciones |= Q(especificaciones_texto__icontains=term)

    return qs.exclude(condiciones).distinct()


def _matches_short_search(producto, term):
    """Para búsquedas de 2 letras, evita resultados basura: solo coincide inicio de palabra."""
    term = _normalize(term)
    fields = [producto.nombre, getattr(producto.categoria, 'nombre', '')]
    fields += [p.nombre for p in producto.plataformas.all()]
    return any(tok.startswith(term) for field in fields for tok in _tokens(field))


class ProductoPagination(PageNumberPagination):
    page_size = 20
    page_size_query_param = 'page_size'
    max_page_size = 100


class StableOrderingFilter(filters.OrderingFilter):
    def get_ordering(self, request, queryset, view):
        if getattr(view, '_has_search', False) and not request.query_params.get('ordering'):
            return ['_relevance', '-ventas', 'pk']
        return list(super().get_ordering(request, queryset, view) or ['-ventas']) + ['pk']


class ProductoViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = (
    Producto.objects
    .select_related('categoria')
    .prefetch_related('plataformas')
)   

    pagination_class = ProductoPagination
    filter_backends = [StableOrderingFilter]
    ordering_fields = ['precio', 'ventas', 'activo', 'valoracion', 'nombre']
    ordering = ['-ventas']
    
    def get_object(self):
        return super().get_object()

    def get_serializer_class(self):
        return ProductoDetailSerializer if self.action == 'retrieve' else ProductoListSerializer

    def get_queryset(self):
        qs = self.queryset if self.action == 'retrieve' else self.queryset.filter(stock__gt=0)

        if self.action == 'retrieve':
            qs = qs.prefetch_related('galeria')

        qs = exclude_adult_content(qs)

        plataforma = self.request.query_params.getlist('plataforma')
        if plataforma:
            qs = qs.filter(plataformas__slug__in=plataforma).distinct()

        categoria = self.request.query_params.get('categoria')
        if categoria:
            qs = qs.filter(Q(categoria__slug=categoria) | Q(categoria__padre__slug=categoria))

        q = (self.request.query_params.get('search') or self.request.query_params.get('q') or '').strip()[:150]
        self._has_search = len(q) >= 2
        if self._has_search:
            name = Lower('nombre')
            for accented, plain in zip('áéíóúüñÁÉÍÓÚÜÑ', 'aeiouunAEIOUUN'):
                name = Replace(name, Value(accented), Value(plain.lower()))
            qs = qs.annotate(_search_name=name)
            terms = [_normalize(term) for term in q.split() if len(term) >= 2] or [_normalize(q)]
            for term in terms:
                if len(term) == 2:
                    qs = qs.filter(Q(_search_name__istartswith=term) | Q(_search_name__icontains=' ' + term) |
                                   Q(categoria__nombre__istartswith=term) | Q(plataformas__nombre__istartswith=term)).distinct()
                else:
                    qs = qs.filter(Q(_search_name__icontains=term) | Q(descripcion__icontains=term) |
                                   Q(categoria__nombre__icontains=term) | Q(plataformas__nombre__icontains=term) |
                                   Q(especificaciones_texto__icontains=term)).distinct()
            normalized = _normalize(q)
            qs = qs.annotate(_relevance=Case(When(_search_name=normalized, then=0),
                                            When(_search_name__startswith=normalized, then=1), default=2, output_field=IntegerField()))

        bounds = {}
        for name in ('precio_min', 'precio_max'):
            value = self.request.query_params.get(name)
            if value not in (None, ''):
                bounds[name] = serializers.DecimalField(max_digits=10, decimal_places=2, min_value=Decimal('0')).run_validation(value)
        if len(bounds) == 2 and bounds['precio_min'] > bounds['precio_max']:
            raise serializers.ValidationError({'precio_max': translate('El precio máximo debe ser mayor o igual al mínimo.')})
        if 'precio_min' in bounds:
            qs = qs.filter(precio__gte=bounds['precio_min'])
        if 'precio_max' in bounds:
            qs = qs.filter(precio__lte=bounds['precio_max'])
        return qs

    def get_serializer_context(self):
        context = super().get_serializer_context()
        if self.request.user.is_authenticated:
            from carrito.models import ItemCarrito
            context['cart_quantities'] = dict(ItemCarrito.objects.filter(carrito__usuario=self.request.user).values_list('producto_id', 'cantidad'))
        return context

    @action(detail=False, methods=['get'])
    def buscar(self, request):
        q = request.query_params.get('q', '').strip()
        if len(q) < 2:
            return Response({'resultados': []})
        productos = self.filter_queryset(self.get_queryset())[:8]
        serializer = ProductoListSerializer(productos, many=True, context=self.get_serializer_context())
        return Response({'resultados': serializer.data})


class PlataformaViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = Plataforma.objects.all()
    serializer_class = PlataformaSerializer


class CategoriaViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = Categoria.objects.filter(padre__isnull=True).prefetch_related('subcategorias')
    serializer_class = CategoriaSerializer
