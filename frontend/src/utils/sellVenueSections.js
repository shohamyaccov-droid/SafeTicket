import { VENUE_BLOOMFIELD_CONCERT, VENUE_RAMAT_GAN, VENUE_CAESAREA } from './venueMaps';
import { CONCERT_SECTION_NAMES } from './bloomfieldConcertGeometry';
import { isRamatGanVenueEvent, ramatGanSellSectionOptions } from './ramatGanSellSections';
import { isCaesareaVenueEvent, caesareaSellSectionOptions } from './caesareaSellSections';
import {
  isSultansPoolVenueName,
  sultansPoolSellSectionOptions,
  VENUE_SULTANS_POOL,
} from './sultansPoolMap';

const rangeOptions = (start, end) =>
  Array.from({ length: end - start + 1 }, (_, i) => {
    const value = String(start + i);
    return { value, label: `גוש ${value}`, structured: false };
  });

const BLOOMFIELD_SECTION_OPTIONS = [
  ...rangeOptions(201, 209),
  ...rangeOptions(214, 216),
  ...rangeOptions(221, 229),
  ...rangeOptions(234, 236),
  ...rangeOptions(301, 338),
  ...rangeOptions(404, 406),
  ...rangeOptions(419, 431),
];

const BLOOMFIELD_CONCERT_SECTION_OPTIONS = CONCERT_SECTION_NAMES.map((name) => ({
  value: name,
  label: `גוש ${name}`,
  structured: false,
}));

export function isBloomfieldConcertEvent(eventLike) {
  if (!eventLike) return false;
  const venue = String(eventLike.venue || '').trim();
  const category = String(eventLike.category || '').toLowerCase();
  const hay = [
    eventLike.venue_detail?.name,
    eventLike.venue,
    eventLike.name,
  ]
    .filter(Boolean)
    .join(' ');
  return (
    venue === VENUE_BLOOMFIELD_CONCERT
    || (hay.includes('בלומפילד') && category === 'concert')
    || (hay.includes('אייל גולן') && hay.includes('בלומפילד'))
  );
}

export function canonicalVenueName(eventLike) {
  const values = [
    eventLike?.venue_detail?.name,
    eventLike?.venue,
    eventLike?.selectedEvent?.venue_detail?.name,
    eventLike?.selectedEvent?.venue,
  ]
    .filter(Boolean)
    .map((v) => String(v).trim());
  const haystack = values.join(' ');
  if (values.some((v) => v === VENUE_BLOOMFIELD_CONCERT) || isBloomfieldConcertEvent(eventLike)) {
    return VENUE_BLOOMFIELD_CONCERT;
  }
  if (haystack.includes('בלומפילד')) return 'אצטדיון בלומפילד';
  if (haystack.includes('פיס ארנה') || haystack.includes('ארנה ירושלים')) return 'פיס ארנה ירושלים';
  if (haystack.includes('מנורה') || haystack.includes('מבטחים')) return 'היכל מנורה מבטחים';
  if (isCaesareaVenueEvent(eventLike)) return VENUE_CAESAREA;
  if (isRamatGanVenueEvent(eventLike)) return VENUE_RAMAT_GAN;
  if (values.some((v) => isSultansPoolVenueName(v)) || haystack.includes('בריכת הסולטן')) {
    return VENUE_SULTANS_POOL;
  }
  return values[0] || '';
}

/** Same גוש list the sell wizard uses (DB sections are applied by the caller). */
export function generatedSectionOptionsForVenue(venueName) {
  if (venueName === 'היכל מנורה מבטחים') {
    return Array.from({ length: 12 }, (_, i) => {
      const number = i + 1;
      return [
        { value: `${number} תחתון`, label: `גוש ${number} תחתון`, structured: false },
        { value: `${number} עליון`, label: `גוש ${number} עליון`, structured: false },
      ];
    }).flat();
  }
  if (venueName === VENUE_BLOOMFIELD_CONCERT) {
    return BLOOMFIELD_CONCERT_SECTION_OPTIONS;
  }
  if (venueName === 'אצטדיון בלומפילד') {
    return BLOOMFIELD_SECTION_OPTIONS;
  }
  if (venueName === 'פיס ארנה ירושלים') {
    return [...rangeOptions(101, 122), ...rangeOptions(301, 330)];
  }
  if (venueName === VENUE_RAMAT_GAN) {
    return ramatGanSellSectionOptions();
  }
  if (venueName === VENUE_CAESAREA) {
    return caesareaSellSectionOptions();
  }
  if (venueName === VENUE_SULTANS_POOL || isSultansPoolVenueName(venueName)) {
    return sultansPoolSellSectionOptions();
  }
  return [];
}
