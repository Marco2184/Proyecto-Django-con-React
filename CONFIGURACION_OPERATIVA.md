# Operación segura de Monolith

Leer también OPERACION.md. No ejecutar migraciones, restauraciones ni pruebas de
compra sobre Neon sin autorización explícita. Firebase permanece opcional.

El plan concreto previo a la aprobación está en [ACTUALIZACION_NEON.md](ACTUALIZACION_NEON.md).

## Transición al uso real local

El único Compose principal para uso normal es `compose.yaml`, proyecto `monolith`.
No depende de `monolith-verification`. Para dejar de ejecutar el entorno de pruebas,
desde el PowerShell habitual con acceso a Docker:

```powershell
docker compose -p monolith-verification -f compose.verify.yaml stop
docker compose -p monolith -f compose.yaml ps
```

`stop` afecta únicamente al proyecto de verificación; no borra volúmenes ni imágenes.
El PostgreSQL temporal no interviene en la aplicación real. El ensayo de un respaldo
real, por seguridad, sí requiere una copia local aislada que nunca reemplaza Neon.

Secuencia para la actualización real (todavía pendiente):

1. Configurar DATABASE_URL_DIRECT en editor privado, ejecutar --check-direct,
   crear respaldo con --backup, verificarlo con --verify-backup y ensayarlo con
   neon_rehearse.py. Revisar resultado y configuración regional de la base.
2. Obtener autorización explícita para las ocho migraciones y acordar una ventana
   sin escrituras. Si Render u otro servicio utiliza el mismo Neon, sus escritores
   también deben coordinarse; detener solo Docker local no garantiza exclusividad.
   No cambiar Render automáticamente. Renovar el respaldo dentro de esa ventana.
3. Desde un terminal sin DATABASE_URL o JWT_SHARED_SECRET heredados de otro entorno,
   reconstruir las imágenes del Compose principal con el código actual. Detener
   frontend, Node y Django durante el cambio. Solo tras la autorización, ejecutar
   `manage.py migrate` en el contenedor Django principal, no en verification.
4. Arrancar el Compose principal y comprobar salud, logs, tablas y migraciones.
   No usar pruebas sintéticas contra Neon. El propietario inicia sesión con su
   contraseña existente; no compartirla, ejecutar create_admin.py ni restablecerla
   para probar. Las pruebas autenticadas pueden registrar sesión/último acceso:
   el propietario debe realizarlas o autorizarlas expresamente.
5. Verificar mediante lectura catálogo y panel, y comprobar disponibilidad de las
   páginas de wishlist, reseñas, promociones, carrito y checkout. No agregar,
   eliminar, comprar, cancelar o moderar datos reales como prueba sin autorización.

URLs previstas: http://localhost:3000, panel http://localhost:3000/admin,
Django http://localhost:8000 y Node http://localhost:4000/health.
Los servicios esperados son monolith-frontend-1, monolith-django-1,
monolith-node-1 y monolith-mongo-1; media-init es una tarea puntual y puede estar
finalizada correctamente. Confirmar nombres e imágenes con `docker compose ps`.

Un HTTP 200 no certifica que la imagen esté actualizada ni que las ocho migraciones
se hayan aplicado. No mostrar `docker compose config` completo ni `docker inspect`
sin filtrado: pueden revelar credenciales inyectadas.

## Docker: permisos y reconstrucción

La sesión del agente usa `marco\codexsandboxoffline` y no puede abrir
`//./pipe/docker_engine` ni leer los contextos privados de Marco. Esto impide
reconstruir imágenes e inspeccionar logs; que HTTP responda no demuestra que las
imágenes contengan los últimos cambios. No exponer Docker por TCP ni ampliar ACL
del sandbox. La instalación por usuario de Docker Desktop no requiere el grupo
docker-users: su ausencia no demuestra un fallo de instalación.

Abrir un PowerShell normal del usuario Marco que inició Docker Desktop:

