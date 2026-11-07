from django.contrib.auth.signals import user_logged_out
from django.dispatch import receiver


@receiver(user_logged_out)
def revoke_on_logout(sender, request, user, **kwargs):
    if user and user.pk:
        from .security import revoke_user
        revoke_user(user)
