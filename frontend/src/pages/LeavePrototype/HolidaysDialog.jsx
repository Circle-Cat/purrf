import { Badge } from "@/components/ui/badge";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";

/**
 * HolidaysDialog
 *
 * The company holiday calendar, read-only.
 *
 * Holidays are stored one row per date, so a multi-day break arrives here as
 * several rows; they are grouped into segments before display, or a five-day
 * break reads as five identical lines. Exchangeability belongs to the break as
 * a whole, so a segment carries one flag.
 *
 * @param {object} props
 * @param {boolean} props.open
 * @param {(open: boolean) => void} props.onOpenChange
 * @param {Array<object>} props.segments - grouped holidays, upcoming first
 * @returns {JSX.Element}
 */
const HolidaysDialog = ({ open, onOpenChange, segments }) => (
  <Dialog open={open} onOpenChange={onOpenChange}>
    <DialogContent className="sm:max-w-lg max-h-[80vh] overflow-y-auto">
      <DialogHeader>
        <DialogTitle>Company holidays</DialogTitle>
        <DialogDescription>
          You do not request these — the office is closed and nothing is
          deducted. A break marked exchangeable can be worked in trade for 8h of
          paid leave a day; you choose how many of its days to work.
        </DialogDescription>
      </DialogHeader>

      {segments.length === 0 ? (
        <p className="py-6 text-center text-sm text-slate-400">
          No holidays left this year.
        </p>
      ) : (
        <ul className="divide-y divide-slate-100">
          {segments.map((s) => (
            <li
              key={`${s.name}-${s.start}`}
              className="py-2.5 flex items-center justify-between gap-4 text-sm"
            >
              <div className="min-w-0">
                <span className="tabular-nums text-slate-500 mr-3">
                  {s.days === 1 ? s.start : `${s.start} – ${s.end}`}
                </span>
                <span className="text-slate-700">{s.name}</span>
                {s.days > 1 && (
                  <span className="text-xs text-slate-400 ml-2">
                    {s.days} days
                  </span>
                )}
              </div>
              {s.exchangeable && (
                <Badge variant="outline" className="text-xs shrink-0">
                  Exchangeable
                </Badge>
              )}
            </li>
          ))}
        </ul>
      )}
    </DialogContent>
  </Dialog>
);

export default HolidaysDialog;
