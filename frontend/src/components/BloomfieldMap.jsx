import { useVenueMapPanZoom } from '../hooks/useVenueMapPanZoom';
import './VenueInteractiveMaps.css';

const BLOOMFIELD_MAP_SRC =
  'https://www.maccabi-tlv.co.il/wp-content/uploads/2019/08/bloomfield_map_2019-2.png';

export default function BloomfieldMap() {
  const panZoom = useVenueMapPanZoom();

  return (
    <div className="venue-interactive-map">
      <div className="venue-interactive-map__controls">
        <button type="button" className="venue-interactive-map__zoom-btn" onClick={panZoom.zoomIn} aria-label="התקרבות">
          +
        </button>
        <button type="button" className="venue-interactive-map__zoom-btn" onClick={panZoom.zoomOut} aria-label="התרחקות">
          −
        </button>
      </div>

      <div
        className="venue-interactive-map__viewport"
        onPointerDown={panZoom.onPointerDown}
        onPointerMove={panZoom.onPointerMove}
        onPointerUp={panZoom.onPointerUp}
        onPointerCancel={panZoom.onPointerUp}
        role="application"
        aria-label="מפת בלומפילד — גרירה להזזה"
      >
        <div className="venue-interactive-map__transform" style={panZoom.transformStyle}>
          <img
            className="venue-interactive-map__img"
            src={BLOOMFIELD_MAP_SRC}
            alt="מפת ישיבה — אצטדיון בלומפילד"
            width={1200}
            height={800}
            decoding="async"
            loading="lazy"
            draggable={false}
          />
        </div>
      </div>
    </div>
  );
}
