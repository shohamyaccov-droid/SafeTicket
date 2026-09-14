const PAIS_ARENA_MAP_SRC = '/images/venues/pais_arena_map.png';

/**
 * Static Pais Arena (פיס ארנה ירושלים) seating diagram.
 */
export default function PaisArenaMap() {
  return (
    <div className="flex w-full max-w-full items-center justify-center overflow-hidden rounded-xl bg-white p-2 sm:p-3">
      <img
        src={PAIS_ARENA_MAP_SRC}
        alt="מפת ישיבה — פיס ארנה ירושלים"
        className="mx-auto block h-auto w-full max-h-[min(70vh,640px)] object-contain object-center"
        width={1235}
        height={1083}
        decoding="async"
        loading="lazy"
        draggable={false}
      />
    </div>
  );
}
