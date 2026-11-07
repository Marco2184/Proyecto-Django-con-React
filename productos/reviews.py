from django.db import transaction
from django.db.models import Avg, Count
from django.shortcuts import get_object_or_404
from rest_framework import serializers
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny, IsAuthenticated, IsAdminUser
from rest_framework.pagination import PageNumberPagination
from rest_framework.response import Response
from rest_framework.exceptions import PermissionDenied
from monolith.messages import message
from monolith.permissions import VerifiedEmail
from monolith.validation import StrictIntegerField
from usuarios.models import PedidoItem, Usuario
from .models import Producto, Review
from .api import exclude_adult_content


class ReviewSerializer(serializers.ModelSerializer):
    producto_nombre=serializers.CharField(source='producto.nombre',read_only=True)
    usuario_nombre=serializers.CharField(source='usuario.nombre',read_only=True)
    compra_verificada=serializers.SerializerMethodField()
    puntuacion=StrictIntegerField(min_value=1,max_value=5)
    comentario=serializers.CharField(min_length=3,max_length=2000)
    def get_compra_verificada(self,obj):
        return bool(obj.compra_id and obj.compra.pedido.estado_pago=='aprobado' and obj.compra.pedido.estado!='cancelado')
    class Meta:
        model=Review
        fields=['id','producto','producto_nombre','usuario_nombre','puntuacion','comentario','compra_verificada','creado_en','actualizado_en','visible','motivo_moderacion']
        read_only_fields=['id','producto','visible','motivo_moderacion']


def valid_purchase(user,product):
    if not user.is_authenticated: return None
    return PedidoItem.objects.filter(pedido__usuario=user,producto=product,pedido__estado_pago='aprobado').exclude(pedido__estado='cancelado').order_by('pk').first()


def review_query():
    return Review.objects.select_related('usuario','producto','compra__pedido')


@api_view(['GET','POST'])
@permission_classes([AllowAny])
def reviews(request,pk):
    product=get_object_or_404(exclude_adult_content(Producto.objects.all()),pk=pk)
    if request.method=='POST':
        if not request.user.is_authenticated: raise PermissionDenied(message('Inicia sesión para publicar.', 'Sign in to publish a review.'))
        VerifiedEmail().has_permission(request,None)
        with transaction.atomic():
            Usuario.objects.select_for_update().get(pk=request.user.pk)
            purchase=valid_purchase(request.user,product)
            if not purchase: raise PermissionDenied(message('Necesitas una compra válida de este videojuego.', 'You need a valid purchase of this game.'))
            if Review.objects.filter(usuario=request.user,producto=product).exists():
                raise serializers.ValidationError({'detail':message('Ya tienes una reseña. Puedes editarla.', 'You already have a review. You can edit it.')})
            s=ReviewSerializer(data=request.data);s.is_valid(raise_exception=True)
            review=s.save(usuario=request.user,producto=product,compra=purchase)
            return Response(ReviewSerializer(review).data,status=201)
    qs=review_query().filter(producto=product,visible=True)
    # Cancelled/refunded purchases do not contribute to verified averages.
    verified=qs.filter(compra__pedido__estado_pago='aprobado').exclude(compra__pedido__estado='cancelado')
    summary=verified.aggregate(promedio=Avg('puntuacion'),cantidad=Count('pk'))
    qs=qs.order_by('-puntuacion','-creado_en','-pk') if request.query_params.get('orden')=='mejor' else qs.order_by('-creado_en','-pk')
    pager=PageNumberPagination();rows=pager.paginate_queryset(qs,request)
    result=pager.get_paginated_response(ReviewSerializer(rows,many=True).data)
    mine=review_query().filter(usuario=request.user,producto=product).first() if request.user.is_authenticated else None
    result.data.update(summary=summary,valoracion_externa=str(product.valoracion),can_review=bool(valid_purchase(request.user,product)),mine=ReviewSerializer(mine).data if mine else None)
    return result


@api_view(['PATCH','DELETE'])
@permission_classes([IsAuthenticated])
@transaction.atomic
def own_review(request,pk):
    review=get_object_or_404(review_query().select_for_update(of=('self',)),usuario=request.user,producto_id=pk)
    if request.method=='DELETE':review.delete();return Response(status=204)
    VerifiedEmail().has_permission(request,None)
    if not valid_purchase(request.user,review.producto):raise PermissionDenied(message('La compra ya no es válida.', 'The purchase is no longer valid.'))
    s=ReviewSerializer(review,data=request.data,partial=True);s.is_valid(raise_exception=True);s.save()
    return Response(s.data)


@api_view(['GET','PATCH'])
@permission_classes([IsAdminUser])
def moderate_reviews(request):
    if request.method=='PATCH':
        VerifiedEmail().has_permission(request,None)
        pk=StrictIntegerField(min_value=1).run_validation(request.data.get('id'))
        visible=serializers.BooleanField().run_validation(request.data.get('visible'))
        reason=serializers.CharField(min_length=3,max_length=250).run_validation(request.data.get('motivo'))
        r=get_object_or_404(review_query(),pk=pk)
        r.visible=visible;r.motivo_moderacion=reason;r.moderador=request.user;r.save(update_fields=['visible','motivo_moderacion','moderador','actualizado_en'])
        return Response(ReviewSerializer(r).data)
    pager=PageNumberPagination();rows=pager.paginate_queryset(review_query(),request)
    return pager.get_paginated_response(ReviewSerializer(rows,many=True).data)
