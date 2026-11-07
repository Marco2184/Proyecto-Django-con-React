from decimal import Decimal
from django.db import transaction
from django.utils import timezone
from django.shortcuts import get_object_or_404
from rest_framework import serializers
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAdminUser
from rest_framework.pagination import PageNumberPagination
from rest_framework.response import Response
from monolith.messages import message
from monolith.permissions import VerifiedEmail
from monolith.validation import StrictIntegerField
from .models import Promotion, CouponUse


def calculate_discount(code,user,subtotal,*,lock=False,strict=True):
    if not code:return Decimal('0.00'),None
    qs=Promotion.objects.select_for_update() if lock else Promotion.objects
    p=qs.filter(codigo=str(code).strip().upper()).first()
    now=timezone.now()
    error=None
    if not p:error=message('Cupón desconocido.', 'Unknown coupon.')
    elif not p.activo:error=message('El cupón está desactivado.', 'This coupon is disabled.')
    elif p.inicio and now<p.inicio:error=message('El cupón todavía no está disponible.', 'This coupon is not available yet.')
    elif p.vencimiento and now>=p.vencimiento:error=message('El cupón ha vencido.', 'This coupon has expired.')
    elif p.limite_total is not None and p.usos>=p.limite_total:error=message('El cupón agotó sus usos.', 'This coupon has reached its usage limit.')
    elif p.limite_usuario is not None and CouponUse.objects.filter(promocion=p,usuario=user).count()>=p.limite_usuario:error=message('Ya alcanzaste el límite de este cupón.', 'You have reached this coupon’s usage limit.')
    elif subtotal<p.minimo_compra:error=message('No se alcanzó el monto mínimo del cupón.', 'The coupon minimum order amount was not reached.')
    if error:
        if strict:raise serializers.ValidationError({'cupon':error})
        return Decimal('0.00'),p
    amount=subtotal*p.valor/Decimal('100') if p.tipo=='porcentaje' else p.valor
    if p.descuento_maximo is not None:amount=min(amount,p.descuento_maximo)
    return min(subtotal,amount).quantize(Decimal('.01')),p


class PromotionSerializer(serializers.ModelSerializer):
    estado=serializers.SerializerMethodField()
    limite_total=StrictIntegerField(min_value=1,required=False,allow_null=True)
    limite_usuario=StrictIntegerField(min_value=1,required=False,allow_null=True)
    def get_estado(self,p):
        now=timezone.now()
        if not p.activo:return 'desactivado'
        if p.vencimiento and now>=p.vencimiento:return 'vencido'
        if p.inicio and now<p.inicio:return 'programado'
        if p.limite_total is not None and p.usos>=p.limite_total:return 'agotado'
        return 'activo'
    def validate_codigo(self,value):
        import re
        value=value.strip().upper()
        if not re.fullmatch(r'[A-Z0-9_-]{3,30}',value):raise serializers.ValidationError(message('Usa entre 3 y 30 letras, números, guiones o guiones bajos.', 'Use 3–30 letters, numbers, hyphens or underscores.'))
        return value
    def validate(self,attrs):
        value=lambda k,default=None:attrs.get(k,getattr(self.instance,k,default))
        if value('valor',0)<=0 or (value('tipo')=='porcentaje' and value('valor',0)>100):raise serializers.ValidationError({'valor':message('Descuento fuera de rango.', 'Discount is out of range.')})
        if value('inicio') and value('vencimiento') and value('vencimiento')<=value('inicio'):raise serializers.ValidationError({'vencimiento':message('El vencimiento debe ser posterior al inicio.', 'Expiry must be later than the start date.')})
        if value('minimo_compra',0)<0 or (value('descuento_maximo') is not None and value('descuento_maximo')<0):raise serializers.ValidationError({'detail':message('Los importes no pueden ser negativos.', 'Amounts cannot be negative.')})
        return attrs
    class Meta:
        model=Promotion
        fields=['id','codigo','tipo','valor','activo','inicio','vencimiento','limite_total','limite_usuario','minimo_compra','descuento_maximo','usos','estado','actualizado_en']
        read_only_fields=['id','usos','actualizado_en']


@api_view(['GET','POST'])
@permission_classes([IsAdminUser])
def promotions(request):
    if request.method=='POST':
        VerifiedEmail().has_permission(request,None)
        s=PromotionSerializer(data=request.data);s.is_valid(raise_exception=True);s.save()
        return Response(s.data,status=201)
    pager=PageNumberPagination();rows=pager.paginate_queryset(Promotion.objects.all(),request)
    return pager.get_paginated_response(PromotionSerializer(rows,many=True).data)


@api_view(['PATCH'])
@permission_classes([IsAdminUser,VerifiedEmail])
@transaction.atomic
def promotion_detail(request,pk):
    p=get_object_or_404(Promotion.objects.select_for_update(),pk=pk)
    s=PromotionSerializer(p,data=request.data,partial=True);s.is_valid(raise_exception=True);s.save()
    return Response(s.data)
