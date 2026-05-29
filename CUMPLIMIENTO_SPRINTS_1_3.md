# Cumplimiento de historias de usuario — Monolith Sprint 1 al Sprint 3

Arquitectura final:

- **React/Vite** es el frontend principal (`http://localhost:3000`).
- **Django + Django REST Framework** queda como backend API (`http://localhost:8000/api/...`).
- Se conservan las rutas legacy de Django solo como respaldo, pero la interfaz principal es React.
- El nombre visual del proyecto es solo **MONOLITH**, sin ícono de marca en el navbar.
- La API bloquea productos/juegos eróticos o adultos mediante lista de exclusión en catálogo, carrito e importadores RAWG.

## Sprint 1 — Usuarios

| HU | Cumplimiento |
|---|---|
| H001.1 | Registro con correo y contraseña en React consumiendo `/api/auth/register/`. |
| H001.2 | Correo de bienvenida separado al registrarse. |
| H002.1 | Inicio de sesión por correo y contraseña usando token DRF. |
| H002.2 | Persistencia de sesión mediante token guardado en `localStorage`. |
| H003.1 | Cierre de sesión accesible desde navbar en React. |
| H003.2 | Modal de confirmación antes de cerrar sesión. |
| H004.1 | Solicitud de restablecimiento vía correo desde React y Django. |
| H004.2 | Cambio de contraseña con enlace/token recibido. |
| H005.1 | Edición de nombre y teléfono desde perfil. |
| H005.2 | Cambio de contraseña desde perfil con contraseña actual. |
| H006.1 | Solicitud de eliminación de cuenta desde perfil. |
| H006.2 | Desactivación de cuenta y anonimización básica de datos personales. |
| H007.1 | Envío de correo de verificación al registrarse. |
| H007.2 | Reenvío de correo de verificación desde perfil. |
| H008.1 | Agregar dirección de envío desde perfil. |
| H008.2 | Editar o eliminar direcciones guardadas. |
| H009.1 | Página de perfil con datos personales y estado del correo. |
| H009.2 | Resumen de actividad reciente: verificación, direcciones, pedidos y último estado. |
| H010.1 | Historial de pedidos en perfil. |
| H010.2 | Filtro de pedidos por fecha y estado. |

## Sprint 2 — Productos

| HU | Cumplimiento |
|---|---|
| H011.1 | Catálogo completo consumiendo `/api/productos/`. |
| H011.2 | Actualización automática mediante recarga al enfocar ventana y polling cada 30 segundos. |
| H012.1 | Búsqueda por nombre con barra de búsqueda. |
| H012.2 | Búsqueda por nombre, descripción, categoría y plataforma. Para 2 letras se usa coincidencia por inicio de palabra para evitar resultados falsos. |
| H013.1 | Filtro por plataforma. |
| H013.2 | Selección múltiple de plataformas. |
| H014.1 | Navegación por categorías. |
| H014.2 | Subcategorías visibles en el sidebar. |
| H015.1 | Página de detalle con información completa del producto. |
| H015.2 | Especificaciones técnicas en panel separado. |
| H016.1 | Precio actual visible en catálogo, detalle y carrito. |
| H016.2 | Precio original, descuento y porcentaje cuando aplica. |
| H017.1 | Estado disponible/sin stock visible. |
| H017.2 | Botón de agregar deshabilitado si no hay stock. |
| H018.1 | Imagen principal en tarjeta de catálogo. |
| H018.2 | Galería de imágenes en detalle. |
| H019.1 | Productos similares en detalle. |
| H019.2 | Productos frecuentemente comprados juntos en detalle. |
| H020.1 | Orden por precio ascendente/descendente. |
| H020.2 | Orden por popularidad o recientes. |

## Sprint 3 — Carrito

| HU | Cumplimiento |
|---|---|
| H021.1 | Catálogo rápido dentro del carrito para seguir agregando productos. |
| H021.2 | Muestra unidades ya agregadas de cada producto. |
| H022.1 | Búsqueda desde carrito. |
| H022.2 | Sugerencias al buscar y sección de recomendados/accesorios. |
| H023.1 | Filtro de plataforma desde carrito. |
| H023.2 | Validación de compatibilidad por intersección de plataformas. |
| H024.1 | Productos agrupados por tipo/categoría. |
| H024.2 | Filtro de productos del carrito por tipo. |
| H025.1 | Acceso al detalle desde cada ítem del carrito. |
| H025.2 | Specs clave visibles en el carrito. |
| H026.1 | Precio actual y subtotal visibles. |
| H026.2 | Aviso si el precio cambió desde que se agregó. |
| H027.1 | Verificación de disponibilidad y stock. |
| H027.2 | Ajuste automático si el stock baja. |
| H028.1 | Imagen visible por producto en carrito. |
| H028.2 | Ampliación de imagen desde carrito. |
| H029.1 | Productos similares/recomendados desde carrito. |
| H029.2 | Accesorios complementarios sugeridos. |
| H030.1 | Orden de productos del carrito por precio. |
| H030.2 | Orden por popularidad. |

## Verificación técnica

- `python manage.py check` ejecutado sin errores.
- `npm run build` ejecutado correctamente en React.
- Búsqueda corta: el backend ya no devuelve todo el catálogo con `th`; filtra por inicio de palabra para evitar falsos positivos.
- Productos adultos/eróticos: bloqueados en API de productos, carrito, importación `cargar_catalogo` e importación `importar_productos`.
