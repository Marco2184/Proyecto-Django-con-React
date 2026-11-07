from django.utils.translation import gettext_lazy as lazy
from django.contrib import admin
from .models import Carrito, ItemCarrito


class ItemInline(admin.TabularInline):
    model = ItemCarrito
    extra = 0


@admin.register(Carrito)
class CarritoAdmin(admin.ModelAdmin):
    list_display = ('usuario', 'cantidad_items', 'total', 'actualizado')
    inlines = [ItemInline]

    @admin.display(description=lazy('Cantidad'))
    def cantidad_items(self, obj):
        return obj.cantidad_items


@admin.register(ItemCarrito)
class ItemCarritoAdmin(admin.ModelAdmin):
    list_display = ('producto', 'carrito', 'cantidad', 'subtotal')

from monolith.admin_i18n import localize_admin_models
localize_admin_models(Carrito, ItemCarrito)
