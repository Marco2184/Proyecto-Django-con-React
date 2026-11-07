from django.urls import path
from . import views

urlpatterns = [
    path('',                        views.catalogo,            name='catalogo'),
    path('buscar/',                  views.buscar_sugerencias,  name='buscar_sugerencias'),
    path('producto/<slug:slug>/',    views.detalle_producto,    name='detalle_producto'),
]
