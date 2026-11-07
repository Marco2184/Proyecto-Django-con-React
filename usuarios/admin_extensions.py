from datetime import datetime, time, timedelta
from decimal import Decimal
from django.db import transaction
from django.db.models import Count, Sum
from django.db.models.functions import TruncDay, TruncWeek, TruncMonth
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
from productos.models import Producto, StockMovement
from productos.inventory import record_stock
from .models import Pedido, PedidoItem, Usuario


def analytics(request):
    today=timezone.localdate()
    start=serializers.DateField().run_validation(request.query_params.get('desde',(today-timedelta(days=29)).isoformat()))
    end=serializers.DateField().run_validation(request.query_params.get('hasta',today.isoformat()))
    if end<start or (end-start).days>366:
        raise serializers.ValidationError({'detail':message('Selecciona un rango de hasta 366 días.', 'Select a date range of up to 366 days.')})
    tz=timezone.get_current_timezone()
    lower=timezone.make_aware(datetime.combine(start,time.min),tz)
    upper=timezone.make_aware(datetime.combine(end+timedelta(days=1),time.min),tz)
    length=upper-lower
    valid=Pedido.objects.filter(estado_pago='aprobado').exclude(estado='cancelado')
    current=valid.filter(fecha__gte=lower,fecha__lt=upper)
    previous=valid.filter(fecha__gte=lower-length,fecha__lt=lower)
    total=current.aggregate(total=Sum('monto_total'))['total'] or Decimal('0.00')
    last=previous.aggregate(total=Sum('monto_total'))['total'] or Decimal('0.00')
    series={}
    for key,trunc in [('daily',TruncDay),('weekly',TruncWeek),('monthly',TruncMonth)]:
        groups=current.annotate(period=trunc('fecha',tzinfo=tz)).values('period').annotate(ingresos=Sum('monto_total'),pedidos=Count('pk')).order_by('period')
        series[key]=[{'fecha':r['period'].date().isoformat(),'ingresos':str(r['ingresos']),'pedidos':r['pedidos']} for r in groups]
    top=PedidoItem.objects.filter(pedido__in=current,producto__isnull=False).values('producto_id','producto__nombre').annotate(cantidad=Sum('cantidad')).order_by('-cantidad','producto_id')[:10]
    return {'desde':start,'hasta':end,'series':series,'comparacion':{'actual':str(total),'anterior':str(last),'diferencia':str(total-last),'porcentaje':str(((total-last)/last*100).quantize(Decimal('.01'))) if last else None},
        'estados_periodo':dict(Pedido.objects.filter(fecha__gte=lower,fecha__lt=upper).values_list('estado').annotate(n=Count('pk'))),
        'top_productos':list(top),'clientes_total':Usuario.objects.filter(is_staff=False).exclude(email__endswith='@monolith.void').count(),
        'agotados_total':Producto.objects.filter(stock=0).count()}


class MovementSerializer(serializers.ModelSerializer):
    class Meta:
        model=StockMovement
        fields=['id','producto','producto_nombre','administrador','administrador_nombre','pedido','tipo','cantidad','stock_anterior','stock_posterior','motivo','creado_en']


class AdjustmentSerializer(serializers.Serializer):
    producto_id=StrictIntegerField(min_value=1)
    cantidad=StrictIntegerField(min_value=-2147483647,max_value=2147483647)
    motivo=serializers.CharField(max_length=250,min_length=3)
    request_id=serializers.UUIDField()


@api_view(['GET','POST'])
@permission_classes([IsAdminUser])
@transaction.atomic
def inventory(request):
    if request.method=='POST':
        VerifiedEmail().has_permission(request,None)
        s=AdjustmentSerializer(data=request.data);s.is_valid(raise_exception=True);d=s.validated_data
        # Product lock serializes adjustments, checkout and cancellation.
        p=get_object_or_404(Producto.objects.select_for_update(),pk=d['producto_id'])
        previous=StockMovement.objects.filter(request_id=d['request_id']).first()
        if previous:
            if previous.administrador_id!=request.user.pk or previous.producto_id!=p.pk or previous.cantidad!=d['cantidad'] or previous.motivo!=d['motivo']:
                raise serializers.ValidationError({'detail':message('Identificador ya utilizado.', 'Identifier already used.')})
            return Response(MovementSerializer(previous).data)
        before=p.stock
        if not d['cantidad'] or not 0<=before+d['cantidad']<=2147483647:
            raise serializers.ValidationError({'cantidad':message('El ajuste debe cambiar el stock sin dejarlo negativo.', 'The adjustment must change stock without making it negative.')})
        p.stock+=d['cantidad'];p.save(update_fields=['stock','actualizado'])
        movement=record_stock(p,before,'ajuste',d['motivo'],request.user)
        movement.request_id=d['request_id'];movement.save(update_fields=['request_id'])
        return Response(MovementSerializer(movement).data,status=201)
    qs=StockMovement.objects.all()
    if request.query_params.get('producto_id'):
        qs=qs.filter(producto_id=StrictIntegerField(min_value=1).run_validation(request.query_params['producto_id']))
    pager=PageNumberPagination();rows=pager.paginate_queryset(qs,request)
    return pager.get_paginated_response(MovementSerializer(rows,many=True).data)
