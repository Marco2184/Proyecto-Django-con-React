# Monolith: ejecución y validación

Para permisos Docker, auditoría Neon sin escrituras, respaldo y configuración
Gmail OAuth2, consultar [CONFIGURACION_OPERATIVA.md](CONFIGURACION_OPERATIVA.md).

Se mantienen Django REST Framework, React/Vite, el servicio Node y PostgreSQL.
Los archivos de entorno locales se conservan; no se incluyen en imágenes ni CI.

## Uso local habitual con Neon

La configuración principal es `compose.yaml`, proyecto Docker `monolith`.
`compose.verify.yaml` es opcional para CI/pruebas y no es necesario para usar la
aplicación real. No usar `tests/docker_verify.mjs` para iniciar el uso habitual:
ese comando levanta exclusivamente cuentas y bases sintéticas.

La aplicación habitual usa http://localhost:3000, Django http://localhost:8000 y
salud Node http://localhost:4000/health. Usar localhost consistentemente para las
cookies y enlaces de correo. Django recibe DATABASE_URL de .env (o del entorno
del terminal, si existe); .env.docker suministra secretos operativos y Gmail.
Node habla con http://django:8000/api y no necesita una conexión directa a Neon.
MongoDB local almacena observabilidad, no sustituye usuarios ni pedidos PostgreSQL.

Antes de actualizar esta instalación: completar respaldo real verificado y ensayo
con `docker/neon_rehearse.py`; después solicitar autorización explícita para las
migraciones de Neon. No iniciar la versión nueva sobre el esquema anterior.
Consultar el procedimiento completo en CONFIGURACION_OPERATIVA.md.

## Dependencias

Python 3.12 y Node 22. Instalar con `pip install -r requirements.txt`,
`npm ci --prefix frontend` y `npm ci --prefix catalog-service`.
Los archivos de bloqueo forman parte del proyecto. Para probar el navegador,
instalar Chromium con `npx --prefix frontend playwright install chromium`.

## Migraciones y ejecución

Revisar y aplicar las migraciones nuevas mediante `python manage.py migrate`
en el entorno que corresponda, después de autorizar la actualización de esa base.
Este trabajo no ejecuta migraciones sobre Neon ni despliega a producción.
La restricción de correo ignora diferencias entre mayúsculas y minúsculas:
si existen variantes duplicadas previas, la migración se detiene sin borrar cuentas.

Ejecutar el stack existente mediante `docker compose up --build` una vez
configurados los entornos y aplicadas las migraciones. Para desarrollo local:
`python manage.py runserver`, `npm run dev --prefix catalog-service` y
`npm run dev --prefix frontend`. Vite conserva los proxies existentes.

## Reglas nuevas

- Registro automático mediante `/auth/register` en Node, con `Idempotency-Key`
  UUID. Node usa el callback firmado `/api/auth/node/register/`, entrega access
  JWT y guarda refresh únicamente en cookie HttpOnly. Los reintentos usan la
  misma clave y contraseña; Django no almacena contraseñas sin hash.
- El correo queda pendiente. El usuario puede usar perfil, carrito y wishlist;
  completar compras, publicar/editar reseñas y realizar escrituras administrativas
  requiere correo verificado. La recuperación, revocación y refresh se conservan.
- Firebase heredado exige tokens no revocados y correo verificado antes de
  vincular cuentas. El registro nuevo no crea otra cuenta Firebase.
- `/api/wishlist/`, `/api/wishlist/<producto>/` (PUT/DELETE),
  `/api/wishlist/sync/` y `/api/notifications/<id>/read/` son privados por usuario.
  Sincronizar descubre bajadas respecto del precio guardado; cada precio se
  notifica una vez. No se envían correos de wishlist.
- `/api/productos/<id>/reviews/` consulta/publica reseñas y
  `/api/productos/<id>/reviews/mine/` edita/elimina la propia. Las compras deben
  estar aprobadas y no canceladas. Una reseña por usuario/producto; las reseñas
  ocultas o de compras canceladas no contribuyen al promedio verificado.
  `Producto.valoracion` sigue siendo el dato externo importado.
- El dashboard existente acepta `desde`/`hasta`; ingresos y top de ventas se
  calculan sobre pagos aprobados no cancelados. No se reconstruye un historial
  de stock anterior que nunca fue registrado.
- `/api/admin/inventory/`, `/api/admin/reviews/` y
  `/api/admin/promotions/` amplían las herramientas administrativas.
  Los ajustes registran administrador, motivo, fecha y balance de stock.
