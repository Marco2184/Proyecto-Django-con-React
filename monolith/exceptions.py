import logging
import uuid
from django.db import IntegrityError
from rest_framework.views import exception_handler
from rest_framework.response import Response
from .messages import message

logger=logging.getLogger('monolith.api')

def api_exception_handler(exc,context):
    response=exception_handler(exc,context)
    if response is not None:return response
    reference=uuid.uuid4().hex[:12]
    logger.error('API failure reference=%s type=%s view=%s',reference,type(exc).__name__,type(context.get('view')).__name__)
    if isinstance(exc,IntegrityError):
        return Response({'detail':message('Los datos entran en conflicto con un registro existente. Actualiza e inténtalo de nuevo.', 'The data conflicts with an existing record. Refresh and try again.'),'reference':reference},status=409)
    return Response({'detail':message('No se pudo completar la operación. Inténtalo de nuevo.', 'The operation could not be completed. Please try again.'),'reference':reference},status=500)
