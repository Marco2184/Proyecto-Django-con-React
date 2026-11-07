"""Explicit API language wins over a potentially stale language cookie."""
from django.utils import translation
from django.utils.cache import patch_vary_headers


class ApiLanguageMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        if request.path.startswith('/api/') and request.headers.get('Accept-Language'):
            language = translation.get_language_from_request(request, check_path=False)
            header = request.headers['Accept-Language'].split(',')[0].split(';')[0].split('-')[0].lower()
            if header in ('en', 'es'):
                language = header
            translation.activate(language)
            request.LANGUAGE_CODE = language
        response = self.get_response(request)
        response['Content-Language'] = translation.get_language() or 'es'
        patch_vary_headers(response, ('Accept-Language', 'Cookie'))
        return response
