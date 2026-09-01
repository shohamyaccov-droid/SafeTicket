/* eslint-disable react/prop-types */
/**
 * Sultan's Pool (בריכת הסולטן) seating map.
 * Zone paths are the Figma export (frame 375×288); Hebrew labels match the designed overlay.
 */
import { currencySymbol, formatListingAmountForCurrency } from '../utils/priceFormat';
import { MAP_TAKEN_BUBBLE_LABEL } from '../utils/mapSectionStatus';
import { normalizeSultansPoolZoneId, SULTANS_POOL_ZONE_LABELS } from '../utils/sultansPoolMap';

const VIEWBOX = '0 0 375 288';
const STROKE_ZONE = '#c9a227';
const LABEL_FILL = '#faf6ee';
const LABEL_TEXT = '#3f2f1e';
const STAGE_FILL = '#2c2c2c';
const STAGE_STROKE = '#4b4b4b';

const CLICKABLE_ZONES = [
  {
    id: 'orchestra',
    d: 'M0.5 92V0.5H135V92H0.5Z',
    x: 119.5,
    y: 28,
    labelX: 68,
    labelY: 46,
    fontSize: 13,
    badge: { x: 28, y: 34, w: 80, h: 24 },
    pinX: 67.5,
    pinY: 10,
  },
  {
    id: 'gush-5',
    d: 'M47 0.5H0.5V93.5L21.5 115.5L53 87L47 0.5Z',
    x: 62,
    y: 28,
    labelX: 26,
    labelY: 52,
    fontSize: 12,
    badge: { x: 4, y: 40, w: 44, h: 24 },
    pinX: 22,
    pinY: 16,
  },
  {
    id: 'gush-1',
    d: 'M5.01279 4.55196L0.512794 89.052L33.0128 115.552L48.0128 94.552L43.5128 0.551956L5.01279 4.55196Z',
    x: 260,
    y: 28,
    labelX: 26,
    labelY: 52,
    fontSize: 12,
    badge: { x: 4, y: 40, w: 44, h: 24 },
    pinX: 24,
    pinY: 16,
  },
  {
    id: 'accessible',
    d: 'M0.5 14V0.5H57.5V14H0.5Z',
    x: 158.5,
    y: 123,
    labelX: 29,
    labelY: 8,
    fontSize: 6.5,
    badge: null,
    pinX: 29,
    pinY: 4,
  },
  {
    id: 'gush-4',
    d: 'M0.5 40.6305L36 6.13047L56.5 32.6305L91.5 0.63047L126 23.1305L136.5 147.13H65.5L0.5 78.1305V40.6305Z',
    x: 4,
    y: 132,
    labelX: 68,
    labelY: 78,
    fontSize: 13,
    badge: { x: 40, y: 66, w: 56, h: 24 },
    pinX: 68,
    pinY: 22,
  },
  {
    id: 'gush-3',
    d: 'M0.545464 0.5H92.5455L75.5455 121H11.0455L0.545464 0.5Z',
    x: 140.5,
    y: 158,
    labelX: 47,
    labelY: 52,
    fontSize: 13,
    badge: { x: 19, y: 40, w: 56, h: 24 },
    pinX: 46,
    pinY: 16,
  },
  {
    id: 'gush-2',
    d: 'M10.5426 25.0713L43.5426 0.668575L75.5426 35.3205L95.0426 6.52523L130.543 35.3205V75.829L63.0426 143.669L0.542622 139.764L10.5426 25.0713Z',
    x: 239,
    y: 135,
    labelX: 66,
    labelY: 78,
    fontSize: 13,
    badge: { x: 38, y: 66, w: 56, h: 24 },
    pinX: 65,
    pinY: 22,
  },
];

function zoneStatusKeys(zone) {
  const label = SULTANS_POOL_ZONE_LABELS[zone.id];
  return [zone.id, label, label ? `גוש ${label}` : null, zone.id === 'orchestra' ? 'גוש אורקסטרה' : null].filter(
    Boolean,
  );
}

function listingForZone(zone, sectionMapStatus, lowestPrices) {
  for (const key of zoneStatusKeys(zone)) {
    if (sectionMapStatus?.[key]) return sectionMapStatus[key];
  }
  for (const key of zoneStatusKeys(zone)) {
    const price = lowestPrices?.[key];
    if (price != null && price !== '') return { status: 'available', minPrice: Number(price) };
  }
  return null;
}

function ZonePricePin({ x, y, label, taken }) {
  const fill = taken ? '#e5e7eb' : '#ffffff';
  const stroke = taken ? '#9ca3af' : '#e5e7eb';
  const text = taken ? '#6b7280' : '#1f2937';
  return (
    <g transform={`translate(${x} ${y})`} pointerEvents="none" data-testid="sultans-price-pin" filter="url(#sultans-pin-shadow)">
      <rect x="-34" y="-11" width="68" height="22" rx="4" fill={fill} stroke={stroke} strokeWidth="1" />
      <text
        x="0"
        y="0"
        textAnchor="middle"
        dominantBaseline="middle"
        fill={text}
        fontSize="12"
        fontWeight="700"
        style={{ fontFamily: 'inherit' }}
      >
        {label}
      </text>
      <polygon points="0,11 -5.5,16.5 5.5,16.5" fill={fill} stroke={stroke} strokeWidth="1" />
      <rect x="-6" y="9.5" width="12" height="3" fill={fill} />
    </g>
  );
}

