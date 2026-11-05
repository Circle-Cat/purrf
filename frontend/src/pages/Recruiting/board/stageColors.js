// Static color classes per stage — every class string below must appear
// verbatim so Tailwind v4's scanner includes it in the generated stylesheet
// (interpolating a variable that only ever resolves to these literals is
// fine; interpolating a dynamically-built class name is not).
const SWATCHES = {
  sky: {
    border: "border-sky-200",
    tint: "bg-sky-50",
    header: "bg-sky-100 text-sky-800",
    count: "bg-sky-200 text-sky-800",
  },
  violet: {
    border: "border-violet-200",
    tint: "bg-violet-50",
    header: "bg-violet-100 text-violet-800",
    count: "bg-violet-200 text-violet-800",
  },
  amber: {
    border: "border-amber-200",
    tint: "bg-amber-50",
    header: "bg-amber-100 text-amber-800",
    count: "bg-amber-200 text-amber-800",
  },
  rose: {
    border: "border-rose-200",
    tint: "bg-rose-50",
    header: "bg-rose-100 text-rose-800",
    count: "bg-rose-200 text-rose-800",
  },
  emerald: {
    border: "border-emerald-200",
    tint: "bg-emerald-50",
    header: "bg-emerald-100 text-emerald-800",
    count: "bg-emerald-200 text-emerald-800",
  },
  slate: {
    border: "border-slate-300",
    tint: "bg-slate-100",
    header: "bg-slate-200 text-slate-700",
    count: "bg-slate-300 text-slate-700",
  },
};

/**
 * Lane color classes per `ApplicationStage` value, matching the Recruiting
 * v2 prototype's swimlane color scheme (docs/superpowers — RecruitingPrototype
 * ScreeningBoardPrototype.jsx). Pipeline stages get a distinct hue each;
 * `hired` reuses the pipeline's terminal-success hue, `rejected` is neutral.
 */
export const STAGE_COLORS = {
  recruiter_screening: SWATCHES.sky,
  behavioral: SWATCHES.violet,
  tech: SWATCHES.amber,
  board_review: SWATCHES.rose,
  offer: SWATCHES.emerald,
  hired: SWATCHES.emerald,
  rejected: SWATCHES.slate,
};

/**
 * The `{ border, tint, header, count }` Tailwind class set for a stage,
 * falling back to the neutral slate swatch for any stage not in the map.
 *
 * @param {string} stage
 * @returns {{border: string, tint: string, header: string, count: string}}
 */
export const getStageColors = (stage) => STAGE_COLORS[stage] ?? SWATCHES.slate;
