"""Envío de correos desde la cuenta Gmail autorizada a Monolith.

OAuth2 user refresh token, scope gmail.send; exclusivamente HTTPS.
No requiere SMTP, password de aplicación, ni una sesión iniciada en Render.
"""
import base64
import json
import os
from email.message import EmailMessage
from email.utils import formataddr, parseaddr
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

TOKEN_URL = 'https://oauth2.googleapis.com/token'
SEND_URL = 'https://gmail.googleapis.com/gmail/v1/users/me/messages/send'
TIMEOUT_SECONDS = 15


class GmailSendError(RuntimeError):
    """Fallo de configuración o transporte sin información sensible."""


def _required_env(name):
    value = os.environ.get(name, '').strip()
    if not value:
        raise GmailSendError(f'Falta configuración: {name}')
    return value


def _json_request(url, payload, headers=None):
    data = json.dumps(payload).encode('utf-8')
    request = Request(
        url,
        data=data,
        headers={'Content-Type': 'application/json', **(headers or {})},
        method='POST',
    )
    try:
        with urlopen(request, timeout=TIMEOUT_SECONDS) as response:
            return json.load(response)
    except HTTPError as error:
        # No imprimir el cuerpo: algunas respuestas contienen detalles sensibles.
        raise GmailSendError(f'Gmail API respondió con HTTP {error.code}') from None
    except (URLError, TimeoutError, OSError):
        raise GmailSendError('No hay conexión con Gmail API') from None


def send_gmail_message(*, subject, body, recipient):
    """Solicita access token y envía un MIME por Gmail API.

    El refresh token debe pertenecer a GMAIL_SENDER_EMAIL y haberse
    autorizado con https://www.googleapis.com/auth/gmail.send.
    """
    client_id = _required_env('GMAIL_CLIENT_ID')
    client_secret = _required_env('GMAIL_CLIENT_SECRET')
    refresh_token = _required_env('GMAIL_REFRESH_TOKEN')
    sender = _required_env('GMAIL_SENDER_EMAIL')

    if '\r' in recipient or '\n' in recipient or parseaddr(recipient)[1] != recipient:
        raise GmailSendError('Destinatario inválido')

    token_request = Request(
        TOKEN_URL,
        data=urlencode({
            'client_id': client_id,
            'client_secret': client_secret,
            'refresh_token': refresh_token,
            'grant_type': 'refresh_token',
        }).encode('utf-8'),
        headers={'Content-Type': 'application/x-www-form-urlencoded'},
        method='POST',
    )
    try:
        with urlopen(token_request, timeout=TIMEOUT_SECONDS) as response:
            access_token = json.load(response).get('access_token')
    except HTTPError as error:
        raise GmailSendError(f'OAuth Google respondió con HTTP {error.code}') from None
    except (URLError, TimeoutError, OSError):
        raise GmailSendError('No hay conexión con el servidor OAuth de Google') from None

    if not access_token:
        raise GmailSendError('OAuth Google no devolvió access_token')

    message = EmailMessage()
    message['From'] = formataddr(('Monolith', sender))
    message['To'] = recipient
    message['Subject'] = subject
    message.set_content(body)
    raw = base64.urlsafe_b64encode(message.as_bytes()).decode('ascii')
    response = _json_request(
        SEND_URL,
        {'raw': raw},
        {'Authorization': f'Bearer {access_token}'},
    )
    if not response.get('id'):
        raise GmailSendError('Gmail API no confirmó el envío')
    return response['id']
