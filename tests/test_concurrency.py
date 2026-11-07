"""Requires real PostgreSQL row locks; SQLite is explicitly skipped."""
import uuid
from concurrent.futures import ThreadPoolExecutor
from threading import Barrier
from unittest import skipUnless
from django.db import connection, close_old_connections
from django.test import TransactionTestCase
from rest_framework.test import APIClient
from productos.models import Producto
from usuarios.models import Usuario,Pedido

@skipUnless(connection.vendor=='postgresql','Requires isolated PostgreSQL (CI service)')
class ConcurrentCheckoutTests(TransactionTestCase):
    def setUp(self):
        self.product=Producto.objects.create(nombre='Last copy',precio=100,stock=1)
        self.users=[Usuario.objects.create_user(f'buyer{i}@example.invalid',f'Buyer {i}','password',email_verificado=True) for i in range(2)]
        self.payload={'direccion':{'calle':'Calle 123','ciudad':'Lima','departamento':'Lima','codigo_postal':'15001'},'metodo_pago':'transferencia','pago':{}}
        for user in self.users:
            c=APIClient();c.force_authenticate(user);c.post('/api/cart/add/',{'producto_id':self.product.pk,'cantidad':1},format='json')
    def run_pair(self,same_user=False):
        barrier=Barrier(2);key=str(uuid.uuid4())
        def buy(index):
            close_old_connections()
            try:
                c=APIClient();c.force_authenticate(Usuario.objects.get(pk=self.users[0 if same_user else index].pk));barrier.wait(timeout=10)
                r=c.post('/api/cart/checkout/',self.payload,format='json',HTTP_IDEMPOTENCY_KEY=key if same_user else str(uuid.uuid4()))
                return r.status_code
            finally:close_old_connections()
        with ThreadPoolExecutor(max_workers=2) as pool:return sorted(pool.map(buy,range(2)))
    def test_last_copy_only_sold_once(self):
        self.assertEqual(self.run_pair(),[201,400]);self.product.refresh_from_db()
        self.assertEqual(self.product.stock,0);self.assertEqual(Pedido.objects.count(),1)
    def test_simultaneous_retry_returns_single_order(self):
        self.assertEqual(self.run_pair(True),[200,201]);self.product.refresh_from_db()
        self.assertEqual(self.product.stock,0);self.assertEqual(Pedido.objects.count(),1)

    def test_last_coupon_use_cannot_be_consumed_twice(self):
        from carrito.models import Promotion,CouponUse
        self.product.stock=2;self.product.save()
        promotion=Promotion.objects.create(codigo='LAST_ONE',tipo='porcentaje',valor=10,limite_total=1)
        for user in self.users:
            c=APIClient();c.force_authenticate(user)
            self.assertEqual(c.post('/api/cart/aplicar-cupon/',{'codigo':promotion.codigo},format='json').status_code,200)
        self.assertEqual(self.run_pair(),[201,400])
        promotion.refresh_from_db();self.assertEqual(promotion.usos,1)
        self.assertEqual(CouponUse.objects.count(),1)
