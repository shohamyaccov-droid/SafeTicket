from pathlib import Path

from django.http import HttpResponse

_APPLE_PAY_DOMAIN_ASSOCIATION_FILE = (
    Path(__file__).resolve().parent.parent / '.well-known' / 'apple-developer-merchantid-domain-association'
)


def apple_pay_domain_association(_request):
    """Serve PayMe/Apple Pay merchant domain verification file at /.well-known/..."""
    content = _APPLE_PAY_DOMAIN_ASSOCIATION_FILE.read_text(encoding='utf-8')
    return HttpResponse(content, content_type='text/plain')
