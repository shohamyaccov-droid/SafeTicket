/* eslint-disable react/prop-types */
import { Calendar, MapPin } from 'lucide-react';
import { formatEventLocation } from '../utils/eventLocalTime';
import { eventTicketCount } from '../utils/artistEventSupply';
import SellerWaitlistCta from './SellerWaitlistCta';
import './EventCard.css';

const GRADIENTS = [
  'linear-gradient(145deg, #071018 0%, #0f2744 52%, #1d4ed8 130%)',
  'linear-gradient(145deg, #0c0618 0%, #2e1065 48%, #5b21b6 125%)',
  'linear-gradient(145deg, #111318 0%, #1c1917 55%, #44403c 125%)',
  'linear-gradient(145deg, #08111f 0%, #1e1b4b 50%, #312e81 125%)',
  'linear-gradient(145deg, #0a0f1c 0%, #164e63 52%, #0e7490 125%)',
];

function nameGradient(name) {
  let h = 0;
  const s = String(name || '');
  for (let i = 0; i < s.length; i += 1) h = (h * 31 + s.charCodeAt(i)) >>> 0;
  return GRADIENTS[h % GRADIENTS.length];
}

function glowForName(name) {
  const g = nameGradient(name);
  if (g.includes('#5b21b6')) return 'hover:shadow-[0_22px_44px_rgba(91,33,182,0.38)]';
  if (g.includes('#0e7490')) return 'hover:shadow-[0_22px_44px_rgba(14,116,144,0.38)]';
  if (g.includes('#312e81')) return 'hover:shadow-[0_22px_44px_rgba(49,46,129,0.38)]';
  if (g.includes('#44403c')) return 'hover:shadow-[0_22px_44px_rgba(68,64,60,0.32)]';
  return 'hover:shadow-[0_22px_44px_rgba(29,78,216,0.38)]';
}

/**
 * Homepage event tile — physical ticket stub metaphor.
 */
export default function EventCard({
  event,
  formatEventDateHe,
  onNavigate,
  dateVariantCount,
  variant = 'default',
  hasListings,
}) {
  const title = event.name || 'אירוע';
  const artistName = event.artist_detail?.name || event.artist_name || '';
  const venueLine = formatEventLocation(event);
  const listings = hasListings ?? eventTicketCount(event) > 0;
  const multiDates =
    typeof dateVariantCount === 'number' && Number.isFinite(dateVariantCount) && dateVariantCount > 1;
  const isLastMinute = variant === 'lastMinute';
  const dateLabel = multiDates
    ? `${dateVariantCount} תאריכים זמינים`
    : formatEventDateHe?.(event.date) || '';

  let badge = listings ? 'כרטיסים זמינים' : 'ביקוש גבוה';
  if (isLastMinute) badge = 'כרטיסים אחרונים';
  else if (multiDates) badge = `${dateVariantCount} תאריכים`;
  else if (!listings && event.high_demand) badge = 'ביקוש גבוה';

  const badgeTone = listings && !isLastMinute
    ? 'bg-emerald-500'
    : isLastMinute
      ? 'bg-orange-500'
      : 'bg-sky-600';

  return (
    <article
      className={`event-ticket group relative flex h-full cursor-pointer flex-col rounded-2xl bg-white shadow-md transition duration-200 hover:-translate-y-1 hover:shadow-2xl ${glowForName(title)}`}
      tabIndex={0}
      aria-label={title}
      onClick={(e) => {
        if (e.target.closest('a, button')) return;
        onNavigate?.();
      }}
      onKeyDown={(e) => {
        if (e.target.closest('a, button')) return;
        if (e.key === 'Enter' || e.key === ' ') {
          e.preventDefault();
          onNavigate?.();
        }
      }}
    >
      <div
        className="event-ticket__grain relative flex min-h-[148px] flex-col items-center justify-center overflow-hidden rounded-t-2xl px-3 py-5 text-center"
        style={{ background: nameGradient(title) }}
      >
        <span
          className={`absolute right-2 top-2 z-[2] rounded-lg px-2 py-1 text-[0.65rem] font-extrabold text-white shadow-md ${badgeTone}`}
          role="status"
        >
          {badge}
        </span>
        <h3 className="m-0 max-w-full text-[1.15rem] font-extrabold leading-snug text-white [text-shadow:0_2px_12px_rgba(0,0,0,0.45)] line-clamp-3">
          {title}
        </h3>
        {artistName && artistName !== title ? (
          <p className="mt-1 m-0 max-w-full truncate text-[0.78rem] font-semibold text-white/80">
            {artistName}
          </p>
        ) : null}
      </div>

      <div className="event-ticket__stub border-t border-dashed border-slate-300 bg-white px-3 pb-3 pt-3">
        <p className="m-0 flex items-center justify-center gap-1.5 text-[0.78rem] font-semibold text-slate-600">
          <Calendar size={14} strokeWidth={2.25} aria-hidden />
          <span>{dateLabel}</span>
        </p>
        {venueLine ? (
          <p className="mt-1.5 m-0 flex items-center justify-center gap-1.5 text-[0.75rem] text-slate-500">
            <MapPin size={14} strokeWidth={2.25} aria-hidden />
            <span className="line-clamp-2 text-center">{venueLine}</span>
          </p>
        ) : null}
        <span className="mt-3 block w-full rounded-xl bg-[#0045af] py-2.5 text-center text-[0.82rem] font-extrabold text-white shadow-md transition group-hover:bg-[#1d5fd6] group-hover:shadow-lg">
          לרכישה ומכירה
        </span>
        {isLastMinute ? <SellerWaitlistCta event={event} variant="card" /> : null}
      </div>
    </article>
  );
}
