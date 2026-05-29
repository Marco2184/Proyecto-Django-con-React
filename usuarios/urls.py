from django.urls import path
from . import views

urlpatterns = [
    path('registro/',                    views.registro,              name='registro'),
    path('login/',                       views.iniciar_sesion,        name='login'),
    path('logout/',                      views.cerrar_sesion,         name='logout'),
    path('verificar/<uuid:token>/',      views.verificar_correo,      name='verificar_correo'),
    path('verificar/reenviar/',          views.reenviar_verificacion, name='reenviar_verificacion'),
    path('recuperar/',                   views.recuperar_password,    name='recuperar_password'),
    path('nueva-password/<uuid:token>/', views.nueva_password,        name='nueva_password'),
    path('dashboard/',                   views.dashboard,             name='dashboard'),
    path('perfil/',                      views.perfil,                name='perfil'),
    path('perfil/editar/',                        views.editar_perfil,      name='editar_perfil'),
    path('perfil/password/',                      views.cambiar_password,   name='cambiar_password'),
    path('perfil/eliminar/',                      views.eliminar_cuenta,    name='eliminar_cuenta'),
    # H008
    path('perfil/direcciones/',                   views.listar_direcciones, name='listar_direcciones'),
    path('perfil/direcciones/agregar/',           views.agregar_direccion,  name='agregar_direccion'),
    path('perfil/direcciones/editar/<int:pk>/',   views.editar_direccion,   name='editar_direccion'),
    path('perfil/direcciones/eliminar/<int:pk>/', views.eliminar_direccion, name='eliminar_direccion'),
    # H010
    path('perfil/pedidos/',                       views.historial_pedidos,  name='historial_pedidos'),
]
