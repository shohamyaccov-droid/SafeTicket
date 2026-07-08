/**
 * Pick the single event that should display the "most tickets" badge.
 * When multiple events tie for max supply, the earliest upcoming date wins.
 *
 * @param {Array<{ id: string|number, tickets_count?: number, date?: string }>} events
 * @returns {string|number|null}
 */
export function pickMostSupplyEventId(events) {
  if (!Array.isArray(events) || events.length === 0) return null;

  const max = Math.max(...events.map((ev) => Number(ev?.tickets_count) || 0));
  if (max <= 0) return null;

  const tied = events.filter((ev) => (Number(ev?.tickets_count) || 0) === max);
  if (tied.length === 1) return tied[0].id ?? null;

  const earliest = [...tied].sort((a, b) => new Date(a.date) - new Date(b.date))[0];
  return earliest?.id ?? null;
}
