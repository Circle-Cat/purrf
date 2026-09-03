import { Badge } from "@/components/ui/badge";

const CHIP = {
  active: {
    label: "Active",
    className: "border-emerald-300 bg-emerald-50 text-emerald-800",
  },
  blocked: {
    label: "Blocked",
    className: "border-rose-300 bg-rose-50 text-rose-800",
  },
  deactivated: {
    label: "Deactivated",
    className: "border-slate-300 bg-slate-100 text-slate-700",
  },
  requested: {
    label: "Block requested",
    className: "border-amber-300 bg-amber-50 text-amber-900",
  },
};

/**
 * StateChips
 *
 * The status cell. Stacks rather than truncates, because a row carrying two
 * states at once is a real case the operator must not miss — blocked and
 * deactivated are orthogonal flags, not steps on one scale.
 *
 * @param {{states: string[]}} props
 * @returns {JSX.Element}
 */
const StateChips = ({ states }) => (
  <div className="flex flex-col items-start gap-1">
    {states.map((state) => (
      <Badge key={state} variant="outline" className={CHIP[state].className}>
        {CHIP[state].label}
      </Badge>
    ))}
  </div>
);

export default StateChips;