```powershell
Set-Location 'C:\Users\marco\Desktop\Proyecto-Django-con-React-main\Proyecto-Django-con-React-main'
whoami
docker context ls
# Solo si desktop-linux figura en la lista:
docker context use desktop-linux
docker info
node tests/docker_verify.mjs
```

Si ese mismo PowerShell tampoco accede al canal, reiniciar Docker Desktop desde
la sesión de Marco y repetir docker info. No aplicar instrucciones de grupos de
una instalación global a esta instalación por usuario sin revisar el diagnóstico.
El verificador construye Django, Node y React y solo modifica el stack aislado
monolith-verification. No ejecutar docker system prune.

## Neon: auditoría sin escrituras y respaldo

```powershell
.venv\Scripts\python.exe docker/neon_preflight.py
```

Usa DATABASE_URL existente, TLS, transacciones de solo lectura y tiempo límite.
No muestra usuarios, correos, cadenas de conexión ni respuestas internas del
proveedor. Compara el registro de las ocho migraciones, detecta grupos de correos
duplicados incluyendo vacíos, tablas/columnas parcialmente creadas y sesiones
visibles esperando bloqueos. No sustituye la comparación completa del esquema.

DATABASE_URL se obtiene primero del entorno del proceso, después de .env y luego
de .env.docker, para respetar la interpolación de compose.yaml. Ejecutar desde un
PowerShell nuevo sin una DATABASE_URL heredada que apunte a otro entorno. El código
10013 indica acceso de red denegado en esa sesión; no implica credenciales inválidas.

Migraciones a revisar:

- usuarios: 0005_email_case_unique, 0006_wishlist, 0007_promotions_checkout.
- productos: 0002_stock_movements, 0003_verified_reviews.
- carrito: 0003_promotions_checkout, 0004_legacy_coupons, 0005_promotion_constraints.

Riesgos: correos que solo difieren en mayúsculas impiden crear el índice único;
no fusionar ni borrar cuentas automáticamente. Las tablas nuevas no reconstruyen
historiales anteriores. Los campos checkout de pedidos antiguos admiten ausencia
de clave. La migración de cupones incorpora tres promociones sin sobrescribir los
registros con exactamente el mismo código. Si existiera una promoción con variante
de mayúsculas creada fuera de estas migraciones, revisar antes de migrar. Los
índices, claves y ALTER TABLE pueden requerir bloqueos y ventana de mantenimiento.

Para respaldar, obtener desde Connect de Neon la conexión **sin Connection
pooling** y guardarla localmente en DATABASE_URL_DIRECT dentro de .env.docker,
con editor local; no pegarla en terminal, chat ni comandos. No se deduce ni modifica
automáticamente el hostname de DATABASE_URL.

```powershell
.venv\Scripts\python.exe docker/neon_preflight.py --backup
```

Antes de crear el respaldo puede comprobarse la configuración sin conexión:

```powershell
.venv\Scripts\python.exe docker/neon_preflight.py --check-direct
```

Requiere un único hostname directo Neon, sin pooler ni hostaddr que redirija la
conexión. Compara endpoint y nombre de base con DATABASE_URL sin imprimir valores.
No demuestra conectividad ni permisos: esos se comprueban al crear el respaldo.

Requiere pg_dump/pg_restore (PostgreSQL 18 está instalado en este equipo; el cliente
debe soportar la versión del servidor). Solo lee Neon. Crea un archivo custom
`.dump`, nunca ZIP, en `.private/backups`, con manifiesto de tamaño, SHA256 y
validación del índice del archivo. Las credenciales viajan por entorno del proceso,
no por argumentos. No confundir esa validación con una restauración ensayada.
El respaldo contiene datos privados: mantenerlo en almacenamiento protegido del
usuario y fuera de Git, imágenes y carpetas compartidas. El script no cifra el dump.

