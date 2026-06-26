import os
import django

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "monolith.settings")
django.setup()

from django.contrib.auth import get_user_model

Usuario = get_user_model()

email = os.environ.get("DJANGO_SUPERUSER_EMAIL", "admin@monolith.com")
password = os.environ.get("DJANGO_SUPERUSER_PASSWORD")
nombre = os.environ.get("DJANGO_SUPERUSER_NOMBRE", "Administrador Monolith")

if not password:
    raise ValueError("Falta DJANGO_SUPERUSER_PASSWORD en las variables de entorno de Render.")

# Buscar usuario por correo
user = Usuario.objects.filter(email=email).first()

# Si no existe, crearlo con los campos obligatorios de tu modelo
if not user:
    user = Usuario.objects.create_user(
        email=email,
        nombre=nombre,
        password=password
    )

# Asegurar permisos de administrador
user.nombre = nombre
user.email = email
user.is_staff = True
user.is_superuser = True
user.is_active = True
user.set_password(password)
user.save()

print(f"Superusuario listo: {email}")