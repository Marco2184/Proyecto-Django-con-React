from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from .models import Usuario, DireccionEnvio, Pedido

@admin.register(Usuario)
class UsuarioAdmin(UserAdmin):
    model = Usuario
    list_display  = ('email','nombre','email_verificado','is_active','fecha_registro')
    list_filter   = ('email_verificado','is_active','is_staff')
    search_fields = ('email','nombre')
    ordering      = ('-fecha_registro',)
    fieldsets = (
        (None,           {'fields':('email','nombre','password')}),
        ('Info extra',   {'fields':('telefono','email_verificado','token_verificacion')}),
        ('Permisos',     {'fields':('is_active','is_staff','is_superuser','groups','user_permissions')}),
    )
    add_fieldsets = (
        (None, {'fields':('email','nombre','password1','password2')}),
    )


@admin.register(DireccionEnvio)
class DireccionEnvioAdmin(admin.ModelAdmin):
    list_display  = ('usuario', 'calle', 'ciudad', 'departamento', 'codigo_postal', 'predeterminada')
    list_filter   = ('departamento', 'predeterminada')
    search_fields = ('usuario__email', 'calle', 'ciudad')


@admin.register(Pedido)
class PedidoAdmin(admin.ModelAdmin):
    list_display  = ('numero', 'usuario', 'fecha', 'monto_total', 'estado')
    list_filter   = ('estado', 'fecha')
    search_fields = ('numero', 'usuario__email')
    ordering      = ('-fecha',)
