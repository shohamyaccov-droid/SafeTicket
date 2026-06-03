import { STADIUM_CONFIG } from '../config/ramatGanMapConfig.js';
import { VENUE_RAMAT_GAN } from './venueMaps.js';

/** @param {object|null|undefined} eventLike */
export function isRamatGanVenueEvent(eventLike) {
  if (!eventLike) return false;
  const values = [
    eventLike.venue_detail?.name,
    eventLike.venue,
    eventLike.name,
    eventLike.city,
  ]
    .filter(Boolean)
    .map((v) => String(v).trim());
  if (values.some((v) => v === VENUE_RAMAT_GAN)) return true;
  const hay = values.join(' ');
  return hay.includes('רמת גן') && hay.includes('אצטדיון');
}

/** Sell-page dropdown options — mirrors STADIUM_CONFIG (excludes STAGE). */
export function ramatGanSellSectionOptions() {
  return STADIUM_CONFIG.filter((entry) => entry.dbId !== 'STAGE').map((entry) => ({
    value: entry.dbId,
    label: `גוש ${entry.displayName}`,
    structured: false,
  }));
}