Para verificar posteriormente un respaldo existente, sin conexión a Neon:

```powershell
.venv\Scripts\python.exe docker/neon_preflight.py --verify-backup '.private/backups/NOMBRE.dump'
```

Sustituir NOMBRE por el archivo realmente generado. Valida nombre, tamaño y SHA256
contra el manifiesto y comprueba que se registró la validación inicial del índice.
No ejecuta pg_restore ni certifica un ensayo de recuperación. No compartir el dump.

## Ensayo automático exclusivamente local

Con PostgreSQL 18 instalado y un respaldo real ya verificado:

```powershell
.venv\Scripts\python.exe docker/neon_rehearse.py '.private/backups/NOMBRE.dump'
```

Este comando no lee DATABASE_URL ni conecta con Neon. Inicializa un clúster nuevo
en .private, con autenticación SCRAM y contraseña aleatoria, enlazado únicamente a
127.0.0.1 en un puerto libre. Restaura sin propietarios ni privilegios originales,
con salida ante errores y transacción única. No toca instalaciones PostgreSQL ni
contenedores existentes. Detiene su propio servidor al terminar; conserva la copia
privada detenida para inspección, por lo que debe protegerse como el respaldo.

Sobre esa copia exige exactamente las ocho migraciones pendientes. Genera otra
base vacía desde el estado histórico registrado de Django, y compara tablas y
columnas públicas, tipos, valores predeterminados, nulabilidad, restricciones,
índices, definiciones de secuencias, triggers y políticas RLS. Una discrepancia
detiene el ensayo para revisión manual; no utiliza --fake ni corrige Neon.

Después aplica las ocho migraciones únicamente a la copia. Compara nuevamente con
el esquema actual generado por Django y comprueba coherencia entre modelos y
migraciones. Calcula cantidades y SHA256 de todos los valores de las columnas
originales de cada tabla pública antes/después, sin imprimir filas. Incluye usuarios,
productos, pedidos, items y los campos de estado/referencia de pago de los pedidos.
El registro django_migrations se excluye porque debe cambiar. migrate incluye
post_migrate: se permiten altas de tipos de contenido y permisos del framework,
verificando por ID que cada fila original conserva sus valores. Las tablas nuevas
y sus restricciones se comparan con el esquema esperado.

Limitaciones: no certifica roles globales, permisos originales, extensiones ni
configuración del proveedor; no copia recursos media ni prueba pasarelas de pago.
La comparación de registros demuestra conservación dentro de la copia restaurada;
no garantiza que Neon no haya cambiado después del snapshot del respaldo. Revisar
collations/locale del servidor real: usar PostgreSQL 18.6 local verifica el motor,
pero la normalización de texto puede depender de la configuración regional.

El manifiesto técnico de éxito queda en .private/rehearsal-*/verification.json.
No modifica el manifiesto original para declarar que cualquier respaldo fue
ensayado: el resultado se vincula por SHA256 al archivo exacto utilizado.
No ejecutar las pruebas de negocio sobre usuarios copiados; las pruebas automatizadas
generales deben continuar en una base sintética separada.

Antes de autorizar migraciones reales:

1. Resolver con el propietario cualquier colisión o discrepancia del esquema;
   comprobar que la auditoría termina correctamente y guardar la lista aplicada.
2. Crear respaldo, comprobar su SHA256 y restaurarlo únicamente en una base nueva
   aislada en PostgreSQL local. No usar --clean contra Neon ni hacer rollback
   destructivo de tablas nuevas con datos.
3. Comparar cantidades de usuarios/productos/pedidos, restricciones y relaciones;
   aplicar las ocho migraciones solo en esa copia y ejecutar las pruebas allí.
   Usar monolith.test_settings y TEST_DATABASE_URL de localhost, nunca DATABASE_URL
   real para las pruebas. No reutilizar la base con datos copiados para las cuentas
   sintéticas del verificador Docker.
