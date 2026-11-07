from django.utils.translation import gettext_lazy as translate
from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from django.contrib.auth.forms import UserChangeForm, AdminUserCreationForm
from django import forms
from django.core.exceptions import ValidationError
from django.db import transaction
from .order_service import TRANSITIONS, transition_order
from .models import Usuario, DireccionEnvio, Pedido, PedidoItem, PedidoTimeline


class UsuarioCreationForm(AdminUserCreationForm):
    class Meta(AdminUserCreationForm.Meta):
        model = Usuario
        fields = ('email', 'nombre')


class UsuarioChangeForm(UserChangeForm):
    class Meta(UserChangeForm.Meta):
        model = Usuario
        fields = '__all__'

    def clean(self):
        data = super().clean()
        if self.instance.pk and self.instance.is_staff:
            remains_active = data.get('is_staff', self.instance.is_staff) and data.get('is_active', self.instance.is_active) and data.get('cuenta_activa', self.instance.cuenta_activa)
            if not remains_active and not Usuario.objects.filter(is_staff=True, is_active=True, cuenta_activa=True).exclude(pk=self.instance.pk).exists():
                raise ValidationError(translate('No puedes dejar el sistema sin administradores activos.'))
        return data

@admin.register(Usuario)
class UsuarioAdmin(UserAdmin):
    model = Usuario
    form = UsuarioChangeForm
    add_form = UsuarioCreationForm
    list_display  = ('email','nombre','email_verificado','is_active','fecha_registro')
    list_filter   = ('email_verificado','is_active','is_staff')
    search_fields = ('email','nombre')
    ordering      = ('-fecha_registro',)
    fieldsets = (
        (None,           {'fields':('email','nombre','password')}),
        (translate('Info extra'),   {'fields':('telefono','email_verificado')}),
        (translate('Permisos'),     {'fields':('is_active','cuenta_activa','is_staff','is_superuser','groups','user_permissions')}),
    )
    add_fieldsets = (
        (None, {'fields':('email','nombre','password1','password2')}),
    )

    def get_readonly_fields(self, request, obj=None):
        return () if request.user.is_superuser else ('is_staff', 'is_superuser', 'groups', 'user_permissions')

    def has_change_permission(self, request, obj=None):
        if obj and obj.is_superuser and not request.user.is_superuser:
            return False
        return super().has_change_permission(request, obj)

    @transaction.atomic
    def changeform_view(self, request, object_id=None, form_url='', extra_context=None):
        if request.method == 'POST':
            list(Usuario.objects.select_for_update().filter(is_staff=True).order_by('pk'))
        return super().changeform_view(request, object_id, form_url, extra_context)


@admin.register(DireccionEnvio)
class DireccionEnvioAdmin(admin.ModelAdmin):
    list_display  = ('usuario', 'calle', 'ciudad', 'departamento', 'codigo_postal', 'predeterminada')
    list_filter   = ('departamento', 'predeterminada')
    search_fields = ('usuario__email', 'calle', 'ciudad')


class PedidoAdminForm(forms.ModelForm):
    class Meta:
        model = Pedido
        fields = ('estado', 'motivo_cancelacion')

    def clean_estado(self):
        state = self.cleaned_data['estado']
        current = Pedido.objects.get(pk=self.instance.pk)
        if state != current.estado and state not in TRANSITIONS.get(current.estado, set()):
            raise ValidationError(translate('Transición de pedido no permitida.'))
        if state != current.estado and state in {'procesando', 'enviado', 'entregado'} and current.estado_pago != 'aprobado':
            raise ValidationError(translate('El pago simulado debe estar aprobado.'))
        return state


@admin.register(Pedido)
class PedidoAdmin(admin.ModelAdmin):
    form = PedidoAdminForm
    list_display  = ('numero', 'usuario', 'fecha', 'monto_total', 'estado')
    list_filter   = ('estado', 'fecha')
    search_fields = ('numero', 'usuario__email')
    ordering      = ('-fecha',)

    @transaction.atomic
    def changeform_view(self, request, object_id=None, form_url='', extra_context=None):
        if request.method == 'POST' and object_id and str(object_id).isdigit():
            Pedido.objects.select_for_update().filter(pk=object_id).first()
        return super().changeform_view(request, object_id, form_url, extra_context)

    def has_add_permission(self, request):
        return False

    def has_delete_permission(self, request, obj=None):
        return False

    def get_readonly_fields(self, request, obj=None):
        return [field.name for field in Pedido._meta.fields if field.name not in {'estado', 'motivo_cancelacion'}]

    def save_model(self, request, obj, form, change):
        if not request.user.email_verificado:
            from django.core.exceptions import PermissionDenied
            raise PermissionDenied
        updated = transition_order(obj.pk, obj.estado, reason=obj.motivo_cancelacion,actor=request.user)
        obj.__dict__.update(updated.__dict__)


@admin.register(PedidoItem)
class PedidoItemAdmin(admin.ModelAdmin):
    list_display = ('pedido', 'producto_nombre', 'cantidad', 'precio_unitario', 'subtotal')

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(PedidoTimeline)
class PedidoTimelineAdmin(admin.ModelAdmin):
    list_display = ('pedido', 'estado', 'descripcion', 'creado_en')

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False

from monolith.admin_i18n import localize_admin_models
localize_admin_models(Usuario, DireccionEnvio, Pedido, PedidoItem, PedidoTimeline)