- Los cupones MONOLITH10, GAMER20 y NEON50 se incorporan con una migración de
  datos que no sobrescribe promociones existentes. Cada checkout revalida fechas,
  mínimos y límites bajo bloqueo. Cancelar no repone el uso del cupón, para evitar
  reutilización abusiva; sí devuelve stock una sola vez.
- `/api/cart/checkout/` requiere `Idempotency-Key` UUID. Repetirlo con los mismos
  datos devuelve el resultado guardado. Cambiar los datos con una clave ya usada
  produce un error. No se aceptan importes finales del cliente. El IGV del 18%
  continúa incluido en el total del comprobante, sin sumarse otra vez.

## Pruebas aisladas y CI

PowerShell: `$env:DJANGO_SETTINGS_MODULE='monolith.test_settings'` y después
`python manage.py test tests`. Para comprobar bloqueos concurrentes, proporcionar
`TEST_DATABASE_URL` de un PostgreSQL aislado en localhost; el módulo rechaza hosts
externos. Nunca usar Neon para pruebas. Sin PostgreSQL, las pruebas de concurrencia se omiten.

`npm test --prefix frontend`, `npm test --prefix catalog-service`,
`npm run build --prefix frontend` y `node --test frontend/test/browser.mjs`.
Las pruebas de navegador usan una base SQLite temporal y cuentas sintéticas
`example.invalid`; eliminan la base y no guardan capturas, vídeos ni informes.
En un entorno con restricciones de esbuild se puede compilar con
`npm run build --prefix frontend -- --configLoader runner`.

GitHub Actions ejecuta pruebas sobre PostgreSQL 17 aislado, traducciones,
autenticación Node, compilación y navegador. No contiene despliegues ni secretos
de producción. Los archivos mínimos de pruebas se conservan para ese workflow.

## Verificación completa mediante Docker

Desde la raíz del proyecto, con un terminal que tenga acceso al motor Docker:

```powershell
node tests/docker_verify.mjs
```

El verificador usa exclusivamente `compose.verify.yaml`, con el proyecto Docker
`monolith-verification`. No lee archivos `.env` dentro de los contenedores, no usa
Neon y no sustituye las imágenes, puertos ni volúmenes del stack habitual.
Las migraciones y las cuentas sintéticas se crean únicamente en el PostgreSQL
temporal `postgres-test`. Gmail usa memoria y Firebase no recibe solicitudes.

Se construyen las imágenes existentes de Django, Node y React/Nginx; se levantan
PostgreSQL, MongoDB y los servicios de aplicación. A continuación se ejecutan las
pruebas Django en PostgreSQL, comprobaciones HTTP de autenticación, wishlist,
carrito, cupón, checkout idempotente, reseñas y permisos administrativos, las
pruebas de navegador existentes a través de Nginx y la revisión de logs.
Se necesitan las dependencias de navegador instaladas en el host, tal como se
indica arriba. No se guardan capturas, vídeos ni informes de resultados.

Las siguientes URL corresponden al stack aislado **solo después de que el
verificador confirme el arranque y las comprobaciones**:

- React/Nginx: `http://127.0.0.1:13001`
- Panel React: `http://127.0.0.1:13001/admin`
- Django: `http://127.0.0.1:18001/`
- Salud Node: `http://127.0.0.1:14001/health`

Al terminar correctamente, los contenedores quedan disponibles para inspección.
PostgreSQL y Mongo usan almacenamiento temporal. Para detener y retirar solamente
esta verificación, sin afectar al stack normal:

```powershell
docker compose -p monolith-verification -f compose.verify.yaml down -v
```

Si Docker responde `permission denied` al acceder a `docker_engine`, el terminal
actual no puede ejecutar esta verificación aunque Docker Desktop esté abierto.
Ejecutar el comando desde el PowerShell habitual con acceso a Docker; no es
necesario exponer la API de Docker por TCP ni modificar la base de producción.

Si el stack aislado ya está levantado pero el terminal actual no puede acceder
a la API de Docker, se pueden ejecutar únicamente las comprobaciones HTTP y de
navegador mediante `node tests/docker_verify.mjs --http-only`. Este modo exige
primero la marca de aislamiento del PostgreSQL temporal; no construye imágenes,
no ejecuta pruebas dentro de contenedores ni inspecciona sus logs. Esas fases se
indican expresamente como pendientes, sin sustituir la verificación completa.

Para repetir solo el navegador: `node tests/docker_verify.mjs --http-only --browser-only`.
Se puede seleccionar un caso agregando `--test-name-pattern "nombre de la prueba"`.
La prueba de checkout contempla direcciones guardadas: selecciona explícitamente
"Nueva dirección" antes de rellenar Calle, espera las respuestas del carrito y
contrasta importes con la API y el PDF real, sin reemplazar precios del servidor.