4. Solicitar autorización explícita con el resultado del ensayo, respaldo,
   duración y ventana de mantenimiento. Detener escrituras durante la operación
   aprobada y renovar el respaldo si hay cambios desde el ensayo.

Recuperación: conservar la configuración anterior y punto de respaldo; ante un
fallo detener escritores, conservar diagnóstico sin secretos, restaurar en otra
base aislada, validar datos y aplicación, y solicitar autorización antes de
cambiar la conexión real. No ejecutar migraciones inversas ni restaurar encima de
Neon automáticamente. Verificar además la ventana de recuperación del plan Neon.

## Correo existente: diagnóstico antes de reconfigurar

### Construcción de Django: reemplazo bloqueado por el esquema pendiente

El diagnóstico del contenedor principal confirmó que falta el router compartido.
La fuente actual sí incluye usuarios/mailer.py, sus llamadas desde API/vistas,
aliases SMTP y docker/mail_status.py. Dockerfile copia usuarios/, monolith/ y docker/;
no se requieren cambios en Dockerfile o Compose para incluir esas correcciones.
El CMD ejecuta collectstatic y Gunicorn: no aplica migraciones automáticamente.

No obstante, reconstruir todo Django incorpora también las funcionalidades nuevas:
Pedido selecciona checkout_key, checkout_hash y checkout_response, ausentes en el
estado anterior; WishlistItem, PriceNotification, StockMovement, Review, Promotion
y CouponUse requieren sus tablas. No reemplazar el contenedor contra Neon con las
ocho migraciones pendientes aunque la ruta raíz o el healthcheck respondan 200.

Desde el PowerShell habitual, estas operaciones solo inspeccionan/construyen y no
reemplazan el contenedor ni ejecutan migraciones:

```powershell
docker compose -p monolith -f compose.yaml ps django
# Conservar una etiqueta local de la imagen que usa el contenedor actual:
$djangoContainerId = docker compose -p monolith -f compose.yaml ps -q django
if (-not $djangoContainerId) { throw 'No se encontró el contenedor Django activo' }
$djangoImageId = docker inspect --format '{{.Image}}' $djangoContainerId
if ($LASTEXITCODE -ne 0) { throw 'No se pudo identificar la imagen actual' }
docker image tag $djangoImageId monolith-django:before-mail-update
if ($LASTEXITCODE -ne 0) { throw 'No se pudo conservar la etiqueta anterior' }
docker compose -p monolith -f compose.yaml build django
```

La construcción puede reutilizar capas válidas de dependencias: COPY de los fuentes
actualizados invalida las capas de código. No se construyen Node ni React.
La etiqueta latest cambiará, pero el contenedor existente sigue usando su imagen.
El guardado anterior es una etiqueta de imagen, no un respaldo de base ni un ZIP.

**No ejecutar aún** el siguiente reemplazo. Solo después del respaldo real,
restauración y ensayo satisfactorios, autorización explícita y migraciones aprobadas:

```powershell
docker compose -p monolith -f compose.yaml up -d --no-deps --no-build --force-recreate django
Get-Content -Raw docker/mail_status.py | docker compose -p monolith -f compose.yaml exec -T django python -
```

--no-deps evita recrear frontend, Node, Mongo o media-init; se conserva el volumen
media existente. Puede haber un corte breve de las solicitudes hacia Django.
No usar down, down -v, prune ni restart como sustituto de esta actualización.
Un restart no aplica cambios de imagen ni nuevas variables de entorno.

### Gmail SMTP con contraseña de aplicación

1. Usar la cuenta remitente propia y habilitar verificación en dos pasos en Google.
2. Abrir https://myaccount.google.com/apppasswords y crear una contraseña para
   Monolith local. Si ya existe una contraseña válida y conservada, reutilizarla.
   No utilizar la contraseña normal de la cuenta Google.
