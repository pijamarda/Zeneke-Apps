from django.http import HttpResponse

HEALTH_CHECK_PATH = '/healthz'


class HealthCheckMiddleware:
    """Answer /healthz before the HTTPS redirect and ALLOWED_HOSTS check.

    Must be first in MIDDLEWARE. Touches neither the database nor sessions.
    """

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        if request.path == HEALTH_CHECK_PATH:
            return HttpResponse('ok', content_type='text/plain')
        return self.get_response(request)
