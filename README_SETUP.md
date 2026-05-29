# Monolith — React frontend + Django API

## Backend Django

```bash
cd monolith_full
python -m venv venv
venv\Scripts\activate
pip install -r requirements.txt
python manage.py migrate
python manage.py cargar_catalogo --juegos 30
python manage.py runserver
```

Backend/API: `http://localhost:8000/`

## Frontend React

En otra terminal:

```bash
cd monolith_full/frontend
npm install
npm run dev
```

Frontend principal: `http://localhost:3000/`

## Importante

- Usa React como interfaz principal.
- Django queda como API, autenticación, correo, perfil, direcciones, pedidos, carrito y administración.
- El navbar muestra solo **MONOLITH** como marca.
- Los juegos/productos eróticos o adultos están bloqueados por filtros de importación y de API.
