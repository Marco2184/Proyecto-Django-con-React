from django.db import models, transaction
from django.conf import settings
from rest_framework import serializers
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.pagination import PageNumberPagination
from django.shortcuts import get_object_or_404
from productos.models import Producto
from productos.serializers import ProductoListSerializer
from productos.api import exclude_adult_content


from .models import WishlistItem, PriceNotification


class WishSerializer(serializers.ModelSerializer):
    producto = ProductoListSerializer(read_only=True)
    class Meta:
        model = WishlistItem
        fields = ['id','producto','precio_guardado','creado_en']


def payload(request):
    items = request.user.wishlist.select_related('producto','producto__categoria').prefetch_related('producto__plataformas')
    pager=PageNumberPagination()
    rows=pager.paginate_queryset(items,request)
    notices = PriceNotification.objects.filter(item__usuario=request.user,leida=False).select_related('item__producto')[:50]
    return {'items':WishSerializer(rows,many=True,context={'request':request,'cart_quantities':{}}).data,
            'saved_ids':list(request.user.wishlist.values_list('producto_id',flat=True)),
            'count':pager.page.paginator.count,'next':pager.get_next_link(),'previous':pager.get_previous_link(),
            'notifications':[{'id':n.pk,'producto_id':n.item.producto_id,'nombre':n.item.producto.nombre,'precio_anterior':str(n.precio_anterior),'precio_actual':str(n.precio_actual),'creado_en':n.creado_en} for n in notices]}


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def wishlist(request):
    return Response(payload(request))


@api_view(['PUT','DELETE'])
@permission_classes([IsAuthenticated])
def wishlist_product(request,pk):
    if request.method=='DELETE':
        request.user.wishlist.filter(producto_id=pk).delete()
        return Response(status=204)
    product=get_object_or_404(exclude_adult_content(Producto.objects.all()),pk=pk)
    item,created=WishlistItem.objects.get_or_create(usuario=request.user,producto=product,defaults={'precio_guardado':product.precio})
    return Response(WishSerializer(item,context={'request':request,'cart_quantities':{}}).data,status=201 if created else 200)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
@transaction.atomic
def wishlist_sync(request):
    # A deliberate sync discovers imports/bulk price changes too, with no email.
    items=list(request.user.wishlist.select_for_update(of=('self',)).select_related('producto'))
    for item in items:
        if item.producto.precio < item.precio_guardado:
            PriceNotification.objects.get_or_create(item=item,precio_actual=item.producto.precio,defaults={'precio_anterior':item.precio_guardado})
    return Response(payload(request))


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def notification_read(request,pk):
    notice=get_object_or_404(PriceNotification,pk=pk,item__usuario=request.user)
    notice.leida=True;notice.save(update_fields=['leida'])
    return Response({'ok':True})
