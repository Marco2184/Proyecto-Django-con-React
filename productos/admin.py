from django.utils.translation import gettext_lazy as lazy
from django.contrib import admin
from django.db import transaction
from django import forms
from django.core.exceptions import PermissionDenied
from .inventory import record_stock
from .models import Producto, Categoria, Plataforma, ImagenProducto


class ProductAdminForm(forms.ModelForm):
    motivo_stock=forms.CharField(label=lazy('Motivo del ajuste de stock'),required=False,max_length=250)
    class Meta:
        model=Producto
        fields='__all__'
    def clean(self):
        data=super().clean()
        if self.instance.pk and 'stock' in self.changed_data and not data.get('motivo_stock','').strip():
            self.add_error('motivo_stock',lazy('Indica el motivo del ajuste de stock.'))
        return data


class ImagenInline(admin.TabularInline):
    model = ImagenProducto
    extra = 2


@admin.register(Producto)
class ProductoAdmin(admin.ModelAdmin):
    form=ProductAdminForm
    readonly_fields = ('ventas',)
    list_display  = ('nombre', 'categoria', 'precio', 'stock', 'ventas', 'disponible')
    list_filter   = ('categoria', 'plataformas')
    search_fields = ('nombre', 'descripcion')
    prepopulated_fields = {'slug': ('nombre',)}
    filter_horizontal   = ('plataformas',)
    inlines = [ImagenInline]

    @transaction.atomic
    def save_model(self, request, obj, form, change):
        if not request.user.email_verificado:raise PermissionDenied
        before=0
        if change:
            current = Producto.objects.select_for_update().get(pk=obj.pk)
            before=current.stock
            obj.ventas = current.ventas
            if 'stock' not in form.changed_data:
                obj.stock = current.stock
        super().save_model(request, obj, form, change)
        record_stock(obj,before,'ajuste' if change else 'inicial',form.cleaned_data.get('motivo_stock') or 'Stock inicial / Initial stock',request.user)

    def disponible(self, obj):
        return obj.disponible
    disponible.boolean = True
    disponible.short_description = lazy("Disponible")


@admin.register(Categoria)
class CategoriaAdmin(admin.ModelAdmin):
    list_display = ('nombre', 'padre')
    prepopulated_fields = {'slug': ('nombre',)}


@admin.register(Plataforma)
class PlataformaAdmin(admin.ModelAdmin):
    list_display = ('nombre', 'slug')
    prepopulated_fields = {'slug': ('nombre',)}

from monolith.admin_i18n import localize_admin_models
localize_admin_models(Producto, Categoria, Plataforma, ImagenProducto)
