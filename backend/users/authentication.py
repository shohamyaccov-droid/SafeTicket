"""
Custom JWT Authentication that reads the access token from HttpOnly cookie.
Falls back to Authorization header for backward compatibility.
"""
from rest_framework_simplejwt.authentication import JWTAuthentication
from rest_framework_simplejwt.exceptions import InvalidToken
from rest_framework.exceptions import AuthenticationFailed
from django.conf import settings


# Cookie names - must match what login/logout set
ACCESS_TOKEN_COOKIE = getattr(settings, 'JWT_ACCESS_COOKIE_NAME', 'access_token')
REFRESH_TOKEN_COOKIE = getattr(settings, 'JWT_REFRESH_COOKIE_NAME', 'refresh_token')


def _jwt_cookie_kwargs():
    """
    Production: SameSite=None + Secure for cross-origin SPA + HTTPS.
    DEBUG: Lax + non-Secure so HttpOnly JWT cookies are sent on http://127.0.0.1 (RFC 6265 blocks Secure cookies on HTTP).
    """
    if getattr(settings, 'DEBUG', False):
        return {
            'httponly': True,
            'samesite': 'Lax',
            'secure': False,
            'path': '/',
        }
    return {
        'httponly': True,
        'samesite': 'None',
        'secure': True,
        'path': '/',
    }


def set_jwt_cookies(response, access_token, refresh_token):
    """Set access and refresh tokens as HttpOnly cookies on the response."""
    from datetime import timedelta
    kwargs = _jwt_cookie_kwargs()
    # Access token: 60 min (match SIMPLE_JWT ACCESS_TOKEN_LIFETIME)
    response.set_cookie(
        ACCESS_TOKEN_COOKIE,
        str(access_token),
        max_age=60 * 60,
        **kwargs
    )
    # Refresh token: 7 days
    response.set_cookie(
        REFRESH_TOKEN_COOKIE,
        str(refresh_token),
        max_age=7 * 24 * 60 * 60,
        **kwargs
    )


def clear_jwt_cookies(response):
    """Clear JWT cookies (for logout)."""
    kwargs = _jwt_cookie_kwargs()
    ss = kwargs.get('samesite', 'Lax')
    response.delete_cookie(ACCESS_TOKEN_COOKIE, path='/', samesite=ss)
    response.delete_cookie(REFRESH_TOKEN_COOKIE, path='/', samesite=ss)


class JWTCookieAuthentication(JWTAuthentication):
    """
    Authenticate using Authorization header first (Safari ITP / cookie fallback), then HttpOnly cookie.

    Invalid/expired Bearer tokens must not401 public IsAuthenticatedOrReadOnly GETs (e.g. event feed):
    JWTAuthentication raises on bad headers before permission checks; treat as anonymous instead.
    """
    def authenticate(self, request):
        try:
            header_auth = super().authenticate(request)
        except (InvalidToken, AuthenticationFailed):
            header_auth = None
        if header_auth:
            return header_auth
        raw_token = request.COOKIES.get(ACCESS_TOKEN_COOKIE)
        if raw_token:
            try:
                token_bytes = raw_token.encode('utf-8') if isinstance(raw_token, str) else raw_token
                validated_token = self.get_validated_token(token_bytes)
                if validated_token:
                    return self.get_user(validated_token), validated_token
            except InvalidToken:
                pass
        return None
