"""Transport tests use mocks or memory; never contact Google or real accounts."""
import ast
import os
from pathlib import Path
from unittest.mock import patch

from django.core import mail
from django.test import SimpleTestCase, TestCase, override_settings
from rest_framework.test import APIClient

from usuarios.gmail_mail import GmailSendError, _required_env
from usuarios.mailer import mail_provider, send_account_mail
from usuarios.models import Usuario


@override_settings(EMAIL_BACKEND='django.core.mail.backends.smtp.EmailBackend',
                   MONOLITH_EMAIL_PROVIDER='auto', EMAIL_USE_TLS=True, EMAIL_USE_SSL=False,
                   EMAIL_HOST_USER='', EMAIL_HOST_PASSWORD='', GMAIL_CLIENT_ID='',
                   GMAIL_CLIENT_SECRET='', GMAIL_REFRESH_TOKEN='', GMAIL_SENDER_EMAIL='')
class MailTransportTests(SimpleTestCase):
    @override_settings(EMAIL_HOST_USER='sender@example.invalid', EMAIL_HOST_PASSWORD='synthetic-only')
    @patch('usuarios.mailer.send_gmail_message')
    @patch('usuarios.mailer.send_mail', return_value=1)
    def test_reuses_smtp_credentials(self, smtp, oauth):
        self.assertEqual(mail_provider(), 'smtp')
        self.assertTrue(send_account_mail('Subject', 'Body', 'recipient@example.invalid'))
        smtp.assert_called_once()
        oauth.assert_not_called()

    @override_settings(GMAIL_CLIENT_ID='synthetic-id', GMAIL_CLIENT_SECRET='synthetic-secret',
                       GMAIL_REFRESH_TOKEN='synthetic-refresh', GMAIL_SENDER_EMAIL='sender@example.invalid')
    @patch('usuarios.mailer.send_mail')
    @patch('usuarios.mailer.send_gmail_message')
    def test_keeps_complete_oauth(self, oauth, smtp):
        self.assertEqual(mail_provider(), 'gmail_oauth')
        self.assertTrue(send_account_mail('Subject', 'Body', 'recipient@example.invalid'))
        oauth.assert_called_once()
        smtp.assert_not_called()

    @override_settings(GMAIL_CLIENT_ID='partial', EMAIL_HOST_USER='sender@example.invalid',
                       EMAIL_HOST_PASSWORD='synthetic-only')
    @patch('usuarios.mailer.send_mail')
    def test_partial_oauth_does_not_silently_switch(self, smtp):
        self.assertFalse(send_account_mail('Subject', 'Body', 'recipient@example.invalid'))
        smtp.assert_not_called()

    @override_settings(EMAIL_HOST_USER='sender@example.invalid', EMAIL_HOST_PASSWORD='synthetic-only')
    @patch('usuarios.mailer.send_gmail_message')
    @patch('usuarios.mailer.send_mail', side_effect=RuntimeError('private-provider-detail'))
    def test_failure_is_not_success_and_logs_are_sanitized(self, smtp, oauth):
        with self.assertLogs('usuarios.mailer', level='WARNING') as logs:
            self.assertFalse(send_account_mail('Subject', 'Body', 'recipient@example.invalid'))
        self.assertNotIn('private-provider-detail', '\n'.join(logs.output))
        self.assertNotIn('recipient@example.invalid', '\n'.join(logs.output))
        oauth.assert_not_called()

    @override_settings(EMAIL_HOST_USER='sender@example.invalid', EMAIL_HOST_PASSWORD='synthetic-only',
                       EMAIL_USE_TLS=False, EMAIL_USE_SSL=False)
    def test_no_unencrypted_smtp(self):
        with self.assertRaises(GmailSendError):
            mail_provider()

    @override_settings(GMAIL_CLIENT_ID='configured-through-django')
    def test_oauth_reads_django_configuration(self):
        with patch.dict(os.environ, {}, clear=True):
            self.assertEqual(_required_env('GMAIL_CLIENT_ID'), 'configured-through-django')

    @override_settings(EMAIL_BACKEND='django.core.mail.backends.locmem.EmailBackend')
    def test_memory_transport_is_not_reported_as_gmail(self):
        self.assertEqual(mail_provider(), 'memory')

    @override_settings(EMAIL_HOST_USER='sender@example.invalid', EMAIL_HOST_PASSWORD='synthetic-only')
    @patch('usuarios.mailer.send_mail', return_value=0)
    def test_zero_messages_is_failure(self, smtp):
        self.assertFalse(send_account_mail('Subject', 'Body', 'recipient@example.invalid'))

    def test_legacy_aliases_and_canonical_priority(self):
        source = Path(__file__).resolve().parents[1] / 'monolith' / 'settings.py'
        nodes = [node for node in ast.parse(source.read_text(encoding='utf-8')).body
                 if isinstance(node, ast.Assign) and any(isinstance(t, ast.Name) and
                 t.id in ('EMAIL_HOST_USER', 'EMAIL_HOST_PASSWORD') for t in node.targets)]
        for canonical in (False, True):
            values = {'MONOLITH_EMAIL': 'legacy@example.invalid', 'MONOLITH_PASSWORD': 'synthetic-legacy'}
            if canonical:
                values.update(EMAIL_HOST_USER='canonical@example.invalid', EMAIL_HOST_PASSWORD='synthetic-canonical')
            namespace = {'config': lambda key, default='': values.get(key, default)}
            exec(compile(ast.Module(body=nodes, type_ignores=[]), str(source), 'exec'), namespace)
            self.assertEqual(namespace['EMAIL_HOST_USER'], values['EMAIL_HOST_USER' if canonical else 'MONOLITH_EMAIL'])
            self.assertEqual(namespace['EMAIL_HOST_PASSWORD'], values['EMAIL_HOST_PASSWORD' if canonical else 'MONOLITH_PASSWORD'])


