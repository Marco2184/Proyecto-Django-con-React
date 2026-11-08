"""Production routing without a React /admin versus Django /admin collision."""
from django.contrib import admin
from django.http import JsonResponse
from django.urls import path
from django.db import connection, transaction
from django.db.migrations.executor import MigrationExecutor
from .urls import urlpatterns as base_patterns


def health(request):
    return JsonResponse({'status': 'ok'})


def ready(request):
    try:
        with transaction.atomic():
            with connection.cursor() as cursor:
                cursor.execute('SET TRANSACTION READ ONLY')
                cursor.execute("SET LOCAL statement_timeout = '5000ms'")
                cursor.execute('SELECT 1')
            executor = MigrationExecutor(connection)
            if executor.migration_plan(executor.loader.graph.leaf_nodes()):
                return JsonResponse({'status': 'pending_migrations'}, status=503)
    except Exception:
        return JsonResponse({'status': 'unavailable'}, status=503)
    return JsonResponse({'status': 'ready'})


urlpatterns = [
    path('health/', health),
    path('ready/', ready),
    path('django-admin/', admin.site.urls),
] + [pattern for pattern in base_patterns if str(pattern.pattern) != 'admin/']
