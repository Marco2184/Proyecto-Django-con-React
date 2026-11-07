"""Idempotent synthetic fixtures, restricted to the disposable Docker database."""
from django.conf import settings
from django.db import transaction

assert settings.SETTINGS_MODULE == 'docker.verification_settings'
assert settings.DATABASES['default']['HOST'] == 'postgres-test'
assert settings.DATABASES['default']['NAME'] == 'monolith_verification'

from usuarios.models import Usuario, Pedido, PedidoItem
from productos.models import Producto, Categoria, Plataforma
from productos.inventory import record_stock

with transaction.atomic():
    password = 'BrowserFixture!78419'  # Synthetic localhost-only test accounts.
    for email, name, admin in [
        ('browser-admin@example.invalid', 'Browser Admin', True),
        ('browser-buyer@example.invalid', 'Browser Buyer', False),
    ]:
        user, created = Usuario.objects.get_or_create(email=email, defaults={
            'nombre': name, 'email_verificado': True, 'is_staff': admin, 'is_superuser': admin,
        })
        if created:
            user.set_password(password)
            user.save(update_fields=['password'])
    buyer = Usuario.objects.get(email='browser-buyer@example.invalid')
    category, _ = Categoria.objects.get_or_create(nombre='Videojuegos')
    platform, _ = Plataforma.objects.get_or_create(nombre='PC')
    product, created = Producto.objects.get_or_create(nombre='Monolith Test Game', defaults={
        'precio': 100, 'stock': 100, 'categoria': category, 'valoracion': 4,
    })
    if created:
        product.plataformas.add(platform)
        record_stock(product, 0, 'inicial', 'Docker verification fixture')
    if not PedidoItem.objects.filter(pedido__usuario=buyer, producto=product, pedido__estado_pago='aprobado').exists():
        order = Pedido.objects.create(usuario=buyer, monto_total=product.precio, estado='procesando', estado_pago='aprobado')
        PedidoItem.objects.create(pedido=order, producto=product, producto_nombre=product.nombre,
            cantidad=1, precio_unitario=product.precio, subtotal=product.precio)
print('Isolated Docker fixtures ready; no existing accounts were modified.')
