from django.utils.translation import gettext_lazy as lazy
from django.apps import AppConfig


class ProductosConfig(AppConfig):
    verbose_name = lazy('Productos')
    name = 'productos'
