/* eslint-disable react/prop-types -- internal map helper */
/**
 * Menora-style price pill — white rounded rect, bold price centered inside section.
 */
export function menoraPriceTagMetrics(width, height, priceLine) {
  const w = Math.max(1, Number(width) || 1);
  const h = Math.max(1, Number(height) || 1);
  const minDim = Math.min(w, h);
  let fontSize = Math.min(16, Math.max(10, Math.round(minDim * 0.17)));
  const len = String(priceLine || '').length;
  if (len > 8) fontSize -= 2;
  else if (len > 6) fontSize -= 1;
  fontSize = Math.max(9, fontSize);
  const tagH = Math.min(Math.max(18, fontSize + 10), h - 4);
  let tagW = Math.min(Math.max(42, len * fontSize * 0.58), w - 4);
  if (tagW > w - 4) {
    tagW = w - 4;
    fontSize = Math.max(9, Math.floor((tagW / Math.max(len, 1)) * 1.35));
  }
  return { fontSize, tagW, tagH };
}

export default function BloomfieldMapPriceTag({ cx, cy, priceLine, width, height, metrics: metricsOverride }) {
  const metrics = metricsOverride ?? menoraPriceTagMetrics(width, height, priceLine);
  const { fontSize, tagW, tagH } = metrics;

  return (
    <g
      pointerEvents="none"
      className="bloomfield-map-price-tag"
      transform={`translate(${cx}, ${cy})`}
    >
      <rect
        x={-tagW / 2}
        y={-tagH / 2}
        width={tagW}
        height={tagH}
        rx="4"
        fill="#ffffff"
        stroke="#e5e7eb"
        strokeWidth="1"
      />
      <text
        x={0}
        y={0}
        textAnchor="middle"
        dominantBaseline="middle"
        fill="#1f2937"
        fontSize={fontSize}
        fontWeight="700"
        fontFamily="system-ui, -apple-system, 'Segoe UI', Roboto, sans-serif"
        style={{ direction: 'ltr', unicodeBidi: 'isolate' }}
      >
        {priceLine}
      </text>
    </g>
  );
}
