from rest_framework.permissions import BasePermission
from rest_framework.exceptions import PermissionDenied
from .messages import message


class VerifiedEmail(BasePermission):
    def has_permission(self, request, view):
        if not request.user.is_authenticated:
            return False
        if not request.user.email_verificado:
            raise PermissionDenied(message('Verifica tu correo para realizar esta operación.', 'Verify your email to perform this operation.'))
        return True


class VerifiedAdminWrites(BasePermission):
    def has_permission(self,request,view):
        return True if request.method in ('GET','HEAD','OPTIONS') else VerifiedEmail().has_permission(request,view)
