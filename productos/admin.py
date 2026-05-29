from django.contrib import admin
from .models import Producto, Categoria, Plataforma, ImagenProducto


class ImagenInline(admin.TabularInline):
    model = ImagenProducto
    extra = 2


@admin.register(Producto)
class ProductoAdmin(admin.ModelAdmin):
    list_display  = ('nombre', 'categoria', 'precio', 'stock', 'ventas', 'disponible')
    list_filter   = ('categoria', 'plataformas')
    search_fields = ('nombre', 'descripcion')
    prepopulated_fields = {'slug': ('nombre',)}
    filter_horizontal   = ('plataformas',)
    inlines = [ImagenInline]

    def disponible(self, obj):
        return obj.disponible
    disponible.boolean = True


@admin.register(Categoria)
class CategoriaAdmin(admin.ModelAdmin):
    list_display = ('nombre', 'padre')
    prepopulated_fields = {'slug': ('nombre',)}


@admin.register(Plataforma)
class PlataformaAdmin(admin.ModelAdmin):
    list_display = ('nombre', 'slug')
    prepopulated_fields = {'slug': ('nombre',)}
