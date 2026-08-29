"""Named throttle scopes for auth, catalog, SMS, checkout, and offers."""
from django.core.exceptions import ImproperlyConfigured
from rest_framework.settings import api_settings
from rest_framework.throttling import SimpleRateThrottle


class FixedScopeThrottle(SimpleRateThrottle):
    """
    DRF ScopedRateThrottle no-ops unless the *view* sets ``throttle_scope``.
    These classes already declare ``.scope``; use that, and read rates from
    live ``api_settings`` so ``override_settings(REST_FRAMEWORK=...)`` works.
    """

    def get_rate(self):
        rates = api_settings.DEFAULT_THROTTLE_RATES or {}
        if not self.scope:
            raise ImproperlyConfigured(f'{self.__class__.__name__} is missing scope')
        try:
            return rates[self.scope]
        except KeyError as exc:
            raise ImproperlyConfigured(
                f'No default throttle rate set for {self.scope!r} scope'
            ) from exc

    def get_cache_key(self, request, view):
        ident = self.get_ident(request)
        if ident is None:
            return None
        return self.cache_format % {'scope': self.scope, 'ident': ident}


class AuthLoginScopedThrottle(FixedScopeThrottle):
    scope = 'auth_login'


class AuthRegisterScopedThrottle(FixedScopeThrottle):
    scope = 'auth_register'


class OffersScopedThrottle(FixedScopeThrottle):
    scope = 'offers'


class OffersMutationScopedThrottle(FixedScopeThrottle):
    """Accept / reject / counter — separate budget from create."""

    scope = 'offers_mutations'


class CheckoutMutationScopedThrottle(FixedScopeThrottle):
    """create_order, guest_checkout, payment_simulation, confirm_order_payment."""

    scope = 'checkout'


class CheckoutReserveScopedThrottle(FixedScopeThrottle):
    """POST /tickets/:id/reserve — cart holds; separate budget from payment."""

    scope = 'checkout_reserve'


class PublicCatalogScopedThrottle(FixedScopeThrottle):
    """Public event / ticket / artist listings — anti-scraping budget."""

    scope = 'public_catalog'


class SmsVerificationScopedThrottle(FixedScopeThrottle):
    """POST /sms/request — aggressive bot / OTP-farming budget."""

    scope = 'sms_verification'