3. En un editor privado, agregar/actualizar estas claves de .env.docker, sin tocar
   DATABASE_URL, JWT ni los otros secretos:

```dotenv
MONOLITH_EMAIL_PROVIDER=smtp
EMAIL_HOST=smtp.gmail.com
EMAIL_PORT=587
EMAIL_USE_TLS=True
EMAIL_USE_SSL=False
EMAIL_TIMEOUT=30
EMAIL_HOST_USER=REEMPLAZAR_POR_LA_CUENTA_REMITENTE
EMAIL_HOST_PASSWORD=REEMPLAZAR_POR_LA_CONTRASENA_DE_APLICACION
```

Los dos últimos valores son marcadores, nunca credenciales funcionales. Introducir
la contraseña de aplicación completa, sin espacios de presentación. DEFAULT_FROM_EMAIL
es opcional; si se configura, usar la cuenta remitente autenticada. Mantener .env.docker
excluido de Git y no escribir secretos mediante comandos guardados en el historial.
SMTP no requiere las cuatro variables OAuth. Esta selección explícita solo es
reconocida por el código actualizado; configurar SMTP no corrige por sí solo la API
OAuth de una imagen antigua. No recrear esa imagen completa antes de resolver el
bloqueo de esquema descrito arriba.

Google puede no ofrecer contraseñas de aplicación en cuentas organizativas, con
Protección Avanzada o determinadas configuraciones de seguridad. No desactivar esas
protecciones para obtenerlas. Si se cambia la contraseña Google, las de aplicación
pueden quedar revocadas. Referencia: https://support.google.com/accounts/answer/185833?hl=es

Después de la actualización autorizada, mail_status debe indicar SMTP y credenciales
presentes. Eso no prueba autenticación ni entrega: solicitar destinatario y permiso
antes de un único envío real. No usar cuentas reales para disparar recuperación sin
esa autorización.

### Diagnóstico SMTP sin autenticación ni mensajes

SMTPServerDisconnected no identifica por sí solo un error de contraseña. Python
puede envolver un timeout de lectura en esa excepción. La revisión encontró timeout
predeterminado de 10 segundos, no EMAIL_TIMEOUT=5 en los archivos locales. Se elevó
el predeterminado y .env.docker a 30 segundos; falta comprobar el contenedor donde
ocurrió el error. El timeout de Gmail OAuth HTTPS es independiente del SMTP.

Sin reconstruir ni reemplazar el contenedor principal, desde PowerShell:

```powershell
Get-Content -Raw docker/mail_status.py | docker compose -p monolith -f compose.yaml run --rm --no-deps -T --entrypoint python django -
Get-Content -Raw docker/smtp_probe.py | docker compose -p monolith -f compose.yaml run --rm --no-deps -T --entrypoint python django - --timeout 30
```

La sonda solo permite EHLO, STARTTLS y NOOP; no AUTH, MAIL, RCPT ni DATA. No importa
Django, no lee credenciales ni accede a Neon. Prueba un resultado DNS por familia
IPv4/IPv6 y verifica certificados TLS. No imprime direcciones IP, respuestas del
servidor, remitentes ni destinatarios. Cada operación tiene timeout de 30 segundos;
DNS utiliza el resolver del sistema y su timeout propio. Que una familia falle no
implica bloqueo total si la otra completa STARTTLS. No se desactiva IPv6 globalmente.

Interpretación:

- DNS: revisar resolución del contenedor/Docker Desktop.
- TCP: revisar salida al puerto 587, firewall, VPN, antivirus o política de red.
- SMTP_BANNER: TCP abrió, pero no llegó el saludo 220 o el servidor cerró conexión.
- EHLO/STARTTLS: revisar anuncio STARTTLS, intermediarios y validación de certificados.
- ENCRYPTED_EHLO/NOOP: fallo después del cifrado, antes de cualquier autenticación.
- Todo aprobado: conectividad y TLS funcionan; credenciales y entrega siguen sin validar.

