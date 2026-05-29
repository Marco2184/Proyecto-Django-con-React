from django.contrib import admin
from .models import Carrito, ItemCarrito


class ItemInline(admin.TabularInline):
    model = ItemCarrito
    extra = 0


@admin.register(Carrito)
class CarritoAdmin(admin.ModelAdmin):
    list_display = ('usuario', 'cantidad_items', 'total', 'actualizado')
    inlines = [ItemInline]


@admin.register(ItemCarrito)
class ItemCarritoAdmin(admin.ModelAdmin):
    list_display = ('producto', 'carrito', 'cantidad', 'subtotal')
