"""Disposable browser fixtures. Refuses to run using application settings."""
import os
import sys
from pathlib import Path
from wsgiref.simple_server import make_server,WSGIRequestHandler

root=Path(__file__).resolve().parent.parent
sys.path.insert(0,str(root))
sys.dont_write_bytecode=True
assert os.environ.get('DJANGO_SETTINGS_MODULE')=='monolith.test_settings'
assert os.environ.get('MONOLITH_BROWSER_TEST')=='1'
import django
django.setup()
from django.conf import settings
assert Path(settings.DATABASES['default']['NAME']).resolve()==(root/'.browser-test.sqlite3').resolve()
from django.core.management import call_command
call_command('migrate',verbosity=0,interactive=False)
from usuarios.models import Usuario,Pedido,PedidoItem
from productos.models import Producto,Plataforma,Categoria

password='BrowserFixture!78419'
admin=Usuario.objects.create_superuser('browser-admin@example.invalid','Browser Admin',password)
buyer=Usuario.objects.create_user('browser-buyer@example.invalid','Browser Buyer',password,email_verificado=True)
category=Categoria.objects.create(nombre='Videojuegos')
platform=Plataforma.objects.create(nombre='PC')
product=Producto.objects.create(nombre='Monolith Test Game',precio=100,stock=10,categoria=category,valoracion=4)
product.plataformas.add(platform)
order=Pedido.objects.create(usuario=buyer,monto_total=100,estado='procesando',estado_pago='aprobado')
PedidoItem.objects.create(pedido=order,producto=product,producto_nombre=product.nombre,cantidad=1,precio_unitario=100,subtotal=100)
from django.core.wsgi import get_wsgi_application
class Quiet(WSGIRequestHandler):
    def log_message(self,*args):pass
with make_server('127.0.0.1',8000,get_wsgi_application(),handler_class=Quiet) as server:server.serve_forever()
