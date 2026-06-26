import os
import django

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "monolith.settings")
django.setup()

from django.contrib.auth.models import User

username = os.environ.get("DJANGO_SUPERUSER_USERNAME", "admin")
email = os.environ.get("DJANGO_SUPERUSER_EMAIL", "admin@monolith.com")
password = os.environ.get("DJANGO_SUPERUSER_PASSWORD", "Admin123456")

user, created = User.objects.get_or_create(username=username)

user.email = email
user.is_staff = True
user.is_superuser = True
user.set_password(password)
user.save()

print(f"Superusuario listo: {username} / {email}")