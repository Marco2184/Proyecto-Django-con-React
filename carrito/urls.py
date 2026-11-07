from django.urls import path
from . import views

urlpatterns = [
    path('',                          views.ver_carrito,         name='ver_carrito'),
    path('agregar/<int:producto_id>/', views.agregar_item,        name='agregar_item'),
    path('actualizar/<int:item_id>/',  views.actualizar_cantidad, name='actualizar_cantidad'),
    path('eliminar/<int:item_id>/',    views.eliminar_item,       name='eliminar_item'),
    path('vaciar/',                    views.vaciar_carrito,      name='vaciar_carrito'),
    path('buscar/',                    views.buscar_en_carrito,   name='buscar_en_carrito'),
]