Para comparar red del host con Docker, ejecutar la misma sonda desde el host:
`.venv\Scripts\python.exe docker/smtp_probe.py --timeout 30`.
Si host funciona y contenedor no, investigar la ruta/red de Docker y reglas de
seguridad correspondientes; si ambos fallan, revisar la red o políticas del equipo.
No abrir puertos entrantes, exponer Docker por TCP ni desactivar validación TLS.
No declarar un bloqueo específico de Docker sin obtener ambos resultados.

Los siguientes intentos autorizados de envío registran categorías fijas: DNS, red,
timeout, TLS, autenticación, desconexión o rechazo SMTP; solo se muestra código SMTP
numérico cuando existe, nunca el cuerpo de la respuesta. No repetir el envío real
sin una nueva autorización del destinatario y del único mensaje.

El respaldo anterior a Docker conserva dos integraciones: la API usa Gmail OAuth2
HTTPS y las vistas tradicionales usan SMTP Django. El helper OAuth de ese respaldo
es idéntico al encontrado antes de esta revisión. No hay evidencia de que las seis
etapas hayan sustituido SMTP por OAuth. No se dispone del historial remoto completo
para afirmar cuál fue el primer mecanismo usado por el proyecto.

La revisión local no encontró credenciales SMTP ni OAuth en .env, .env.docker,
el entorno del agente ni el .env del respaldo. Eso no demuestra que nunca hubieran
estado configuradas en Render o en contenedores anteriores. No copiar secretos
desde logs ni publicar archivos de entorno para investigar.

Se corrigió la lectura de MONOLITH_EMAIL / MONOLITH_PASSWORD como alias de
EMAIL_HOST_USER / EMAIL_HOST_PASSWORD y se unificó el envío de API y vistas Django.
MONOLITH_EMAIL_PROVIDER acepta auto, smtp o gmail_oauth. Auto conserva OAuth si las
cuatro variables están completas; sin OAuth utiliza SMTP autenticado con TLS/SSL.
OAuth parcial se considera error de configuración y no cambia silenciosamente a
SMTP. Tampoco se cambia de proveedor después de un fallo de autenticación o envío.
Los logs solo indican transporte y tipo de error, sin destinatarios ni respuestas
del proveedor. El backend de memoria de las pruebas nunca se registra como Gmail.

Para inspeccionar las variables efectivas del contenedor existente sin secretos,
sin reconstruir ni conectarse a Neon/Google, ejecutar desde el PowerShell habitual:

```powershell
Get-Content -Raw docker/mail_status.py | docker compose -p monolith -f compose.yaml exec -T django python -
```

El script informa presencia y transporte, nunca valores. Si la imagen es anterior,
informa que falta el router compartido. No ejecutar docker inspect/config completos
ni enviar solicitudes de recuperación contra cuentas reales como diagnóstico.
El estado de configuración no certifica autenticación ni entrega.

Compose carga .env y .env.docker en Django; Node no envía estos correos. Si se
restauran credenciales existentes en .env.docker, deben inyectarse recreando Django
en una ventana autorizada. Un simple restart no actualiza las variables. Mantener
los bloqueos de respaldo/migración antes de arrancar código nuevo contra Neon.

El enlace se genera desde FRONTEND_URL, fijado por el Compose principal en
http://localhost:3000, y las rutas /verify/<token> y /reset-password/<token> coinciden
con React. Se mantiene la firma, caducidad, propósito y uso único de los tokens.
La respuesta genérica de recuperación evita enumerar cuentas y no certifica envío.
Antes de probar entrega real, solicitar destinatario y autorización explícita.

## Gmail OAuth2: solo si es el mecanismo elegido o previamente configurado

