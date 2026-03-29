"""Named throttle scopes for auth + offer endpoints (see REST_FRAMEWORK DEFAULT_THROTTLE_RATES)."""
from rest_framework.throttling import ScopedRateThrottle


class AuthLoginScopedThrottle(ScopedRateThrottle):
    scope = 'auth_login'


class AuthRegisterScopedThrottle(ScopedRateThrottle):
    scope = 'auth_register'


class OffersScopedThrottle(ScopedRateThrottle):
    scope = 'offers'


class OffersMutationScopedThrottle(ScopedRateThrottle):
    """Accept / reject / counter — separate budget from create."""

    scope = 'offers_mutations'
