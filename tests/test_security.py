from unittest.mock import patch
from django.test import TestCase,override_settings
from rest_framework.test import APIClient
from monolith.exceptions import api_exception_handler
from django.db import IntegrityError
from usuarios.models import Usuario
from productos.models import Producto

class SecurityTests(TestCase):
    def test_unverified_firebase_cannot_link_existing_django_account(self):
        u=Usuario.objects.create_user('owner@example.invalid','Owner','password')
        with patch('usuarios.api._init_firebase_if_configured',return_value=True),patch('usuarios.api.firebase_auth.verify_id_token',return_value={'email':u.email,'email_verified':False}):
            r=APIClient().post('/api/auth/firebase-login/',{},format='json',HTTP_AUTHORIZATION='Firebase invalid')
        self.assertEqual(r.status_code,401)
        u.refresh_from_db();self.assertFalse(u.email_verificado)
    def test_error_handler_never_exposes_database_or_secret(self):
        r=api_exception_handler(IntegrityError('secret-password in database URL'),{'view':None})
        self.assertEqual(r.status_code,409);self.assertNotIn('secret-password',str(r.data))
        r=api_exception_handler(RuntimeError('private stack'),{'view':None})
        self.assertEqual(r.status_code,500);self.assertNotIn('private stack',str(r.data))
    def test_bilingual_coupon_errors_and_all_admin_endpoints_protected(self):
        u=Usuario.objects.create_user('buyer@example.invalid','Buyer','password',email_verificado=True)
        p=Producto.objects.create(nombre='Game',precio=100,stock=1)
        c=APIClient();c.force_authenticate(u)
        for endpoint in ['dashboard','products','orders','users','inventory','promotions','reviews']:
            self.assertEqual(c.get(f'/api/admin/{endpoint}/').status_code,403)
        c.post('/api/cart/add/',{'producto_id':p.pk,'cantidad':1},format='json')
        r=c.post('/api/cart/aplicar-cupon/',{'codigo':'UNKNOWN'},format='json',HTTP_ACCEPT_LANGUAGE='en')
        self.assertEqual(r.status_code,400);self.assertIn('Unknown coupon',str(r.data))