function ZoneLabel({ zone, isActive }) {
  const label = SULTANS_POOL_ZONE_LABELS[zone.id] || zone.id;
  const twoLine = zone.id === 'accessible';

  return (
    <g pointerEvents="none">
      {zone.badge ? (
        <rect
          x={zone.badge.x}
          y={zone.badge.y}
          width={zone.badge.w}
          height={zone.badge.h}
          rx="6"
          fill={isActive ? '#fff8dc' : LABEL_FILL}
          stroke={STROKE_ZONE}
          strokeWidth="0.75"
        />
      ) : null}
      {twoLine ? (
        <text
          x={zone.labelX}
          y={zone.labelY}
          textAnchor="middle"
          fill={LABEL_TEXT}
          fontSize={zone.fontSize}
          fontWeight="700"
          style={{ fontFamily: 'inherit' }}
        >
          <tspan x={zone.labelX} dy="-0.35em">
            מושבים
          </tspan>
          <tspan x={zone.labelX} dy="1.15em">
            נגישים
          </tspan>
        </text>
      ) : (
        <text
          x={zone.labelX}
          y={zone.labelY}
          textAnchor="middle"
          dominantBaseline="middle"
          fill={LABEL_TEXT}
          fontSize={zone.fontSize}
          fontWeight="700"
          style={{ fontFamily: 'inherit' }}
        >
          {label}
        </text>
      )}
    </g>
  );
}

export default function SultansPoolMap({
  activeZone = null,
  onZoneClick,
  lowestPrices = {},
  sectionMapStatus = {},
  currencyIso = 'ILS',
  pinPrice = null,
}) {
  const activeId = normalizeSultansPoolZoneId(activeZone);

  const handleActivate = (zoneId) => {
    if (typeof onZoneClick === 'function') onZoneClick(zoneId);
  };

  const pinForZone = (zone) => {
    const isActive = activeId === zone.id;
    const meta = listingForZone(zone, sectionMapStatus, lowestPrices);
    const isTaken = meta?.status === 'taken' && !isActive;
    const rawPrice =
      isActive && pinPrice != null && pinPrice !== ''
        ? Number(pinPrice)
        : meta?.status === 'available'
          ? meta.minPrice
          : lowestPrices[zone.id];
    const price = rawPrice != null && rawPrice !== '' ? Number(rawPrice) : null;
    const hasPrice = !isTaken && price != null && !Number.isNaN(price);
    if (!hasPrice && !isTaken) return null;
    return {
      taken: Boolean(isTaken),
      label: isTaken
        ? MAP_TAKEN_BUBBLE_LABEL
        : `${currencySymbol(currencyIso)}${formatListingAmountForCurrency(price, currencyIso)}`,
    };
  };

  return (
    <div className="relative w-full overflow-visible rounded-xl bg-slate-100">
      <svg
        viewBox={VIEWBOX}
        className="block h-auto w-full overflow-visible"
        preserveAspectRatio="xMidYMid meet"
        role="img"
        aria-label="מפת ישיבה בריכת הסולטן"
      >
        <defs>
          <filter id="sultans-zone-glow" x="-12%" y="-12%" width="124%" height="124%">
            <feDropShadow dx="0" dy="1" stdDeviation="1.2" floodColor="#c9a227" floodOpacity="0.4" />
          </filter>
          <filter id="sultans-pin-shadow" x="-40%" y="-50%" width="180%" height="200%">
            <feDropShadow dx="0" dy="1.5" stdDeviation="1.4" floodColor="#0f172a" floodOpacity="0.22" />
          </filter>
        </defs>

        {/* Stage / במה — visual only, not a ticket zone */}
        <g id="stage" className="pointer-events-none" transform="translate(157 6)">
          <path
            d="M0.5 0.5H60.5V18H0.5V0.5Z"
            fill={STAGE_FILL}
            stroke={STAGE_STROKE}
            strokeWidth="1"
          />
          <text
            x="30.5"
            y="10.5"
            textAnchor="middle"
            dominantBaseline="middle"
            fill="#f5f5f5"
            fontSize="9"
            fontWeight="700"
            letterSpacing="0.6"
            style={{ fontFamily: 'inherit' }}
          >
            במה
          </text>
        </g>

        {CLICKABLE_ZONES.map((zone) => {
          const isActive = activeId === zone.id;
          return (
            <g
              key={zone.id}
              id={zone.id}
              transform={`translate(${zone.x} ${zone.y})`}
              className="group cursor-pointer outline-none"
              role="button"
              tabIndex={0}
              aria-label={SULTANS_POOL_ZONE_LABELS[zone.id] || zone.id}
              aria-pressed={isActive}
              filter="url(#sultans-zone-glow)"
              onClick={() => handleActivate(zone.id)}
              onKeyDown={(e) => {
                if (e.key === 'Enter' || e.key === ' ') {
                  e.preventDefault();
                  handleActivate(zone.id);
                }
              }}
            >
              <path
                d={zone.d}
                fill={isActive ? '#22c55e' : '#f4efe4'}
                stroke={isActive ? '#16a34a' : STROKE_ZONE}
                strokeWidth={isActive ? 2.4 : 1.6}
                strokeLinejoin="round"
                data-active={isActive ? 'true' : 'false'}
                className={
                  isActive
                    ? 'fill-green-500 transition-colors duration-200'
                    : 'fill-[#f4efe4] transition-colors duration-200 group-hover:fill-[#ebe3d0]'
                }
              />
              <ZoneLabel zone={zone} isActive={isActive} />
            </g>
          );
        })}

        {CLICKABLE_ZONES.map((zone) => {
          const pin = pinForZone(zone);
          if (!pin) return null;
          return (
            <g key={`pin-${zone.id}`} transform={`translate(${zone.x} ${zone.y})`}>
              <ZonePricePin x={zone.pinX} y={zone.pinY} label={pin.label} taken={pin.taken} />
            </g>
          );
        })}
      </svg>
    </div>
  );
}
