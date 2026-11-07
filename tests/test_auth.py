import hashlib
import json
import uuid
import jwt
from django.conf import settings
from django.test import TestCase
from rest_framework.test import APIClient
from usuarios.models import Usuario
from usuarios.security import consume_email_token, issue_email_token, rotate_jwt_session


class AuthenticationTests(TestCase):
    def service(self, path, payload):
        body = json.dumps(payload).encode()
        token = jwt.encode({'typ':'service','purpose':path,'body_hash':hashlib.sha256(body).hexdigest()}, settings.JWT_SHARED_SECRET, algorithm='HS256', headers={})
        import time
        claims = jwt.decode(token, settings.JWT_SHARED_SECRET, algorithms=['HS256'])
        claims.update(iat=int(time.time()),exp=int(time.time())+30,iss='monolith-node',aud='monolith-internal')
        token=jwt.encode(claims,settings.JWT_SHARED_SECRET,algorithm='HS256')
        return APIClient().post(path,body,content_type='application/json',HTTP_AUTHORIZATION='Bearer '+token)

    def test_registration_retry_verification_refresh_logout(self):
        payload={'nombre':'Cliente','email':'new@example.invalid','password1':'Secure$Random!941a','password2':'Secure$Random!941a','request_id':str(uuid.uuid4())}
        path='/api/auth/node/register/'
        response=self.service(path,payload)
        self.assertEqual(response.status_code,201,response.data)
        user=Usuario.objects.get(email=payload['email'])
        self.assertFalse(user.email_verificado)
        self.assertIn('sid',response.data['session'])
        self.assertEqual(self.service(path,payload).status_code,200)
        self.assertEqual(Usuario.objects.count(),1)
        claims=response.data['session'];claims['sub']=str(user.pk)
        rotated=rotate_jwt_session(claims)
        self.assertNotEqual(rotated['jti'],claims['jti'])
        token=issue_email_token(user,'verify');consume_email_token(token,'verify')
        user.refresh_from_db();self.assertTrue(user.email_verificado)
        c=APIClient();c.force_authenticate(user)
        self.assertEqual(c.post('/api/auth/logout/').status_code,200)
        with self.assertRaises(Exception):rotate_jwt_session({**rotated,'sub':str(user.pk)})

    def test_unverified_cannot_checkout_and_common_user_cannot_admin(self):
        user=Usuario.objects.create_user('a@example.invalid','User','password')
        c=APIClient();c.force_authenticate(user)
        self.assertEqual(c.post('/api/cart/checkout/',{},format='json').status_code,403)
        self.assertEqual(c.get('/api/admin/dashboard/').status_code,403)
        self.assertEqual(APIClient().post('/api/auth/node/register/',{},format='json').status_code,401)

    def test_case_insensitive_duplicate_registration_rejected(self):
        Usuario.objects.create_user('known@example.invalid','Existing','password')
        response=self.service('/api/auth/node/register/',{'nombre':'New','email':'KNOWN@example.invalid','password1':'Secure$Random!941a','password2':'Secure$Random!941a','request_id':str(uuid.uuid4())})
        self.assertEqual(response.status_code,400)
        self.assertEqual(Usuario.objects.count(),1)

    def test_verification_single_use_and_password_reset_revokes_sessions(self):
        from usuarios.security import create_jwt_session,validate_jwt_session
        from django.contrib.auth import authenticate
        user=Usuario.objects.create_user('reset@example.invalid','Reset','OldPassword!9834')
        session=create_jwt_session(user)
        token=issue_email_token(user,'verify');client=APIClient()
        self.assertEqual(client.post(f'/api/auth/verify/{token}/').status_code,200)
        self.assertEqual(client.post(f'/api/auth/verify/{token}/').status_code,400)
        user.refresh_from_db();self.assertTrue(user.email_verificado)
        token=issue_email_token(user,'reset')
        r=client.post(f'/api/auth/reset-password/{token}/',{'password1':'NewPassword!89347','password2':'NewPassword!89347'},format='json')
        self.assertEqual(r.status_code,200,r.data)
        self.assertIsNone(authenticate(username=user.email,password='OldPassword!9834'))
        self.assertIsNotNone(authenticate(username=user.email,password='NewPassword!89347'))
        user.refresh_from_db()
        with self.assertRaises(Exception):validate_jwt_session(user,session)
