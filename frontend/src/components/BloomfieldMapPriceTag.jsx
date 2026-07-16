/* eslint-disable react/prop-types -- internal map helper */
/**
 * Map price pill — white/green for available, gray "נתפס" for taken (keeps map populated).
 */
export function menoraPriceTagMetrics(width, height, priceLine) {
  const w = Math.max(1, Number(width) || 1);
  const h = Math.max(1, Number(height) || 1);
  const minDim = Math.min(w, h);
  const len = String(priceLine || '').length;
  let fontSize = Math.min(24, Math.max(15, Math.round(minDim * 0.27)));
  if (len > 8) fontSize -= 3;
  else if (len > 6) fontSize -= 2;
  fontSize = Math.max(14, fontSize);

  const maxTagW = Math.max(58, w * 0.98);
  const tagH = Math.min(Math.max(30, fontSize + 13), Math.max(30, h * 0.78));
  let tagW = Math.min(Math.max(62, len * fontSize * 0.72 + 20), maxTagW);
  if (tagW >= maxTagW && len > 0) {
    fontSize = Math.max(14, Math.floor((tagW - 20) / (len * 0.72)));
  }
  return { fontSize, tagW, tagH };
}

export default function BloomfieldMapPriceTag({
  cx,
  cy,
  priceLine,
  width,
  height,
  metrics: metricsOverride,
  offsetX = 0,
  offsetY = 0,
  variant = 'available',
}) {
  const metrics = metricsOverride ?? menoraPriceTagMetrics(width, height, priceLine);
  const { fontSize, tagW, tagH } = metrics;
  const rx = Math.min(12, tagH / 2);
  const isTaken = variant === 'taken';

  return (
    <g
      pointerEvents="none"
      className={`bloomfield-map-price-tag${isTaken ? ' bloomfield-map-price-tag--taken' : ''}`}
      transform={`translate(${cx + offsetX}, ${cy + offsetY})`}
      style={isTaken ? { cursor: 'not-allowed' } : undefined}
    >
      <rect
        x={-tagW / 2 + 1.5}
        y={-tagH / 2 + 2.5}
        width={tagW}
        height={tagH}
        rx={rx}
        fill="#0f172a"
        opacity={isTaken ? 0.08 : 0.14}
      />
      <rect
        x={-tagW / 2}
        y={-tagH / 2}
        width={tagW}
        height={tagH}
        rx={rx}
        fill={isTaken ? '#e5e7eb' : '#ffffff'}
        stroke={isTaken ? '#9ca3af' : '#bfdbfe'}
        strokeWidth="1.6"
      />
      <text
        x={0}
        y={0}
        textAnchor="middle"
        dominantBaseline="middle"
        fill={isTaken ? '#6b7280' : '#075985'}
        fontSize={fontSize}
        fontWeight="900"
        fontFamily="system-ui, -apple-system, 'Segoe UI', Roboto, sans-serif"
        style={{ direction: 'ltr', unicodeBidi: 'isolate', letterSpacing: '-0.02em' }}
      >
        {priceLine}
      </text>
    </g>
  );
}
