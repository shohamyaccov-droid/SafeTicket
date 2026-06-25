/* eslint-disable react/prop-types -- internal map helper */
/**
 * Map price pill — white rounded rect, bold price, designed to stay readable while SVG scales.
 */
export function menoraPriceTagMetrics(width, height, priceLine) {
  const w = Math.max(1, Number(width) || 1);
  const h = Math.max(1, Number(height) || 1);
  const minDim = Math.min(w, h);
  const len = String(priceLine || '').length;
  let fontSize = Math.min(22, Math.max(13, Math.round(minDim * 0.24)));
  if (len > 8) fontSize -= 3;
  else if (len > 6) fontSize -= 2;
  fontSize = Math.max(12, fontSize);

  const maxTagW = Math.max(48, w * 0.9);
  const tagH = Math.min(Math.max(26, fontSize + 12), Math.max(26, h * 0.72));
  let tagW = Math.min(Math.max(54, len * fontSize * 0.7 + 18), maxTagW);
  if (tagW >= maxTagW && len > 0) {
    fontSize = Math.max(12, Math.floor((tagW - 18) / (len * 0.7)));
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
}) {
  const metrics = metricsOverride ?? menoraPriceTagMetrics(width, height, priceLine);
  const { fontSize, tagW, tagH } = metrics;
  const rx = Math.min(12, tagH / 2);

  return (
    <g
      pointerEvents="none"
      className="bloomfield-map-price-tag"
      transform={`translate(${cx + offsetX}, ${cy + offsetY})`}
    >
      <rect
        x={-tagW / 2 + 1.5}
        y={-tagH / 2 + 2.5}
        width={tagW}
        height={tagH}
        rx={rx}
        fill="#0f172a"
        opacity="0.14"
      />
      <rect
        x={-tagW / 2}
        y={-tagH / 2}
        width={tagW}
        height={tagH}
        rx={rx}
        fill="#ffffff"
        stroke="#bfdbfe"
        strokeWidth="1.6"
      />
      <text
        x={0}
        y={0}
        textAnchor="middle"
        dominantBaseline="middle"
        fill="#075985"
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
