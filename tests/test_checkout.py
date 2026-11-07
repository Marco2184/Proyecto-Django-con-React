import uuid
from decimal import Decimal
from datetime import timedelta
from django.utils import timezone
from django.test import TestCase
from rest_framework.test import APIClient
from usuarios.models import Usuario,Pedido
from productos.models import Producto,StockMovement
from carrito.models import Promotion,CouponUse


class CheckoutTests(TestCase):
    def setUp(self):
        self.u=Usuario.objects.create_user('buyer@example.invalid','Buyer','password',email_verificado=True)
        self.c=APIClient();self.c.force_authenticate(self.u)
        self.p=Producto.objects.create(nombre='Game',precio=100,stock=2)
        self.payload={'direccion':{'calle':'Calle 123','ciudad':'Lima','departamento':'Lima','codigo_postal':'15001'},'metodo_pago':'tarjeta','pago':{'numero_tarjeta':'4111111111111111','cvv':'123'},'monto_total':'0.01'}
    def add(self):
        self.assertEqual(self.c.post('/api/cart/add/',{'producto_id':self.p.pk,'cantidad':1},format='json').status_code,200)
    def checkout(self,key):
        return self.c.post('/api/cart/checkout/',self.payload,format='json',HTTP_IDEMPOTENCY_KEY=key)
    def test_discount_idempotency_stock_cancellation_and_totals(self):
        self.add();self.assertEqual(self.c.post('/api/cart/aplicar-cupon/',{'codigo':'MONOLITH10'},format='json').status_code,200)
        key=str(uuid.uuid4());a=self.checkout(key);self.assertEqual(a.status_code,201,a.data)
        self.assertEqual(Decimal(a.data['pedido']['monto_total']),90)
        self.assertEqual(self.checkout(key).data,a.data)
        self.assertEqual(Pedido.objects.count(),1);self.assertEqual(CouponUse.objects.count(),1)
        self.p.refresh_from_db();self.assertEqual(self.p.stock,1)
        self.assertEqual(StockMovement.objects.filter(tipo='venta').count(),1)
        receipt=self.c.get(f"/api/profile/orders/{a.data['pedido']['id']}/receipt/")
        self.assertEqual(receipt.status_code,200);self.assertTrue(receipt.content.startswith(b'%PDF'))
        path=f"/api/profile/orders/{a.data['pedido']['id']}/cancel/"
        self.assertEqual(self.c.post(path,{},format='json').status_code,200)
        self.assertEqual(self.c.post(path,{},format='json').status_code,200)
        self.p.refresh_from_db();self.assertEqual(self.p.stock,2)
        self.assertEqual(StockMovement.objects.filter(tipo='cancelacion').count(),1)
    def test_coupon_limits_expiry_minimum_and_disabled_legacy(self):
        self.add();p=Promotion.objects.get(codigo='MONOLITH10');p.activo=False;p.save()
        self.assertEqual(self.c.post('/api/cart/aplicar-cupon/',{'codigo':p.codigo},format='json').status_code,400)
        p.activo=True;p.vencimiento=timezone.now()-timedelta(seconds=1);p.save()
        self.assertEqual(self.c.post('/api/cart/aplicar-cupon/',{'codigo':p.codigo},format='json').status_code,400)
        p.vencimiento=None;p.minimo_compra=200;p.save()
        self.assertEqual(self.c.post('/api/cart/aplicar-cupon/',{'codigo':p.codigo},format='json').status_code,400)
        p.minimo_compra=0;p.valor=50;p.descuento_maximo=10;p.limite_usuario=1;p.save()
        self.assertEqual(self.c.post('/api/cart/aplicar-cupon/',{'codigo':p.codigo},format='json').status_code,200)
        a=self.checkout(str(uuid.uuid4()));self.assertEqual(a.status_code,201,a.data);self.assertEqual(Decimal(a.data['pedido']['monto_total']),90)
        self.add();self.assertEqual(self.c.post('/api/cart/aplicar-cupon/',{'codigo':p.codigo},format='json').status_code,400)
    def test_other_users_stock_and_idempotency_conflict(self):
        self.add();key=str(uuid.uuid4());self.assertEqual(self.checkout(key).status_code,201)
        self.payload['metodo_pago']='transferencia'
        self.assertEqual(self.checkout(key).status_code,400)
        self.assertEqual(Pedido.objects.count(),1)
        self.assertEqual(self.c.post('/api/admin/promotions/',{},format='json').status_code,403)
