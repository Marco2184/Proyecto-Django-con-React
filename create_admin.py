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

# IMPORTANTE:
# Tu login valida ambas banderas.
user.is_active = True
user.cuenta_activa = True

# Permisos de administrador.
user.is_staff = True
user.is_superuser = True

# Para que no bloquee por verificación interna de Django.
user.email_verificado = True

# Mantén esto mientras estás recuperando la cuenta.
user.set_password(password)

user.save()

print(f"Superusuario reactivado completamente: {email}")
print(f"is_active={user.is_active}, cuenta_activa={user.cuenta_activa}, is_staff={user.is_staff}, is_superuser={user.is_superuser}")