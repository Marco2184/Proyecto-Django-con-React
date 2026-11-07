"""Source/catalog maintenance; never opens a database or changes persisted values."""
import ast
import json
import struct
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PAIRS = {
 'Este correo ya esta registrado.':'This email address is already registered.',
 'Las contraseñas no coinciden.':'The passwords do not match.',
 'La contraseña actual es incorrecta.':'The current password is incorrect.',
 'Credenciales inválidas o cuenta inactiva.':'Invalid credentials or inactive account.',
 'Sesión cerrada.':'Signed out.', 'Sesiones cerradas.':'Signed out of all sessions.',
 'Sesiones revocadas.':'Sessions revoked.', 'Sesión inválida.':'Invalid session.',
 'Servicio no autorizado.':'Unauthorized service.', 'Cuenta inactiva.':'Inactive account.',
 'Sesión inválida o revocada.':'Invalid or revoked session.',
 'Refresh reutilizado; sesión revocada.':'Refresh token reused; session revoked.',
 'Enlace inválido o expirado.':'Invalid or expired link.',
 'Token de autenticación vacío.':'The authentication token is empty.',
 'JWT no configurado en Django.':'Authentication is unavailable.',
 'Tipo de token inválido.':'Invalid token type.',
 'Identificador de usuario inválido.':'Invalid user identifier.',
 'Fechas del token inválidas.':'Invalid token dates.',
 'Token inválido o expirado.':'Invalid or expired token.',
 'Correo verificado correctamente.':'Email verified successfully.',
 'Tu correo ya está verificado.':'Your email is already verified.',
 'Si el correo está registrado, recibirás un enlace en breve.':'If the email address is registered, you will receive a link shortly.',
 'Contraseña actualizada.':'Password updated.',
 'Contraseña actualizada correctamente.':'Password updated successfully.',
 'Cuenta eliminada correctamente.':'Account deleted successfully.',
 'Cuenta creada correctamente.':'Account created successfully.',
 'Debes ingresar tu contraseña para eliminar la cuenta.':'Enter your password to delete your account.',
 'Configura una contraseña Django antes de eliminar la cuenta.':'Set an account password before deleting your account.',
 'Contraseña incorrecta. No se pudo eliminar la cuenta.':'Incorrect password. Your account could not be deleted.',
 'Dirección no encontrada.':'Address not found.', 'Estado invalido.':'Invalid status.',
 'Debe ser posterior a fecha_desde.':'The end date must be after the start date.',
 'Pedido no encontrado.':'Order not found.', 'Usuario no encontrado.':'User not found.',
 'Token Firebase inválido.':'Invalid Firebase token.',
 'El token Firebase no corresponde al usuario autenticado.':'The Firebase token does not match the signed-in user.',
 'Verificación Firebase no disponible.':'Firebase verification is unavailable.',
 'El token Firebase no contiene email.':'The Firebase token has no email address.',
 'El precio no puede ser negativo.':'The price cannot be negative.',
 'El stock no puede ser negativo.':'Stock cannot be negative.',
 'El precio original no puede ser menor al precio actual.':'The original price cannot be lower than the current price.',
 'Se requiere un objeto JSON.':'A JSON object is required.',
 'Producto no encontrado.':'Product not found.',
 'No puedes modificar una cuenta eliminada.':'You cannot change a deleted account.',
 'Solo un superusuario puede cambiar roles o modificar superusuarios.':'Only a superuser can change roles or update superusers.',
 'No puedes desactivar tu propia cuenta de administrador.':'You cannot deactivate your own administrator account.',
 'No puedes quitarte tus propios permisos de administrador.':'You cannot remove your own administrator permissions.',
 'No puedes dejar el sistema sin administradores activos.':'At least one active administrator is required.',
 'Estado de pedido inválido.':'Invalid order status.',
 'Usa texto de hasta 250 caracteres.':'Use no more than 250 characters.',
 'Transición de pedido no permitida.':'This order status change is not allowed.',
 'El pago simulado debe estar aprobado.':'The simulated payment must be approved.',
 'El pedido ya fue cancelado.':'This order has already been cancelled.',
 'No se puede cancelar porque el pedido ya fue enviado o entregado.':'This order cannot be cancelled because it has already been shipped or delivered.',
 'No se puede cancelar porque el pago fue rechazado.':'This order cannot be cancelled because the payment was declined.',
 'Productos compatibles entre sí.':'These products are compatible.',
 'Revisa compatibilidad: no todos los productos comparten una misma plataforma.':'Check compatibility: these products do not all share a platform.',
 'Carrito vacío.':'Your cart is empty.', 'El carrito está vacío.':'Your cart is empty.',
 'No se pudo completar el checkout por un error interno del servidor.':'Checkout could not be completed because of a server error.',
 'La cantidad excede el stock disponible.':'The quantity exceeds available stock.',
 'No puedes aplicar un cupón porque el carrito está vacío.':'You cannot apply a coupon to an empty cart.',
 'Ingresa un código de descuento.':'Enter a discount code.',
 'Código de descuento inválido.':'Invalid discount code.',
 'Pedido creado correctamente.':'Order created successfully.',
 'Completa la dirección de envío.':'Complete the shipping address.',
 'Producto no disponible.':'Product unavailable.', 'Ítem no encontrado.':'Item not found.',
 'No hay stock adicional.':'No additional stock is available.',
 'Cupón removido correctamente.':'Coupon removed successfully.',
 'Solo se admiten datos de demostración: 4111111111111111, CVV 123. No uses datos bancarios reales.':'Only demo details are accepted: 4111111111111111, CVV 123. Do not use real banking information.',
 'Indica mas, menos o una cantidad entera positiva.':'Specify mas, menos or a positive whole quantity.',
 'Cantidad o importe fuera de rango.':'Quantity or amount is out of range.',
 'El total excede el importe máximo permitido.':'The total exceeds the maximum permitted amount.',
 'Completa la dirección de envío antes de pagar.':'Complete the shipping address before paying.',
 'Pedido recibido.':'Order received.',
 'Pago simulado aprobado. Preparando entrega.':'Simulated payment approved. Preparing delivery.',
 'Dirección de envío no encontrada.':'Shipping address not found.',
 'El precio máximo debe ser mayor o igual al mínimo.':'The maximum price must be greater than or equal to the minimum.',
 'Comprobante generado automaticamente por el sistema':'Receipt generated automatically by the system',
 'FACTURA':'SIMULATED RECEIPT', 'Cliente:':'Customer:', 'Cobrar a:':'Merchant:',
 'Pago:':'Payment:', 'Referencia:':'Reference:', 'Fecha:':'Date:',
 'Condiciones de pago:':'Payment terms:', 'Pago simulado aprobado':'Simulated payment approved',
 'Fecha de vencimiento:':'Due date:', 'Orden de Compra:':'Order number:',
 'Saldo Adeudado:':'Balance due:', 'Estado del pedido':'Order status',
 'Direccion':'Address', 'Entrega estimada':'Estimated delivery', 'Articulo':'Item',
 'Cantidad':'Quantity', 'Tasa':'Unit price', 'Importe':'Amount', 'Sin productos':'No products',
 'Descuento aplicado:':'Discount applied:', 'IGV incluido (18%):':'VAT included (18%):',
 'Cantidad Pagada:':'Amount paid:', 'Terminos:':'Terms:',
 'El pago correspondiente a esta compra ha sido completado exitosamente mediante una operacion simulada. No se requiere ninguna accion adicional por parte del cliente en relacion con este pago.':'Payment for this purchase was completed successfully through a simulated transaction. No further payment action is required. No real money was charged.',
 'Este comprobante representa una demostracion academica del flujo de compra de Monolith. Los productos, importes y estado del pago son generados por el sistema para evidenciar el proceso de comercio electronico. Para devoluciones o cambios dentro de una implementacion real, el cliente deberia presentar este comprobante y cumplir las politicas de la tienda.':'This receipt is an academic demonstration of the Monolith shopping process. Products, amounts and payment status demonstrate a simulated ecommerce transaction. This document is not a tax invoice and does not represent a real charge.',
 'Monolith Gaming Store - comprobante de compra':'Monolith Gaming Store - simulated purchase receipt',
 'pendiente':'Pending', 'procesando':'Processing', 'enviado':'Shipped', 'entregado':'Delivered',
 'cancelado':'Cancelled', 'tarjeta':'Card', 'transferencia':'Bank transfer',
 'aprobado':'Approved', 'rechazado':'Declined', 'reembolsado':'Refunded',
}

