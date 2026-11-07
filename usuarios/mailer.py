"""Shared mail transport; no fallback on delivery/authentication errors."""
import logging
import smtplib
import socket
import ssl

from django.conf import settings
from django.core.mail import send_mail

from .gmail_mail import GmailSendError, send_gmail_message

logger = logging.getLogger(__name__)
OAUTH_KEYS = ('GMAIL_CLIENT_ID', 'GMAIL_CLIENT_SECRET', 'GMAIL_REFRESH_TOKEN', 'GMAIL_SENDER_EMAIL')


def smtp_error_category(error):
    """Fixed diagnostic labels; never include SMTP response bodies or addresses."""
    if isinstance(error, smtplib.SMTPAuthenticationError):
        return 'authentication'
    # smtplib.getreply wraps socket timeouts in SMTPServerDisconnected.
    if isinstance(error, TimeoutError) or isinstance(error.__context__, TimeoutError):
        return 'timeout'
    if isinstance(error, socket.gaierror):
        return 'dns'
    if isinstance(error, ssl.SSLError):
        return 'tls'
    if isinstance(error, smtplib.SMTPServerDisconnected):
        return 'disconnected'
    if isinstance(error, smtplib.SMTPRecipientsRefused):
        return 'recipients_rejected'
    if isinstance(error, smtplib.SMTPSenderRefused):
        return 'sender_rejected'
    if isinstance(error, smtplib.SMTPResponseException):
        return 'server_rejected'
    if isinstance(error, OSError):
        return 'network'
    return 'configuration_or_transport'


def mail_provider():
    # Test-only backend never contacts a real provider.
    if settings.EMAIL_BACKEND == 'django.core.mail.backends.locmem.EmailBackend':
        return 'memory'
    provider = settings.MONOLITH_EMAIL_PROVIDER.strip().lower()
    if provider not in ('auto', 'smtp', 'gmail_oauth'):
        raise GmailSendError('Proveedor de correo no válido')
    if provider == 'auto':
        oauth = [bool(getattr(settings, key, '').strip()) for key in OAUTH_KEYS]
        if any(oauth):
            if not all(oauth):
                raise GmailSendError('Configuración OAuth incompleta')
            return 'gmail_oauth'
        provider = 'smtp'
    if provider == 'smtp':
        if not settings.EMAIL_HOST_USER or not settings.EMAIL_HOST_PASSWORD:
            raise GmailSendError('Faltan credenciales SMTP')
        if bool(settings.EMAIL_USE_TLS) == bool(settings.EMAIL_USE_SSL):
            raise GmailSendError('SMTP requiere TLS o SSL, exclusivamente uno')
    return provider


def send_account_mail(subject, body, recipient):
    """Return actual transport acceptance, never expose recipients/tokens/errors."""
    provider = 'configuration'
    try:
        provider = mail_provider()
        if provider == 'gmail_oauth':
            send_gmail_message(subject=subject, body=body, recipient=recipient)
        else:
            accepted = send_mail(subject, body, settings.DEFAULT_FROM_EMAIL,
                                 [recipient], fail_silently=False)
            if accepted != 1:
                raise GmailSendError('El transporte no aceptó el mensaje')
        logger.info('Account email accepted transport=%s', provider)
        return True
    except Exception as error:
        # Exception messages may contain addresses or provider responses.
        code = getattr(error, 'smtp_code', None)
        logger.warning('Account email failed transport=%s error=%s category=%s smtp_code=%s',
                       provider, type(error).__name__, smtp_error_category(error),
                       code if isinstance(code, int) else 'none')
        return False
