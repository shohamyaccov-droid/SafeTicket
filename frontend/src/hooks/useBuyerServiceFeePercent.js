import { useEffect, useState } from 'react';
import { orderAPI } from '../services/api';
import { BUYER_SERVICE_FEE_PERCENT } from '../constants/pricing';

/**
 * Live buyer service-fee % from GET /users/pricing/settings/
 * (same source CheckoutModal uses). Falls back to BUYER_SERVICE_FEE_PERCENT.
 */
export default function useBuyerServiceFeePercent() {
  const [percent, setPercent] = useState(BUYER_SERVICE_FEE_PERCENT);

  useEffect(() => {
    let cancelled = false;
    orderAPI
      .getPricingSettings()
      .then((res) => {
        const raw =
          res?.data?.service_fee_percentage ?? res?.data?.base_buyer_fee_percent;
        const next = parseFloat(raw);
        if (!cancelled && Number.isFinite(next) && next >= 0) {
          setPercent(next);
        }
      })
      .catch(() => {
        /* keep fallback constant */
      });
    return () => {
      cancelled = true;
    };
  }, []);

  return percent;
}