def main():
    files=['usuarios/api.py','usuarios/admin_api.py','usuarios/order_service.py','usuarios/node_api.py','usuarios/security.py','monolith/node_jwt_auth.py','carrito/api.py','productos/api.py']
    # Only complete messages are wrapped. Status codes and DB values stay intact.
    messages={k:v for k,v in PAIRS.items() if ' ' in k or ':' in k or k in ['FACTURA','Direccion','Articulo','Cantidad','Tasa','Importe']}
    for name in files:
        p=ROOT/name; source=p.read_text(encoding='utf-8-sig'); tree=ast.parse(source)
        lines=source.splitlines(keepends=True); edits=[]
        for n in ast.walk(tree):
            if isinstance(n,ast.Constant) and isinstance(n.value,str) and n.value in messages:
                # f-string parts require interpolation separately.
                if any(isinstance(parent,ast.JoinedStr) and n in parent.values for parent in ast.walk(tree)): continue
                start=sum(len(x) for x in lines[:n.lineno-1])+len(lines[n.lineno-1].encode()[:n.col_offset].decode())
                end=sum(len(x) for x in lines[:n.end_lineno-1])+len(lines[n.end_lineno-1].encode()[:n.end_col_offset].decode())
                edits.append((start,end,'_('+source[start:end]+')'))
        for start,end,new in sorted(edits,reverse=True): source=source[:start]+new+source[end:]
        source='from django.utils.translation import gettext as _\n'+source
        p.write_text(source,encoding='utf-8')
    # Existing Django PO is the single server translation catalog.
    p=ROOT/'locale/en/LC_MESSAGES/django.po'; source=p.read_text(encoding='utf-8')
    for key,value in PAIRS.items():
        if 'msgid '+json.dumps(key,ensure_ascii=False) not in source:
            source+='\nmsgid '+json.dumps(key,ensure_ascii=False)+'\nmsgstr '+json.dumps(value,ensure_ascii=False)+'\n'
    p.write_text(source,encoding='utf-8')
    compile_catalog()

def compile_catalog():
    from gettext_catalog import read_po, write_mo
    write_mo(read_po(ROOT/'locale/en/LC_MESSAGES/django.po'), ROOT/'locale/en/LC_MESSAGES/django.mo')

if __name__=='__main__': raise SystemExit('One-off source update already applied. Use docker/sync_i18n.py.')
