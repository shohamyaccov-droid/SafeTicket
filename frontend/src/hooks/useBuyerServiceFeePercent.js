import { useEffect, useState } from 'react';
import {
  formatBuyerFeePercent,
  getCachedBuyerFeePercent,
  getCachedPricingSettings,
  loadPricingSettings,
  subscribePricingSettings,
} from '../services/pricingSettings';

/**
 * Live buyer service-fee % from GlobalFeeSettings
 * (GET /users/pricing/settings/). Shared cache across the app.
 */
export default function useBuyerServiceFeePercent() {
  const [percent, setPercent] = useState(() => getCachedBuyerFeePercent());

  useEffect(() => {
    const unsub = subscribePricingSettings((next) => {
      setPercent(next.serviceFeePercent);
    });
    loadPricingSettings().catch(() => {
      /* keep fallback from constants / last good cache */
    });

    const refresh = () => {
      loadPricingSettings({ force: true }).catch(() => {});
    };
    const onVisibility = () => {
      if (document.visibilityState === 'visible') refresh();
    };
    window.addEventListener('focus', refresh);
    document.addEventListener('visibilitychange', onVisibility);

    return () => {
      unsub();
      window.removeEventListener('focus', refresh);
      document.removeEventListener('visibilitychange', onVisibility);
    };
  }, []);

  return Number(formatBuyerFeePercent(percent));
}

/** Full fee split for checkout / coupon UI. */
export function usePricingSettings() {
  const [settings, setSettings] = useState(() => getCachedPricingSettings());

  useEffect(() => {
    const unsub = subscribePricingSettings(setSettings);
    loadPricingSettings().catch(() => {});
    return unsub;
  }, []);

  return settings;
}
