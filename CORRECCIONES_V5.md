# Correcciones v5

Esta versión mantiene React como frontend principal y Django como API.

## Cambios solicitados

- Se corrigió el desborde visual del carrito: las imágenes del catálogo rápido ya no se estiran ni ocupan toda la pantalla.
- Se agregó búsqueda predictiva tipo Steam mientras se escriben 2 o más caracteres.
- El desplegable de búsqueda aparece debajo del input con imagen, nombre y precio.
- Al hacer clic en una sugerencia se abre el detalle del producto.
- El botón Buscar sigue filtrando el catálogo principal usando el backend Django.
- Se reforzó la traducción ES/EN en catálogo, carrito, modal de logout y controles principales.
- Se mantiene el bloqueo de productos/juegos eróticos o adultos desde API e importadores.

## Validaciones

- `python manage.py check`: sin errores.
- `npm run build`: compilación correcta.
