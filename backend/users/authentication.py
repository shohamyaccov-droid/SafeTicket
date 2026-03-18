"""
Custom JWT Authentication that reads the access token from HttpOnly cookie.
Falls back to Authorization header for backward compatibility.
"""
from rest_framework_simplejwt.authentication import JWTAuthentication
from rest_framework_simplejwt.exceptions import InvalidToken
from django.conf import settings


# Cookie names - must match what login/logout set
ACCESS_TOKEN_COOKIE = getattr(settings, 'JWT_ACCESS_COOKIE_NAME', 'access_token')
REFRESH_TOKEN_COOKIE = getattr(settings, 'JWT_REFRESH_COOKIE_NAME', 'refresh_token')


def _jwt_cookie_kwargs():
    """Cookie options for cross-origin. SameSite=None requires Secure=True (Chrome)."""
    return {
        'httponly': True,
        'samesite': 'None',
        'secure': True,  # Mandatory for SameSite=None
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
    response.delete_cookie(ACCESS_TOKEN_COOKIE, path='/', samesite=kwargs.get('samesite', 'Lax'))
    response.delete_cookie(REFRESH_TOKEN_COOKIE, path='/', samesite=kwargs.get('samesite', 'Lax'))


class JWTCookieAuthentication(JWTAuthentication):
    """
    Authenticate using JWT from HttpOnly cookie (primary) or Authorization header (fallback).
    """
    def authenticate(self, request):
        # Try cookie first
        raw_token = request.COOKIES.get(ACCESS_TOKEN_COOKIE)
        if raw_token:
            try:
                # get_validated_token may expect bytes in some versions
                token_bytes = raw_token.encode('utf-8') if isinstance(raw_token, str) else raw_token
                validated_token = self.get_validated_token(token_bytes)
                if validated_token:
                    return self.get_user(validated_token), validated_token
            except InvalidToken:
                pass
        # Fallback to Authorization header
        return super().authenticate(request)
