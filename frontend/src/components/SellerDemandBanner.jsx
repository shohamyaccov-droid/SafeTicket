/* eslint-disable react/prop-types */
import { Eye, TrendingUp } from 'lucide-react';
import { buildSellerDemandLines } from '../utils/sellIntentCopy';
import './SellerDemandBanner.css';

/**
 * Translates the winning Facebook creative
 * ("הכרטיס שלך נמכר פשוט עוד לא העלת אותו") into the upload wizard.
 * Shows live waitlist / view demand when the API provides it.
 */
export default function SellerDemandBanner({ event }) {
  const lines = buildSellerDemandLines(event);
  if (!lines) return null;

  const Icon = lines.tone === 'views' ? Eye : TrendingUp;

  return (
    <aside
      className={`seller-demand-banner seller-demand-banner--${lines.tone} rounded-xl border border-blue-300 border-s-4 border-s-blue-600 bg-blue-100 px-4 py-3.5 shadow-sm`}
      role="status"
      aria-live="polite"
    >
      <div className="flex items-start gap-2.5">
        <Icon className="mt-0.5 h-6 w-6 shrink-0 text-blue-700" aria-hidden="true" />
        <div className="min-w-0">
          <p className="seller-demand-banner__headline m-0 text-lg font-bold leading-snug text-blue-900 sm:text-xl">
            {lines.headline}
          </p>
          <p className="seller-demand-banner__detail mt-1.5 text-sm font-semibold text-blue-700 sm:text-base">
            {lines.detail}
          </p>
        </div>
      </div>
    </aside>
  );
}
