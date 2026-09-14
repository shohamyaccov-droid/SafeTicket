const PAIS_ARENA_MAP_SRC = '/images/venues/pais_arena_map.png';

/**
 * Static Pais Arena (פיס ארנה) seating photo for NEXT Jerusalem events.
 * Interactive SVG remains in JerusalemArenaMap for other Pais Arena shows.
 */
export default function PaisArenaMap() {
  return (
    <div className="w-full max-w-full overflow-hidden rounded-xl bg-slate-50">
      <img
        src={PAIS_ARENA_MAP_SRC}
        alt="מפת ישיבה — פיס ארנה ירושלים"
        className="mx-auto block h-auto w-full max-h-[min(70vh,640px)] object-contain object-center"
        width={930}
        height={648}
        decoding="async"
        loading="lazy"
        draggable={false}
      />
    </div>
  );
}
