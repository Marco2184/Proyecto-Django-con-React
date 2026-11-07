# Monolith

Tienda de videojuegos con Django REST Framework, React + Vite, un servicio Node.js
y PostgreSQL. Conserva una interfaz cyberpunk oscura con verde neón `#00ff41`,
traducciones español/inglés y pantallas adaptables.

## Funcionalidades

- Catálogo, búsqueda, detalle de productos y carrito persistente.
- Registro con inicio automático de sesión, JWT y refresh en cookie HttpOnly;
  verificación de correo, recuperación de contraseña y revocación de sesiones.
- Wishlist privada por usuario y notificaciones internas de bajadas de precio.
- Checkout con importes calculados por el backend, cupones, IGV incluido,
  control de stock, idempotencia, cancelaciones y comprobante PDF.
- Reseñas de compradores verificados, edición propia y moderación administrativa.
- Panel administrativo con productos, usuarios, pedidos, estadísticas reales,
  historial de inventario y promociones.

El flujo actual de pago registra estados de pago; no debe interpretarse como una
integración certificada con una pasarela bancaria real. Firebase es opcional y no
es necesario para el registro Node/Django.

## Arquitectura

```text
frontend/          React, Vite, Nginx, traducciones y pruebas de navegador
catalog-service/   Node.js: autenticación, catálogo y servicios auxiliares
monolith/          Configuración Django
usuarios/          Usuarios, pedidos, wishlist y API administrativa
productos/         Catálogo, inventario y reseñas
carrito/           Carrito, checkout y promociones
templates/         Plantillas Django y comprobantes
locale/            Traducciones del backend
docker/            Utilidades operativas y verificación aislada
tests/             Pruebas backend y verificador integral Docker
.github/workflows/ Validaciones automáticas sin despliegue
```

## Requisitos e instalación

Python 3.12, Node.js 22 con npm y PostgreSQL. Para Docker, Docker Desktop con el
motor Linux activo. MongoDB se utiliza para observabilidad y está incluido en
Compose. Los comandos siguientes se ejecutan desde la raíz del repositorio.

```powershell
python -m venv .venv
.venv\Scripts\python.exe -m pip install -r requirements.txt
npm ci --prefix frontend
npm ci --prefix catalog-service
npx --prefix frontend playwright install chromium
```

Los lockfiles de npm y requirements.txt se conservan. No es necesario versionar
las dependencias instaladas ni los resultados de compilación.

## Variables de entorno

En una instalación nueva, copiar las plantillas sin sobrescribir archivos locales
que ya contengan configuración:

```powershell
Copy-Item .env.example .env
Copy-Item docker/runtime.env.example .env.docker
```

Editar los archivos localmente. Los valores `REPLACE_WITH...` y la URL de ejemplo
son marcadores y no sirven como credenciales.

| Variable | Uso |
| --- | --- |
| `DATABASE_URL` | PostgreSQL de la aplicación; Neon requiere TLS |
| `SECRET_KEY` | Secreto Django; sustituir el marcador en ambas plantillas copiadas |
| `JWT_SHARED_SECRET` | Secreto compartido por Node y Django, mínimo 32 caracteres |
| `JWT_REFRESH_SECRET` | Secreto distinto para refresh tokens, mínimo 32 caracteres |
| `DEBUG` | `False` para Docker o despliegue; `True` solo en desarrollo privado |
| `GMAIL_CLIENT_ID`, `GMAIL_CLIENT_SECRET`, `GMAIL_REFRESH_TOKEN`, `GMAIL_SENDER_EMAIL` | Envío real de verificación y recuperación mediante Gmail API |
| `EMAIL_HOST_USER`, `EMAIL_HOST_PASSWORD` | Alternativa SMTP existente; acepta alias `MONOLITH_EMAIL` / `MONOLITH_PASSWORD` |
| `MONOLITH_EMAIL_PROVIDER` | `auto` (OAuth completo o SMTP), `gmail_oauth` o `smtp`; no cambia de proveedor si falla un envío |
| `DATABASE_URL_DIRECT` | Opcional: conexión directa sin pooler para respaldo de Neon |
| `MONGO_URI`, `MONGO_DB` | MongoDB para observabilidad; Compose los configura |

Los secretos no deben incluirse en variables `VITE_*`, código frontend, logs ni
GitHub Actions. `.env`, `.env.docker` y `.private/` están excluidos de Git.
La configuración pública del SDK Firebase permanece separada de las claves
privadas de servicio. No es necesario crear cuentas Firebase para usar Monolith.

Consultar [CONFIGURACION_OPERATIVA.md](CONFIGURACION_OPERATIVA.md) para Gmail OAuth2,
permisos Docker, respaldo, integridad SHA256 y ensayo local de migraciones.

