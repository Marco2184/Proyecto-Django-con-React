from django.test import TestCase
from rest_framework.test import APIClient
from usuarios.models import Usuario, WishlistItem, PriceNotification
from productos.models import Producto

class WishlistTests(TestCase):
    def test_isolation_persistence_price_notification_deduplication(self):
        a=Usuario.objects.create_user('a@example.invalid','A','password')
        b=Usuario.objects.create_user('b@example.invalid','B','password')
        p=Producto.objects.create(nombre='Game',precio=100,stock=3)
        c=APIClient();c.force_authenticate(a)
        path=f'/api/wishlist/{p.pk}/'
        self.assertEqual(c.put(path).status_code,201)
        self.assertEqual(c.put(path).status_code,200)
        self.assertEqual(WishlistItem.objects.count(),1)
        p.precio=80;p.save()
        c.post('/api/wishlist/sync/');c.post('/api/wishlist/sync/')
        self.assertEqual(PriceNotification.objects.count(),1)
        n=PriceNotification.objects.get()
        c.force_authenticate(b)
        self.assertEqual(c.get('/api/wishlist/').data['items'],[])
        self.assertEqual(c.post(f'/api/notifications/{n.pk}/read/').status_code,404)
        c.delete(path);self.assertEqual(WishlistItem.objects.count(),1)
        c.force_authenticate(a);c.post(f'/api/notifications/{n.pk}/read/')
        self.assertEqual(c.get('/api/wishlist/').data['notifications'],[])
        c.delete(path);self.assertEqual(WishlistItem.objects.count(),0)

    def test_out_of_stock_product_keeps_its_detail_page(self):
        p=Producto.objects.create(nombre='Out of stock game',precio=100,stock=0)
        response=APIClient().get(f'/api/productos/{p.pk}/')
        self.assertEqual(response.status_code,200)
        self.assertFalse(response.data['disponible'])