class AccountMailLinksTests(TestCase):
    def test_registration_generates_valid_verification_link_in_memory(self):
        from usuarios.api import FRONTEND_URL
        from usuarios.security import email_token_user
        response = APIClient().post('/api/auth/register/', {
            'nombre': 'Mail fixture', 'email': 'verify-mail@example.invalid',
            'password1': 'SyntheticPassword!58', 'password2': 'SyntheticPassword!58',
        }, format='json')
        self.assertEqual(response.status_code, 201)
        self.assertEqual(len(mail.outbox), 1)
        prefix = FRONTEND_URL + '/verify/'
        link = next(line for line in mail.outbox[0].body.splitlines() if line.startswith(prefix))
        user, _ = email_token_user(link[len(prefix):], 'verify')
        self.assertFalse(user.email_verificado)
        self.assertEqual(mail.outbox[0].to, [user.email])

    def test_recovery_generates_current_frontend_link_in_memory(self):
        from usuarios.api import FRONTEND_URL
        from usuarios.security import email_token_user
        user = Usuario.objects.create_user('mail-fixture@example.invalid', 'Fixture', 'SyntheticPassword!58')
        response = APIClient().post('/api/auth/forgot-password/', {'email': user.email}, format='json')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(mail.outbox), 1)
        prefix = FRONTEND_URL + '/reset-password/'
        link = next(line for line in mail.outbox[0].body.splitlines() if line.startswith(prefix))
        recovered, _ = email_token_user(link[len(prefix):], 'reset')
        self.assertEqual(recovered.pk, user.pk)
        self.assertEqual(mail.outbox[0].to, [user.email])

    def test_missing_account_keeps_generic_response_without_mail(self):
        response = APIClient().post('/api/auth/forgot-password/', {'email': 'absent@example.invalid'}, format='json')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(mail.outbox), 0)
