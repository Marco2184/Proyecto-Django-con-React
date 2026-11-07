from django.test import TestCase
from rest_framework.test import APIClient
from usuarios.models import Usuario,Pedido,PedidoItem
from productos.models import Producto,Review

class ReviewTests(TestCase):
    def test_purchase_ownership_edit_delete_and_moderation(self):
        a=Usuario.objects.create_user('a@example.invalid','Public name','password',email_verificado=True)
        b=Usuario.objects.create_user('b@example.invalid','Other','password',email_verificado=True)
        admin=Usuario.objects.create_superuser('admin@example.invalid','Admin','password')
        p=Producto.objects.create(nombre='Game',precio=100,stock=3,valoracion=4)
        order=Pedido.objects.create(usuario=a,monto_total=100,estado_pago='aprobado',estado='procesando')
        PedidoItem.objects.create(pedido=order,producto=p,producto_nombre=p.nombre,cantidad=1,precio_unitario=100,subtotal=100)
        c=APIClient();path=f'/api/productos/{p.pk}/reviews/'
        c.force_authenticate(b);self.assertEqual(c.post(path,{'puntuacion':5,'comentario':'Nice game'},format='json').status_code,403)
        c.force_authenticate(a)
        self.assertEqual(c.post(path,{'puntuacion':6,'comentario':'Nice game'},format='json').status_code,400)
        self.assertEqual(c.post(path,{'puntuacion':5,'comentario':'Nice game'},format='json').status_code,201)
        self.assertEqual(c.post(path,{'puntuacion':5,'comentario':'Again'},format='json').status_code,400)
        self.assertEqual(c.patch(path+'mine/',{'puntuacion':4},format='json').status_code,200)
        data=c.get(path).data;self.assertEqual(data['summary']['promedio'],4);self.assertEqual(data['valoracion_externa'],'4.0')
        review=Review.objects.get();c.force_authenticate(admin)
        self.assertEqual(c.patch('/api/admin/reviews/',{'id':review.pk,'visible':False,'motivo':'Moderated'},format='json').status_code,200)
        self.assertEqual(c.get(path).data['summary']['cantidad'],0)
        c.force_authenticate(b);self.assertEqual(c.delete(path+'mine/').status_code,404)
        c.force_authenticate(a);self.assertEqual(c.delete(path+'mine/').status_code,204)
