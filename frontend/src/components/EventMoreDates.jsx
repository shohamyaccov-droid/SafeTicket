import { Link } from 'react-router-dom';
import { formatEventDatePill } from '../utils/eventLocalTime';
import { eventGroupHref, eventHref } from '../utils/eventSeo';
import { selectRelatedShowDates } from '../utils/eventSchedule';

function isSameEvent(a, b) {
  if (!a || !b) return false;
  if (a.id != null && b.id != null && String(a.id) === String(b.id)) return true;
  const sa = (a.slug || '').trim();
  const sb = (b.slug || '').trim();
  return Boolean(sa && sb && sa === sb);
}

/**
 * Date switcher + event-group CTA under the event hero.
 */
export default function EventMoreDates({ event, relatedEvents }) {
  if (!event) return null;

  const dates = selectRelatedShowDates(relatedEvents, event);
  const groupName = String(event.name || '').trim();
  if (dates.length < 2) return null;

  return (
    <section
      className="mb-4 mt-3 rounded-2xl border border-sky-200 bg-gradient-to-l from-sky-50 via-white to-orange-50 px-3 py-3 shadow-sm sm:px-4"
      dir="rtl"
      aria-labelledby="event-more-dates-heading"
    >
      <div className="mb-2 flex items-center justify-between gap-2">
        <h2
          id="event-more-dates-heading"
          className="m-0 text-sm font-extrabold tracking-wide text-slate-800 sm:text-base"
        >
          תאריכים נוספים
        </h2>
        <span className="text-xs font-semibold text-sky-700">{dates.length} מועדים</span>
      </div>

      <div
        className="-mx-1 flex gap-2 overflow-x-auto px-1 pb-2 [scrollbar-width:thin]"
        aria-label="בחירת תאריך"
      >
        {dates.map((ev) => {
          const label = formatEventDatePill(ev.date);
          if (!label) return null;
          const current = isSameEvent(ev, event);
          const key = ev.id ?? ev.slug ?? ev.date;
          const className = current
            ? 'shrink-0 rounded-full border-2 border-[#0045af] bg-[#0045af] px-3.5 py-2 text-sm font-extrabold text-white shadow-md shadow-sky-200'
            : 'shrink-0 rounded-full border border-slate-200 bg-white px-3.5 py-2 text-sm font-bold text-slate-800 shadow-sm transition hover:border-[#0045af] hover:text-[#0045af]';
          if (current) {
            return (
              <span key={key} className={className} aria-current="date">
                {label}
              </span>
            );
          }
          return (
            <Link key={key} to={eventHref(ev)} className={`${className} no-underline`}>
              {label}
            </Link>
          );
        })}
      </div>

      {groupName ? (
        <Link
          to={eventGroupHref(groupName)}
          className="mt-1 flex w-full items-center justify-center rounded-xl bg-gradient-to-l from-[#0045af] to-[#003894] px-4 py-3 text-center text-sm font-extrabold text-white no-underline shadow-lg shadow-blue-200 transition hover:brightness-110 sm:text-base"
        >
          {`צפה בכל התאריכים של ${groupName}`}
        </Link>
      ) : null}
    </section>
  );
}
