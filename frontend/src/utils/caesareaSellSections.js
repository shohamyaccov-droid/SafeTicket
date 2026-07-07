import { VENUE_CAESAREA } from './venueMaps';
import { CAESAREA_SECTION_IDS } from './caesareaGeometry';

/** @param {object|null|undefined} eventLike */
export function isCaesareaVenueEvent(eventLike) {
  if (!eventLike) return false;
  const values = [
    eventLike.venue_detail?.name,
    eventLike.venue,
    eventLike.name,
    eventLike.city,
  ]
    .filter(Boolean)
    .map((v) => String(v).trim());
  if (values.some((v) => v === VENUE_CAESAREA)) return true;
  const hay = values.join(' ');
  return hay.includes('קיסריה') || /caesarea/i.test(hay) || hay.includes('אמפי קיסריה');
}

/** Sell-page dropdown — mirrors CaesareaMap section IDs (19 sections). */
export function caesareaSellSectionOptions() {
  return CAESAREA_SECTION_IDS.map((id) => ({
    value: id,
    label: `גוש ${id}`,
    structured: false,
  }));
}
