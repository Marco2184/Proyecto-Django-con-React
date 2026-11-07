"""Isolation marker is exposed only by the verification settings module."""
from django.conf import settings
from django.http import JsonResponse
from django.urls import path
from monolith.urls import urlpatterns as application_patterns


def marker(request):
    return JsonResponse({
        'mode': 'monolith-docker-verification',
        'database': settings.DATABASES['default']['NAME'],
        'engine': 'postgresql',
    })


urlpatterns = [path('api/__verification__/', marker)] + application_patterns
