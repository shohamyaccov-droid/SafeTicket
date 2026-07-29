/* eslint-disable react/prop-types */
import './LaunchPromoBanner.css';

export default function LaunchPromoBanner({ text = '', isActive = false }) {
  const showBanner = Boolean(isActive && String(text || '').trim());
  if (!showBanner) return null;

  const bannerText = String(text || '').trim();

  return (
    <aside className="launch-promo-banner" role="status" aria-label="הודעת מערכת">
      <span>{bannerText}</span>
    </aside>
  );
}
