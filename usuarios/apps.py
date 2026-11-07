from django.utils.translation import gettext_lazy as lazy
from django.apps import AppConfig


class UsuariosConfig(AppConfig):
    verbose_name = lazy('Usuarios')
    name = 'usuarios'

    def ready(self):
        from . import signals  # noqa: F401
