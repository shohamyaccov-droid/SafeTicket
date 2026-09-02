/* eslint-disable react/prop-types */
import { Link } from 'react-router-dom';
import {
  sellTicketsPathForEvent,
  sellerWaitlistCtaLabel,
  waitlistDemandCount,
} from '../utils/sellEventPrefill';
import './SellerWaitlistCta.css';

/**
 * Seller-facing waitlist demand CTA. Renders nothing when nobody is waiting.
 */
export default function SellerWaitlistCta({ event, variant = 'card' }) {
  const count = waitlistDemandCount(event);
  if (!count) return null;
  return (
    <Link
      to={sellTicketsPathForEvent(event)}
      className={`seller-waitlist-cta seller-waitlist-cta--${variant}`}
      onClick={(e) => e.stopPropagation()}
    >
      {sellerWaitlistCtaLabel(count)}
    </Link>
  );
}
