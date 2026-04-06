"""
URL configuration for safeticket project.

The `urlpatterns` list routes requests to views. For more information please see:
https://docs.djangoproject.com/en/4.2/topics/http/urls/
"""
from pathlib import Path

from django.contrib import admin
from django.http import FileResponse, Http404, JsonResponse
from django.urls import path, include, re_path
from django.conf import settings
from django.conf.urls.static import static


def health_check(_request):
    """Lightweight GET for uptime monitors and SPA keep-alive (Render cold-start mitigation)."""
    return JsonResponse({'status': 'ok'})


def spa_index_view(request):
    """
    React SPA (Vite build copied by collectstatic). Without this, /login and /sell return 404 on the API host
    even though /static/index.html exists — breaks browser flows that use https://safeticket-api.onrender.com/...
    """
    index = Path(settings.STATIC_ROOT) / 'index.html'
    if not index.is_file():
        raise Http404('index.html missing — run build_render.sh then collectstatic.')
    return FileResponse(index.open('rb'), content_type='text/html; charset=utf-8')


urlpatterns = [
    path('admin/', admin.site.urls),
    path('api-auth/', include('rest_framework.urls')),
    path('api/health/', health_check, name='health_check'),
    path('api/users/', include('users.urls')),
]

# Dev: serve static from STATIC_ROOT. Media only from local disk (not Cloudinary).
if settings.DEBUG:
    urlpatterns += static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)
    if not getattr(settings, 'USE_CLOUDINARY', False):
        urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)

# Client-side routes: same origin as API (build_render.sh → collectstatic).
# Vite emits /assets/*.js|css at repo root of collectstatic — must not be caught by SPA (would return HTML).
urlpatterns += [
    path('', spa_index_view),
    re_path(r'^(?!api/|admin/|static/|assets/).+$', spa_index_view),
]
