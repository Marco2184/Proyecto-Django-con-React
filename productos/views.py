from django.shortcuts import render, get_object_or_404
from django.core.paginator import Paginator
from django.db.models import Q
from django.http import JsonResponse
from .models import Producto, Categoria, Plataforma, ImagenProducto


# ── H011.1 + H016 + H017 + H018 + H020 — Catálogo ───────────
def catalogo(request):
    productos = Producto.objects.prefetch_related('plataformas', 'categoria')

    # H012.1 / H012.2 — Búsqueda
    # El filtro SOLO se aplica con 2 o más caracteres.
    # Con menos de 2 se ignora por completo y se muestra todo el catálogo.
    q = request.GET.get('q', '').strip()
    if len(q) >= 2:
        productos = productos.filter(
            Q(nombre__icontains=q) |
            Q(descripcion__icontains=q) |
            Q(categoria__nombre__icontains=q)
        )

    # H013.1 / H013.2 — Filtro por plataforma (múltiple)
    plataformas_sel = request.GET.getlist('plataforma')
    if plataformas_sel:
        productos = productos.filter(plataformas__slug__in=plataformas_sel).distinct()

    # H014.1 / H014.2 — Filtro por categoría
    categoria_sel = request.GET.get('categoria', '')
    if categoria_sel:
        cat = Categoria.objects.filter(slug=categoria_sel).first()
        if cat:
            # incluir subcategorías
            subcats = list(cat.subcategorias.values_list('id', flat=True))
            ids = [cat.id] + subcats
            productos = productos.filter(categoria__id__in=ids)

    # H020.1 / H020.2 — Ordenamiento
    orden = request.GET.get('orden', '')
    if orden == 'precio_asc':
        productos = productos.order_by('precio')
    elif orden == 'precio_desc':
        productos = productos.order_by('-precio')
    elif orden == 'popularidad':
        productos = productos.order_by('-ventas')
    elif orden == 'recientes':
        productos = productos.order_by('-activo')
    else:
        productos = productos.order_by('-ventas')

    # H011.1 — Paginación 20 por página
    paginator = Paginator(productos, 20)
    page      = request.GET.get('page', 1)
    productos_page = paginator.get_page(page)

    # Sidebar data
    todas_plataformas = Plataforma.objects.all()
    categorias_raiz   = Categoria.objects.filter(padre__isnull=True).prefetch_related('subcategorias')

    return render(request, 'productos/catalogo.html', {
        'productos':         productos_page,
        'todas_plataformas': todas_plataformas,
        'categorias_raiz':   categorias_raiz,
        'plataformas_sel':   plataformas_sel,
        'categoria_sel':     categoria_sel,
        'orden':             orden,
        'q':                 q,
        'total':             paginator.count,
    })


# ── H012.1 — Sugerencias en tiempo real (AJAX) ───────────────
def buscar_sugerencias(request):
    q = request.GET.get('q', '').strip()
    if len(q) < 2:
        return JsonResponse({'resultados': []})
    productos = Producto.objects.filter(
        Q(nombre__icontains=q) | Q(categoria__nombre__icontains=q)
    )[:6]
    resultados = [{
        'id':     p.id,
        'nombre': p.nombre,
        'precio': str(p.precio),
        'imagen': p.imagen,
        'slug':   p.slug,
    } for p in productos]
    return JsonResponse({'resultados': resultados})


# ── H015.1 + H015.2 + H018.2 + H019 — Detalle ───────────────
def detalle_producto(request, slug):
    producto  = get_object_or_404(Producto, slug=slug)
    galeria   = producto.galeria.all()

    # H019.1 — Productos similares (misma categoría y plataforma)
    similares = Producto.objects.filter(
        categoria=producto.categoria
    ).exclude(id=producto.id)[:4]

    # H019.2 — Frecuentemente comprados juntos (misma plataforma, más vendidos)
    plataforma_ids = producto.plataformas.values_list('id', flat=True)
    juntos = Producto.objects.filter(
        plataformas__id__in=plataforma_ids
    ).exclude(id=producto.id).order_by('-ventas').distinct()[:4]

    # H015.2 — Especificaciones
    specs = producto.especificaciones or {}

    return render(request, 'productos/detalle.html', {
        'producto':  producto,
        'galeria':   galeria,
        'similares': similares,
        'juntos':    juntos,
        'specs':     specs,
    })
