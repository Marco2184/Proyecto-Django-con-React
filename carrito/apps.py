from django.utils.translation import gettext_lazy as lazy
from django.apps import AppConfig


class CarritoConfig(AppConfig):
    verbose_name = lazy('Carritos')
    name = 'carrito'
