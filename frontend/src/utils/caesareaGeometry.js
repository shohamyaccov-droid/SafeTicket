/**
 * Caesarea Amphitheater — exact paths from Figma export (Untitled.svg, viewBox 1080×1080).
 * 19 selectable sections + static stage + arena outline.
 */

export const VIEW_W = 1080;
export const VIEW_H = 1080;
export const VIEWBOX = `0 0 ${VIEW_W} ${VIEW_H}`;

export const STAGE = {
  d: 'M686 188.5H601.5V254.5H686V188.5Z',
  labelX: 644,
  labelY: 222,
};

export const ARENA_OUTLINE = {
  d: 'M108 305C148.817 248.594 178.465 220.29 246 177C475.112 167.31 605.331 167.136 841 177C914.994 240.458 946.281 272.598 986 324.5C1005.28 525.99 1004.29 659.233 969 853.5C658.191 1007.97 450.254 1001.3 93.5 853.5C76.4627 642.329 83.9356 502.287 108 305Z',
};

/** Hardcoded Figma paths — order: orchestra, תחתון 1→6 (right→left), אמצע 1→6, עליון 1→6. */
export const CAESAREA_SECTIONS = [
  {
    id: 'אורקסטרה',
    d: 'M479.5 255.5C514.833 255.167 587.1 254.7 593.5 255.5V189.5H479.5V255.5Z',
    labelX: 536,
    labelY: 228,
    displayLabel: 'אורקסטרה',
  },
  {
    id: '1 תחתון',
    d: 'M745 326.5L676 411H827.5L745 326.5Z',
    labelX: 749,
    labelY: 371,
    displayLabel: '1',
  },
  {
    id: '2 תחתון',
    d: 'M665.526 406H603V315H735L665.526 406Z',
    labelX: 669,
    labelY: 361,
    displayLabel: '2',
  },
  {
    id: '3 תחתון',
    d: 'M486.5 316.5H600.5V387H575V350H507V394H486.5V316.5Z',
    labelX: 544,
    labelY: 355,
    displayLabel: '3',
  },
  {
    id: '4 תחתון',
    d: 'M350 310.5H477.5V409H418.5L350 342V310.5Z',
    labelX: 414,
    labelY: 360,
    displayLabel: '4',
  },
  {
    id: '5 תחתון',
    d: 'M323.5 330L250.5 408L417.5 418.5V408L323.5 330Z',
    labelX: 334,
    labelY: 374,
    displayLabel: '5',
  },
  {
    id: '6 תחתון',
    d: 'M119 375.5H181L187.5 345L139.5 303.5L119 324.5V375.5Z',
    labelX: 150,
    labelY: 340,
    displayLabel: '6',
  },
  {
    id: '1 אמצע',
    d: 'M825.5 473.5H673V416.5H825.5V473.5Z',
    labelX: 749,
    labelY: 445,
    displayLabel: '1',
  },
  {
    id: '2 אמצע',
    d: 'M767.809 572L674 480.357L826 474L767.809 572Z',
    labelX: 750,
    labelY: 523,
    displayLabel: '2',
  },
  {
    id: '3 אמצע',
    d: 'M589.5 529.5L614 487.5H648.5V599.5H589.5V529.5Z',
    labelX: 619,
    labelY: 544,
    displayLabel: '3',
  },
  {
    id: '4 אמצע',
    d: 'M543.5 552.5L499 531.5V598.5H583V531.5L543.5 552.5Z',
    labelX: 541,
    labelY: 565,
    displayLabel: '4',
  },
  {
    id: '5 אמצע',
    d: 'M435 601V505.369L493.033 501L495 601H435Z',
    labelX: 465,
    labelY: 553,
    displayLabel: '5',
  },
  {
    id: '6 אמצע',
    d: 'M351 600.5L427.5 506V600.5H351Z',
    labelX: 389,
    labelY: 554,
    displayLabel: '6',
  },
  {
    id: '1 עליון',
    d: 'M754.733 767L798.5 898L956 842L898.386 711M754.733 767L725.5 679.5L866.5 638.5L898.386 711M754.733 767L898.386 711',
    labelX: 841,
    labelY: 768,
    displayLabel: '1',
  },
  {
    id: '2 עליון',
    d: 'M643 776.5V682L713.5 670L744.026 757M643 776.5V920L793.5 898L744.026 757M643 776.5L744.026 757',
    labelX: 718,
    labelY: 782,
    displayLabel: '2',
  },
  {
    id: '3 עליון',
    d: 'M463 774.948V912.351L626 927V774.948M463 774.948V682H626V774.948M463 774.948H626',
    labelX: 545,
    labelY: 805,
    displayLabel: '3',
  },
  {
    id: '4 עליון',
    d: 'M451.5 781.5V682H361.5L333.064 762L286.5 893L451.5 912.5V781.5ZM333.064 762L451.5 781.5',
    labelX: 369,
    labelY: 797,
    displayLabel: '4',
  },
  {
    id: '5 עליון',
    d: 'M321.502 752.5L347 679.5L201.5 655.5L176.283 713.5L121.5 839.5L274 888.5L321.502 752.5ZM176.283 713.5L321.502 752.5',
    labelX: 234,
    labelY: 772,
    displayLabel: '5',
  },
  {
    id: '6 עליון',
    d: 'M103 525L161 497.5L211.5 575L152.5 608.5L103 525Z',
    labelX: 157,
    labelY: 553,
    displayLabel: '6',
  },
];

export const CAESAREA_SECTION_IDS = CAESAREA_SECTIONS.map((s) => s.id);

/** Orchestra + 6 תחתון + 6 אמצע + 6 עליון */
export const CAESAREA_SELECTABLE_COUNT = 19;

if (CAESAREA_SECTIONS.length !== CAESAREA_SELECTABLE_COUNT) {
  throw new Error(
    `Caesarea geometry: expected ${CAESAREA_SELECTABLE_COUNT} sections, got ${CAESAREA_SECTIONS.length}`
  );
}
