"""
URL configuration for safeticket project.

SPA index serves Vite build from collectstatic. For /event/<slug|id>, /artist/<slug|id>,
and marketing routes (/ , /how-it-works, /faq) we inject title/meta/JSON-LD and crawler HTML
into the initial document so Googlebot and AI crawlers see SEO without waiting on React.
"""
from pathlib import Path

from django.contrib import admin
from django.http import FileResponse, Http404, HttpResponse, HttpResponsePermanentRedirect, JsonResponse
from django.urls import path, include, re_path
from django.conf import settings
from django.conf.urls.static import static

from safeticket.apple_pay_views import apple_pay_domain_association
from users.views import subscribe_ticket_alert, secret_run_seed_dummy_tickets


def health_check(_request):
    """Lightweight GET for uptime monitors and SPA keep-alive (Render cold-start mitigation)."""
    return JsonResponse({'status': 'ok'})


def _cached_text_response(body: str, content_type: str, cache_control: str) -> HttpResponse:
    response = HttpResponse(body, content_type=content_type)
    response['Cache-Control'] = cache_control
    return response


def robots_txt(_request):
    from users.seo import frontend_origin

    origin = frontend_origin()
    body = f'User-agent: *\nAllow: /\nSitemap: {origin}/sitemap.xml\n'
    return _cached_text_response(body, 'text/plain; charset=utf-8', 'public, max-age=3600')


def sitemap_xml(_request):
    from users.seo import cached_sitemap_xml

    return _cached_text_response(
        cached_sitemap_xml(),
        'application/xml; charset=utf-8',
        'public, max-age=300, stale-while-revalidate=3600',
    )


def spa_index_view(request):
    """
    React SPA (Vite build copied by collectstatic). Event, artist, and marketing paths get
    server-injected Schema.org JSON-LD, meta, and static HTML inside #root.
    """
    from users.seo import (
        build_artist_seo_payload,
        build_event_seo_payload,
        get_static_page_seo,
        inject_seo_into_html,
        load_spa_index_html,
        resolve_artist_by_identifier,
        resolve_event_by_identifier,
        event_legacy_redirect_path,
    )

    raw = (request.path or '/').strip()
    path = raw.strip('/')
    html = None
    cache_control = 'public, max-age=60, stale-while-revalidate=300'
    if path.startswith('event/'):
        identifier = path.split('/', 1)[1].split('/')[0].strip()
        if identifier:
            try:
                event = resolve_event_by_identifier(identifier)
                redirect_to = event_legacy_redirect_path(identifier, event)
                if redirect_to:
                    return HttpResponsePermanentRedirect(redirect_to)
                seo = build_event_seo_payload(event, request=request)
                html = inject_seo_into_html(load_spa_index_html(), seo)
                cache_control = 'public, max-age=60, stale-while-revalidate=300'
            except Exception:
                html = None
    elif path.startswith('artist/'):
        identifier = path.split('/', 1)[1].split('/')[0].strip()
        if identifier:
            try:
                artist = resolve_artist_by_identifier(identifier)
                seo = build_artist_seo_payload(artist, request=request)
                html = inject_seo_into_html(load_spa_index_html(), seo)
                cache_control = 'public, max-age=60, stale-while-revalidate=300'
            except Exception:
                html = None
    else:
        route = '/' if not path else f'/{path}'
        try:
            seo = get_static_page_seo(route)
            if seo:
                html = inject_seo_into_html(load_spa_index_html(), seo)
                cache_control = 'public, max-age=300, stale-while-revalidate=3600'
        except Exception:
            html = None
    if html is None:
        index = Path(settings.STATIC_ROOT) / 'index.html'
        if not index.is_file():
            raise Http404('index.html missing — run build_render.sh then collectstatic.')
        response = FileResponse(index.open('rb'), content_type='text/html; charset=utf-8')
        response['Cache-Control'] = cache_control
        return response
    return _cached_text_response(html, 'text/html; charset=utf-8', cache_control)


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
