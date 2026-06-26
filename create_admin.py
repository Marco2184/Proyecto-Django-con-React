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

user = Usuario.objects.filter(email=email).first()

if not user:
    user = Usuario.objects.create_user(
        email=email,
        nombre=nombre,
        password=password,
    )
    print(f"Superusuario creado: {email}")
else:
    print(f"Superusuario encontrado: {email}")

user.nombre = nombre
user.email = email
user.is_active = True
user.is_staff = True
user.is_superuser = True

# Mantén esta línea mientras necesitas recuperar/reactivar la cuenta.
# Luego puedes quitarla si no quieres que Render restablezca la contraseña en cada deploy.
user.set_password(password)

user.save()

print(f"Superusuario activo y con permisos verificados: {email}")
