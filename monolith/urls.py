from django.contrib import admin
from django.urls import path, include
from django.http import JsonResponse
from django.conf import settings
from django.conf.urls.static import static
from rest_framework.routers import DefaultRouter
from productos.api import ProductoViewSet, PlataformaViewSet, CategoriaViewSet
from usuarios import api as usuarios_api
from usuarios import admin_api
from carrito import api as carrito_api

router = DefaultRouter()
router.register(r'api/productos', ProductoViewSet, basename='api-producto')
router.register(r'api/plataformas', PlataformaViewSet, basename='api-plataforma')
router.register(r'api/categorias', CategoriaViewSet, basename='api-categoria')


def api_root(request):
    return JsonResponse({
        'name': 'Monolith API',
        'frontend': settings.FRONTEND_URL,
        'endpoints': {
            'productos': '/api/productos/',
            'auth': '/api/auth/login/',
            'perfil': '/api/auth/me/',
            'carrito': '/api/cart/',
        }
    })

urlpatterns = [
    path('', api_root),
    path('i18n/', include('django.conf.urls.i18n')),
    path('admin/', admin.site.urls),

    # API Auth / Perfil / Traducción
    path('api/auth/register/', usuarios_api.register),
    path('api/auth/firebase-register/', usuarios_api.firebase_register), 
    path('api/auth/firebase-login/', usuarios_api.firebase_login), 
    path('api/auth/firebase-sync-email/', usuarios_api.firebase_sync_email),
    path('api/auth/firebase-delete-account/', usuarios_api.firebase_delete_account),
    path('api/auth/login/', usuarios_api.login_api),
    path('api/auth/logout/', usuarios_api.logout_api),
    path('api/auth/me/', usuarios_api.me),
    path('api/auth/verify/<uuid:token>/', usuarios_api.verify_email),
    path('api/auth/resend-verification/', usuarios_api.resend_verification),
    path('api/auth/forgot-password/', usuarios_api.forgot_password),
    path('api/auth/reset-password/<uuid:token>/', usuarios_api.reset_password),
    path('api/auth/change-password/', usuarios_api.change_password),
    path('api/auth/delete-account/', usuarios_api.delete_account),
    path('api/profile/addresses/', usuarios_api.addresses),
    path('api/profile/addresses/<int:pk>/', usuarios_api.address_detail),
    path('api/profile/orders/', usuarios_api.orders),
    path('api/profile/orders/<int:pk>/', usuarios_api.order_detail),
    path('api/profile/orders/<int:pk>/cancel/', usuarios_api.cancel_order),
    path('api/profile/orders/<int:pk>/receipt/', usuarios_api.order_receipt),
    path('api/i18n/set-language/', usuarios_api.set_language),

    # API Administrador
    path('api/admin/dashboard/', admin_api.admin_dashboard),
    path('api/admin/products/', admin_api.admin_products),
    path('api/admin/products/<int:pk>/', admin_api.admin_product_detail),
    path('api/admin/catalog-options/', admin_api.admin_catalog_options),
    path('api/admin/orders/', admin_api.admin_orders),
    path('api/admin/orders/<int:pk>/', admin_api.admin_order_detail),
    path('api/admin/users/', admin_api.admin_users),

    # API Carrito
    path('api/cart/', carrito_api.cart_detail),
    path('api/cart/add/', carrito_api.cart_add),
    path('api/cart/items/<int:item_id>/', carrito_api.cart_item),
    path('api/cart/clear/', carrito_api.cart_clear),
    path('api/cart/aplicar-cupon/', carrito_api.cart_apply_coupon),
    path('api/cart/quitar-cupon/', carrito_api.cart_remove_coupon),
    path('api/cart/checkout/', carrito_api.cart_checkout),

    # Rutas antiguas conservadas como backend legacy/template, sin borrar tu Django previo.
    path('', include('usuarios.urls')),
    path('catalogo/', include('productos.urls')),
    path('carrito/', include('carrito.urls')),
] + router.urls + static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