## Docker: entorno de pruebas aislado

Para comprobar la aplicación sin usar Neon ni enviar correos reales:

```powershell
node tests/docker_verify.mjs
```

El verificador reconstruye las imágenes y levanta `compose.verify.yaml` bajo el
proyecto Docker `monolith-verification`, con PostgreSQL temporal, MongoDB y cuentas
sintéticas. Ejecuta pruebas backend, HTTP y navegador. Requiere acceso al motor
Docker y las dependencias de navegador instaladas. No utilizar `--http-only` para
certificar reconstrucción de imágenes: ese modo solo comprueba servicios existentes.

| Servicio aislado | URL |
| --- | --- |
| React/Nginx | http://127.0.0.1:13001 |
| Panel React | http://127.0.0.1:13001/admin |
| Django | http://127.0.0.1:18001/ |
| Salud Node | http://127.0.0.1:14001/health |

Para retirar exclusivamente ese entorno de pruebas y sus datos temporales:

```powershell
docker compose -p monolith-verification -f compose.verify.yaml down -v
```

## Docker con la base configurada

Revisar primero las migraciones y autorizar cualquier modificación de una base
real. El arranque no sustituye ese procedimiento ni autoriza migraciones en Neon.

```powershell
docker compose build django node frontend
docker compose up -d
docker compose ps
```

El stack habitual expone React en http://localhost:3000, Django en
http://localhost:8000 y Node en http://localhost:4000/health. El panel React está en
http://localhost:3000/admin. Nginx comunica frontend, Node y Django internamente.
La base PostgreSQL se obtiene de DATABASE_URL; Compose no crea una base Neon.

## Desarrollo sin Docker

Usar una base PostgreSQL propia de desarrollo. Solo sobre una base nueva local
o una base cuya actualización haya sido autorizada:

```powershell
.venv\Scripts\python.exe manage.py migrate
.venv\Scripts\python.exe manage.py runserver 8000
```

En otras dos terminales, desde la raíz:

```powershell
node --env-file=.env --env-file=.env.docker catalog-service/src/server.js
npm run dev --prefix frontend
```

Vite sirve en http://localhost:3000 y utiliza sus proxies a Django:8000 y Node:4000.
Para observabilidad sin Docker configurar MONGO_URI de un MongoDB local. El módulo
El correo comparte transporte entre API y vistas Django y acepta configuración
de Django/decouple o variables inyectadas. Reutilizar las credenciales existentes
del proveedor elegido; no es obligatorio migrar SMTP a OAuth.
Los permisos administrativos y la verificación del correo se aplican en backend.
No ejecutar `create_admin.py` automáticamente: crea o modifica una cuenta
administrativa y requiere una decisión explícita del operador.

## Pruebas y CI

```powershell
$env:DJANGO_SETTINGS_MODULE='monolith.test_settings'
.venv\Scripts\python.exe manage.py check
.venv\Scripts\python.exe manage.py makemigrations --check --dry-run
.venv\Scripts\python.exe manage.py test tests
npm test --prefix frontend
npm test --prefix catalog-service
npm run build --prefix frontend
node --test frontend/test/browser.mjs
```

Cerrar esa terminal o retirar DJANGO_SETTINGS_MODULE antes de volver a ejecutar la
aplicación normal. Las pruebas Django usan SQLite en memoria por defecto y omiten
concurrencia; para comprobar bloqueos configurar TEST_DATABASE_URL de un PostgreSQL
aislado. Nunca usar Neon. El navegador local usa su base temporal y correo en memoria.
Si esbuild está restringido, compilar con
`npm run build --prefix frontend -- --configLoader runner`.

GitHub Actions comprueba Django sobre PostgreSQL aislado, autenticación Node,
traducciones, compilación React y navegador. No contiene despliegues ni requiere
secretos de producción. Revisar resultados reales de cada ejecución antes de
considerar validada una instalación.

## Seguridad y operación

- No versionar `.env`, tokens, claves privadas, dumps, bases SQLite, ZIP o respaldos.
- Respaldar y ensayar las migraciones antes de autorizarlas en una base real.
- La configuración de Gmail y la auditoría satisfactoria por sí solas no prueban
  recepción real del correo ni restauración completa de los datos.
- Conservar recursos `media/` por separado: un respaldo PostgreSQL no incluye archivos.
- Render y Vercel conservan la arquitectura y configuraciones existentes; las
  variables reales se configuran privadamente en cada entorno. No hay despliegue automático.

Más detalles: [OPERACION.md](OPERACION.md) y
[CONFIGURACION_OPERATIVA.md](CONFIGURACION_OPERATIVA.md).
