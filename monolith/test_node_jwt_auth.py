from django.test import SimpleTestCase, override_settings
from rest_framework.test import APIRequestFactory
from rest_framework.exceptions import AuthenticationFailed
from .node_jwt_auth import NodeJWTAuthentication

class TokenTests(SimpleTestCase):
    @override_settings(JWT_SHARED_SECRET='x'*64)
    def test_invalid_token_rejected(self):
        request=APIRequestFactory().get('/',HTTP_AUTHORIZATION='Bearer invalid')
        with self.assertRaises(AuthenticationFailed): NodeJWTAuthentication().authenticate(request)
    def test_missing_header_ignored(self):
        self.assertIsNone(NodeJWTAuthentication().authenticate(APIRequestFactory().get('/')))
