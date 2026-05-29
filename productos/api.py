import re
import unicodedata
from rest_framework import viewsets, filters
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.pagination import PageNumberPagination
from django.db.models import Q, Case, When, IntegerField
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
    qs = qs.exclude(_adult_query()).distinct()
    ids = [obj.id for obj in qs.select_related('categoria') if not is_adult_product(obj)]
    return qs.filter(id__in=ids)


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


class ProductoViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = Producto.objects.select_related('categoria').prefetch_related('plataformas', 'galeria', 'itemcarrito_set')
    pagination_class = ProductoPagination
    filter_backends = [filters.OrderingFilter]
    ordering_fields = ['precio', 'ventas', 'activo', 'valoracion', 'nombre']
    ordering = ['-ventas']

    def get_serializer_class(self):
        return ProductoDetailSerializer if self.action == 'retrieve' else ProductoListSerializer

    def get_queryset(self):
        qs = exclude_adult_content(self.queryset.filter(stock__gt=0))

        plataforma = self.request.query_params.getlist('plataforma')
        if plataforma:
            qs = qs.filter(plataformas__slug__in=plataforma).distinct()

        categoria = self.request.query_params.get('categoria')
        if categoria:
            cat_obj = Categoria.objects.filter(slug=categoria).first()
            if cat_obj:
                subcats = list(cat_obj.subcategorias.values_list('id', flat=True))
                ids = [cat_obj.id] + subcats
                qs = qs.filter(categoria__id__in=ids)

        q = (self.request.query_params.get('search') or self.request.query_params.get('q') or '').strip()
        if len(q) >= 2:
            terms = [t for t in q.split() if len(t) >= 2] or [q]
            for raw_term in terms:
                term = _normalize(raw_term)
                if len(term) <= 2:
                    matches = [obj.id for obj in qs if _matches_short_search(obj, term)]
                    preserved = Case(*[When(pk=pk, then=pos) for pos, pk in enumerate(matches)], output_field=IntegerField())
                    qs = qs.filter(id__in=matches).order_by(preserved) if matches else qs.none()
                else:
                    qs = qs.filter(
                        Q(nombre__icontains=raw_term) |
                        Q(descripcion__icontains=raw_term) |
                        Q(categoria__nombre__icontains=raw_term) |
                        Q(plataformas__nombre__icontains=raw_term)
                    ).distinct()

        precio_min = self.request.query_params.get('precio_min')
        precio_max = self.request.query_params.get('precio_max')
        if precio_min:
            qs = qs.filter(precio__gte=float(precio_min))
        if precio_max:
            qs = qs.filter(precio__lte=float(precio_max))
        return qs

    @action(detail=False, methods=['get'])
    def buscar(self, request):
        q = request.query_params.get('q', '').strip()
        if len(q) < 2:
            return Response({'resultados': []})
        productos = self.get_queryset()[:8]
        serializer = ProductoListSerializer(productos, many=True, context={'request': request})
        return Response({'resultados': serializer.data})


class PlataformaViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = Plataforma.objects.all()
    serializer_class = PlataformaSerializer


class CategoriaViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = Categoria.objects.filter(padre__isnull=True).prefetch_related('subcategorias')
    serializer_class = CategoriaSerializer