Si se dispone de credenciales SMTP válidas, reutilizarlas sin crear OAuth desde
cero. Para OAuth se conservan GMAIL_CLIENT_ID, GMAIL_CLIENT_SECRET,
GMAIL_REFRESH_TOKEN y GMAIL_SENDER_EMAIL. Se leen mediante configuración Django y
entorno; Compose inyecta .env.docker en Django. El diagnóstico anterior encontró
las cuatro ausentes localmente. Los pasos siguientes son opcionales si se usa SMTP.

1. En Google Cloud Console, crear/seleccionar el proyecto del correo de Monolith y
   habilitar Gmail API en APIs y servicios > Biblioteca.
2. Configurar Google Auth Platform: Branding (nombre y contacto), Audience (External
   si es Gmail personal) y agregar la cuenta remitente como usuario de prueba.
3. En Data Access agregar únicamente
   `https://www.googleapis.com/auth/gmail.send`. Es un permiso sensible de envío;
   no requiere leer toda la bandeja ni usar Firebase.
4. En Clients crear cliente OAuth de tipo Web application para este procedimiento
   con el Playground oficial. Agregar exactamente
   `https://developers.google.com/oauthplayground` como URI de redirección autorizada.
5. Abrir https://developers.google.com/oauthplayground/ en el navegador personal.
   En el engranaje seleccionar Google endpoints, Server-side, Offline, Consent
   Screen y **Use your own OAuth credentials**. Introducir allí el client ID y
   client secret propios (solo en Google). Este procedimiento pasa por el servidor
   de Google Playground; no usar servicios de terceros para generar tokens.
6. Autorizar solo gmail.send con la cuenta remitente. En Step 2 intercambiar el
   código por tokens. Copiar el refresh token directamente al editor local;
   no usar el access token temporal como GMAIL_REFRESH_TOKEN.
7. Editar .env.docker localmente y agregar las cuatro claves con sus valores reales,
   sin alterar las otras variables. GMAIL_SENDER_EMAIL debe ser la cuenta que dio
   consentimiento. No enviar valores al chat ni incluirlos en capturas, enlaces,
   logs o historial de comandos. Cerrar Playground y limpiar el portapapeles.
8. El estado External/Testing emite refresh tokens que caducan a los siete días con
   este permiso. Antes del uso estable, revisar publicación/verificación OAuth y
   políticas de Google. No publicar ni cambiar audiencia automáticamente.
9. Autorizar una dirección destinataria para **un solo envío real de prueba**.
   Una vez configurado el proceso real, invocar send_gmail_message con esa dirección;
   confirmar recepción y luego validar los enlaces de verificación y recuperación.
   No hacer registros sintéticos sobre Neon ni recrear el stack real antes de
   resolver las migraciones pendientes y obtener autorización.

No se ha enviado correo real ni se ha modificado configuración de Google. La prueba
aislada usa correo en memoria y valida el flujo sin contactar a Gmail.

## Exclusión de credenciales

.env y .env.* están excluidos de Git (solo .env.example es plantilla permitida).
.private y descargas OAuth se excluyen de Git y del contexto Docker del backend.
No descargar credenciales dentro de frontend o catalog-service: tienen contextos
Docker propios. Esta copia se preparó como un repositorio Git nuevo, sin remoto ni
historial importado. La revisión de archivos locales no certifica el historial de
un repositorio remoto que se configure posteriormente. Antes de publicar, revisar
git ls-files y cualquier historial que se incorpore. La configuración pública del SDK Firebase en
frontend/src/services/firebase.js no es una clave privada de servicio; permanece
sin cambios. Las claves privadas y refresh tokens nunca deben estar en el frontend.

## Fuentes oficiales

- https://docs.docker.com/desktop/setup/install/windows-permission-requirements/
- https://neon.com/docs/manage/backup-pg-dump
- https://developers.google.com/workspace/gmail/api/auth/scopes
- https://developers.google.com/oauthplayground/
- https://developers.google.com/identity/protocols/oauth2#expiration
