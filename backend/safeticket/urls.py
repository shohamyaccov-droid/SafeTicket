"""
URL configuration for safeticket project.

SPA index serves Vite build from collectstatic. For /event/<slug|id> routes we inject
title/meta/JSON-LD into the initial HTML so Googlebot and social crawlers see SEO
without waiting on client-side React rendering.
"""
from pathlib import Path

from django.contrib import admin
from django.http import FileResponse, Http404, HttpResponse, JsonResponse
from django.urls import path, include, re_path
from django.conf import settings
from django.conf.urls.static import static

from safeticket.apple_pay_views import apple_pay_domain_association
from users.views import subscribe_ticket_alert, secret_run_seed_dummy_tickets


def health_check(_request):
    """Lightweight GET for uptime monitors and SPA keep-alive (Render cold-start mitigation)."""
    return JsonResponse({'status': 'ok'})


def robots_txt(_request):
    from users.seo import frontend_origin

    origin = frontend_origin()
    body = f'User-agent: *\nAllow: /\nSitemap: {origin}/sitemap.xml\n'
    return HttpResponse(body, content_type='text/plain; charset=utf-8')


def sitemap_xml(_request):
    from users.models import Event
    from users.seo import event_canonical_url, frontend_origin

    origin = frontend_origin()
    lines = [
        '<?xml version="1.0" encoding="UTF-8"?>',
        '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">',
        f'  <url><loc>{origin}/</loc><changefreq>daily</changefreq></url>',
    ]
    qs = (
        Event.objects.exclude(status='בוטל')
        .only('id', 'slug')
        .order_by('-id')[:5000]
    )
    for event in qs:
        loc = event_canonical_url(event)
        lines.append(f'  <url><loc>{loc}</loc><changefreq>daily</changefreq></url>')
    lines.append('</urlset>')
    return HttpResponse('\n'.join(lines), content_type='application/xml; charset=utf-8')


def _load_spa_index_html() -> str:
    index = Path(settings.STATIC_ROOT) / 'index.html'
    if not index.is_file():
        raise Http404('index.html missing — run build_render.sh then collectstatic.')
    return index.read_text(encoding='utf-8')


def spa_index_view(request):
    """
    React SPA (Vite build copied by collectstatic). Without this, /login and /sell return 404 on the API host
    even though /static/index.html exists — breaks browser flows that use https://safeticket-api.onrender.com/...
    Event paths get server-injected Schema.org Event JSON-LD + meta for crawler-visible first HTML.
    """
    path = (request.path or '/').strip('/')
    html = None
    if path.startswith('event/'):
        identifier = path.split('/', 1)[1].split('/')[0].strip()
        if identifier:
            try:
                from users.seo import build_event_seo_payload, inject_seo_into_html, resolve_event_by_identifier

                event = resolve_event_by_identifier(identifier)
                seo = build_event_seo_payload(event, request=request)
                html = inject_seo_into_html(_load_spa_index_html(), seo)
            except Exception:
                html = None
    if html is None:
        # Fast path: stream file when no injection
        index = Path(settings.STATIC_ROOT) / 'index.html'
        if not index.is_file():
            raise Http404('index.html missing — run build_render.sh then collectstatic.')
        return FileResponse(index.open('rb'), content_type='text/html; charset=utf-8')
    return HttpResponse(html, content_type='text/html; charset=utf-8')


urlpatterns = [
    path(
        '.well-known/apple-developer-merchantid-domain-association',
        apple_pay_domain_association,
        name='apple_pay_domain_association',
    ),
    path('robots.txt', robots_txt, name='robots_txt'),
    path('sitemap.xml', sitemap_xml, name='sitemap_xml'),
    path('admin/', admin.site.urls),
    path('api-auth/', include('rest_framework.urls')),
    path('api/health/', health_check, name='health_check'),
    path('api/alerts/subscribe/', subscribe_ticket_alert, name='subscribe_ticket_alert'),
    path('api/secret-run-seed-9988/', secret_run_seed_dummy_tickets, name='secret_run_seed_dummy_tickets'),
    path('api/payments/', include('users.payme_urls')),
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
    re_path(r'^(?!api/|admin/|static/|assets/|\.well-known/).+$', spa_index_view),
]
