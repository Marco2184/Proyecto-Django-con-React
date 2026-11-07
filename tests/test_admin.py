from decimal import Decimal
import uuid
from django.test import TestCase
from rest_framework.test import APIClient
from usuarios.models import Usuario,Pedido,PedidoItem
from productos.models import Producto,StockMovement


class AdminTests(TestCase):
    def setUp(self):
        self.user=Usuario.objects.create_superuser('admin@example.invalid','Admin','password')
        self.c=APIClient();self.c.force_authenticate(self.user)
        self.product=Producto.objects.create(nombre='Game',precio=100,stock=5)

    def test_dashboard_uses_paid_non_cancelled_real_orders(self):
        for state,paid,total in [('procesando','aprobado',100),('cancelado','aprobado',500),('pendiente','rechazado',300)]:
            order=Pedido.objects.create(usuario=self.user,monto_total=total,estado=state,estado_pago=paid)
            PedidoItem.objects.create(pedido=order,producto=self.product,producto_nombre='Game',cantidad=1,precio_unitario=100,subtotal=100)
        r=self.c.get('/api/admin/dashboard/')
        self.assertEqual(r.status_code,200,r.data)
        self.assertEqual(Decimal(r.data['comparacion']['actual']),100)
        self.assertEqual(r.data['top_productos'][0]['cantidad'],1)
        self.assertEqual(len(r.data['series']['daily']),1)
        self.assertEqual(self.c.get('/api/admin/dashboard/?desde=2030-02-01&hasta=2020-01-01').status_code,400)

    def test_adjustments_are_audited_idempotent_and_nonnegative(self):
        payload={'producto_id':self.product.pk,'cantidad':-2,'motivo':'Ajuste manual','request_id':str(uuid.uuid4())}
        self.assertEqual(self.c.post('/api/admin/inventory/',payload,format='json').status_code,201)
        self.assertEqual(self.c.post('/api/admin/inventory/',payload,format='json').status_code,200)
        self.product.refresh_from_db();self.assertEqual(self.product.stock,3)
        self.assertEqual(StockMovement.objects.count(),1)
        payload.update(cantidad=-20,request_id=str(uuid.uuid4()))
        self.assertEqual(self.c.post('/api/admin/inventory/',payload,format='json').status_code,400)
        self.assertEqual(StockMovement.objects.get().administrador,self.user)

    def test_empty_dashboard_and_paginated_products(self):
        r=self.c.get('/api/admin/dashboard/')
        self.assertEqual(r.data['series'],{'daily':[],'weekly':[],'monthly':[]})
        self.assertEqual(r.data['top_productos'],[])
        self.assertEqual(Decimal(r.data['comparacion']['actual']),0)
        r=self.c.get('/api/admin/products/');self.assertEqual(r.data['count'],1)
        path=f'/api/admin/products/{self.product.pk}/'
        self.assertEqual(self.c.patch(path,{'stock':4},format='json').status_code,400)
        self.assertEqual(self.c.patch(path,{'stock':4,'motivo_stock':'Reconteo'},format='json').status_code,200)
        self.assertEqual(StockMovement.objects.get().cantidad,-1)

    def test_promotion_creation_edit_and_activation(self):
        r=self.c.post('/api/admin/promotions/',{'codigo':'NEW_FIXED','tipo':'fijo','valor':'12.50','limite_total':2,'limite_usuario':1},format='json')
        self.assertEqual(r.status_code,201,r.data)
        path=f"/api/admin/promotions/{r.data['id']}/"
        self.assertEqual(self.c.patch(path,{'activo':False},format='json').data['estado'],'desactivado')
        r=self.c.patch(path,{'activo':True,'valor':'20.00'},format='json')
        self.assertEqual(r.data['estado'],'activo');self.assertEqual(r.data['valor'],'20.00')
        self.assertEqual(self.c.patch(path,{'tipo':'porcentaje','valor':'101'},format='json').status_code,400)

    def test_legacy_django_admin_and_import_commands_record_stock(self):
        from types import SimpleNamespace
        from django.test import RequestFactory
        from django.contrib.admin.sites import AdminSite
        from productos.admin import ProductoAdmin
        from productos.inventory import create_imported_product
        request=RequestFactory().post('/admin/');request.user=self.user
        self.product.stock=3
        ProductoAdmin(Producto,AdminSite()).save_model(request,self.product,SimpleNamespace(changed_data=['stock'],cleaned_data={'motivo_stock':'Reconteo físico'}),True)
        movement=StockMovement.objects.get()
        self.assertEqual(movement.cantidad,-2);self.assertEqual(movement.administrador,self.user)
        p=create_imported_product(nombre='Imported game',precio=100,stock=2)
        self.assertEqual(p.stock_movements.get().cantidad,2)
