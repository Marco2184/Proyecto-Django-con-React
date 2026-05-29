from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.http import JsonResponse
from django.views.decorators.http import require_POST
from django.db.models import Q
from collections import defaultdict
from productos.models import Producto, Plataforma, Categoria
from .models import Carrito, ItemCarrito


def _get_carrito(request):
    carrito, _ = Carrito.objects.get_or_create(usuario=request.user)
    return carrito


# ── Ver carrito ──────────────────────────────────────────────
@login_required
def ver_carrito(request):
    carrito = _get_carrito(request)
    items   = list(carrito.items)

    # H027.1 — Verificar stock al abrir el carrito + H027.2 ajuste automático
    ajustados = []
    for item in items:
        if item.cantidad > item.producto.stock:
            if item.producto.stock == 0:
                ajustados.append(f'{item.producto.nombre} se quedó sin stock y fue removido.')
                item.delete()
            else:
                item.cantidad = item.producto.stock
                item.save()
                ajustados.append(f'{item.producto.nombre} ajustado a {item.producto.stock} unidades por stock.')
    if ajustados:
        for msg in ajustados:
            messages.warning(request, msg)
        items = list(carrito.items)

    # H030 — Ordenamiento de ítems
    orden = request.GET.get('orden', '')
    if orden == 'precio_asc':
        items.sort(key=lambda i: i.producto.precio)
    elif orden == 'precio_desc':
        items.sort(key=lambda i: i.producto.precio, reverse=True)
    elif orden == 'popularidad':
        items.sort(key=lambda i: i.producto.ventas, reverse=True)

    # H024.1 — Agrupar por categoría
    agrupado = defaultdict(list)
    for item in items:
        cat = item.producto.categoria.nombre if item.producto.categoria else 'Sin categoría'
        agrupado[cat].append(item)

    # H024.2 — Filtro por tipo (categoría)
    tipo_sel = request.GET.get('tipo', '')
    if tipo_sel:
        items = [i for i in items
                 if i.producto.categoria and i.producto.categoria.slug == tipo_sel]

    # H023.2 — Detectar plataformas mezcladas
    plataformas_en_carrito = set()
    for item in carrito.items:
        for p in item.producto.plataformas.all():
            plataformas_en_carrito.add(p.nombre)
    plataformas_mezcladas = len(plataformas_en_carrito) > 1

    # H029 — Recomendados (misma categoría que los productos del carrito)
    cats_carrito = [i.producto.categoria_id for i in carrito.items if i.producto.categoria_id]
    ids_carrito  = [i.producto_id for i in carrito.items]
    recomendados = Producto.objects.filter(
        categoria_id__in=cats_carrito
    ).exclude(id__in=ids_carrito).order_by('-ventas')[:4]

    # H029.2 — Accesorios complementarios
    cat_accesorios = Categoria.objects.filter(nombre__iexact='Accesorios').first()
    accesorios = []
    if cat_accesorios:
        accesorios = Producto.objects.filter(
            categoria=cat_accesorios
        ).exclude(id__in=ids_carrito).order_by('-ventas')[:4]

    # H024.2 — categorías presentes para el filtro
    categorias_carrito = Categoria.objects.filter(
        productos__id__in=ids_carrito
    ).distinct()

    return render(request, 'carrito/carrito.html', {
        'carrito':              carrito,
        'items':                items,
        'agrupado':             dict(agrupado),
        'plataformas_mezcladas': plataformas_mezcladas,
        'plataformas_carrito':  plataformas_en_carrito,
        'recomendados':         recomendados,
        'accesorios':           accesorios,
        'categorias_carrito':   categorias_carrito,
        'tipo_sel':             tipo_sel,
        'orden':                orden,
    })


# ── H021/H022 — Agregar al carrito ──────────────────────────
@login_required
@require_POST
def agregar_item(request, producto_id):
    producto = get_object_or_404(Producto, id=producto_id)
    carrito  = _get_carrito(request)

    if producto.stock == 0:
        messages.error(request, f'{producto.nombre} no tiene stock disponible.')
        return redirect(request.META.get('HTTP_REFERER', 'catalogo'))

    item, creado = ItemCarrito.objects.get_or_create(
        carrito=carrito, producto=producto,
        defaults={'precio_agregado': producto.precio, 'cantidad': 1}
    )
    if not creado:
        if item.cantidad < producto.stock:
            item.cantidad += 1
            item.save()
            messages.success(request, f'Cantidad de {producto.nombre} actualizada.')
        else:
            messages.warning(request, f'No hay más stock de {producto.nombre}.')
    else:
        messages.success(request, f'{producto.nombre} agregado al carrito.')

    return redirect(request.META.get('HTTP_REFERER', 'catalogo'))


# ── Actualizar cantidad ──────────────────────────────────────
@login_required
@require_POST
def actualizar_cantidad(request, item_id):
    item = get_object_or_404(ItemCarrito, id=item_id, carrito__usuario=request.user)
    accion = request.POST.get('accion')

    if accion == 'mas':
        if item.cantidad < item.producto.stock:
            item.cantidad += 1
            item.save()
    elif accion == 'menos':
        if item.cantidad > 1:
            item.cantidad -= 1
            item.save()
        else:
            item.delete()
            messages.info(request, 'Producto removido del carrito.')
            return redirect('ver_carrito')
    item.save()
    return redirect('ver_carrito')


# ── Eliminar ítem ────────────────────────────────────────────
@login_required
@require_POST
def eliminar_item(request, item_id):
    item = get_object_or_404(ItemCarrito, id=item_id, carrito__usuario=request.user)
    nombre = item.producto.nombre
    item.delete()
    messages.info(request, f'{nombre} removido del carrito.')
    return redirect('ver_carrito')


# ── Vaciar carrito ───────────────────────────────────────────
@login_required
@require_POST
def vaciar_carrito(request):
    carrito = _get_carrito(request)
    carrito.itemcarrito_set.all().delete()
    messages.info(request, 'Carrito vaciado.')
    return redirect('ver_carrito')


# ── H022 — Buscar productos desde el carrito (AJAX) ─────────
@login_required
def buscar_en_carrito(request):
    q = request.GET.get('q', '').strip()
    # SOLO funciona con 3+ caracteres
    if len(q) < 3:
        return JsonResponse({'resultados': []})
    productos = Producto.objects.filter(
        Q(nombre__icontains=q) | Q(categoria__nombre__icontains=q)
    )[:6]
    return JsonResponse({'resultados': [{
        'id':     p.id,
        'nombre': p.nombre,
        'precio': str(p.precio),
        'imagen': p.imagen,
        'stock':  p.stock,
    } for p in productos]})
