import os
import django

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "monolith.settings")
django.setup()

from django.contrib.auth import get_user_model

User = get_user_model()

username = os.environ.get("DJANGO_SUPERUSER_USERNAME", "admin")
email = os.environ.get("DJANGO_SUPERUSER_EMAIL", "admin@monolith.com")
password = os.environ.get("DJANGO_SUPERUSER_PASSWORD")

if not password:
    raise ValueError("Falta DJANGO_SUPERUSER_PASSWORD en las variables de entorno de Render.")

# Tu modelo personalizado probablemente usa email como identificador.
# Primero intenta buscar por email.
user = User.objects.filter(email=email).first()

# Si no existe, intenta buscar por username si el modelo tiene ese campo.
if not user and hasattr(User, "username"):
    user = User.objects.filter(username=username).first()

# Si no existe, lo crea.
if not user:
    try:
        user = User.objects.create_user(
            email=email,
            password=password,
            username=username
        )
    except TypeError:
        user = User.objects.create_user(
            email=email,
            password=password
        )

# Actualiza permisos admin.
if hasattr(user, "username"):
    user.username = username

user.email = email
user.is_staff = True
user.is_superuser = True
user.is_active = True
user.set_password(password)
user.save()

print(f"Superusuario listo: {email}")