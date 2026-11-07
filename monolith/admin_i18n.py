"""Localized admin labels. Identifiers, columns and persisted choices are unchanged."""
from django.utils.translation import gettext_lazy as lazy

LABELS = {'is_active':'Activo','is_staff':'Administrador','token_verificacion':'C\u00f3digo de verificaci\u00f3n',
    'nombre':'Nombre', 'telefono':'Teléfono', 'fecha_registro':'Fecha de registro',
    'email_verificado':'Correo verificado', 'cuenta_activa':'Cuenta activa', 'usuario':'Usuario',
    'calle':'Calle', 'ciudad':'Ciudad', 'departamento':'Departamento', 'codigo_postal':'Código postal',
    'predeterminada':'Predeterminada', 'creado_en':'Creado el', 'numero':'Número',
    'fecha':'Fecha', 'monto_total':'Total', 'estado':'Estado', 'direccion_envio':'Dirección de envío',
    'direccion_texto':'Dirección', 'metodo_pago':'Método de pago', 'estado_pago':'Estado del pago',
    'referencia_pago':'Referencia de pago', 'fecha_estimada_entrega':'Entrega estimada',
    'entregado_en':'Entregado el', 'cancelado_en':'Cancelado el', 'motivo_cancelacion':'Motivo de cancelación',
    'pedido':'Pedido', 'producto':'Producto', 'producto_nombre':'Nombre del producto',
    'producto_imagen':'Imagen del producto', 'cantidad':'Cantidad', 'precio_unitario':'Precio unitario',
    'descripcion':'Descripción', 'precio':'Precio', 'precio_original':'Precio original',
    'imagen_principal':'Imagen principal', 'imagen_url':'URL de imagen', 'categoria':'Categoría',
    'plataformas':'Plataformas', 'valoracion':'Valoración', 'ventas':'Ventas',
    'especificaciones':'Especificaciones', 'activo':'Añadido el', 'actualizado':'Actualizado el',
    'padre':'Categoría superior', 'icono':'Icono', 'imagen':'Imagen', 'orden':'Orden',
    'carrito':'Carrito', 'codigo_cupon':'Código del cupón',
}
MODELS = {
 'Usuario':('Usuario','Usuarios'), 'DireccionEnvio':('Dirección de envío','Direcciones de envío'),
 'Pedido':('Pedido','Pedidos'), 'PedidoItem':('Item de pedido','Items de pedido'),
 'PedidoTimeline':('Evento de pedido','Eventos de pedido'), 'Producto':('Producto','Productos'),
 'Plataforma':('Plataforma','Plataformas'), 'Categoria':('Categoría','Categorías'),
 'ImagenProducto':('Imagen de producto','Imágenes de producto'), 'Carrito':('Carrito','Carritos'),
 'ItemCarrito':('Item de carrito','Items de carrito'),
}
def localize_admin_models(*models):
    for model in models:
        singular, plural = MODELS[model.__name__]
        model._meta.verbose_name, model._meta.verbose_name_plural = lazy(singular), lazy(plural)
        for field in model._meta.fields + model._meta.many_to_many:
            if field.name in LABELS: field.verbose_name = lazy(LABELS[field.name])
            if field.choices and field.name in ('estado','metodo_pago','estado_pago'):
                field.choices = [(code, lazy(label)) for code,label in field.choices]
