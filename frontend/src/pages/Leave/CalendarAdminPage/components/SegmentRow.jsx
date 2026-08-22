import { Button } from "@/components/ui/button";
import { Checkbox } from "@/components/ui/checkbox";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";

/**
 * SegmentRow
 *
 * One run of company-holiday days sharing a name.
 *
 * Exchangeable is one checkbox for the whole run, not a choice per day: a
 * holiday either can be traded or it cannot. Which days of it somebody trades
 * is their own decision at request time, and the calendar does not record it.
 *
 * Native date inputs, whose values are already the `YYYY-MM-DD` strings the API
 * takes, so nothing here constructs a Date.
 *
 * @param {{
 *   index: number,
 *   segment: object,
 *   isSaving: boolean,
 *   onEdit: (index: number, field: string, value: any) => void,
 *   onRemove: (index: number) => void,
 * }} props
 */
const SegmentRow = ({ index, segment, isSaving, onEdit, onRemove }) => (
  <li className="flex flex-wrap items-end gap-3 py-3">
    <div className="min-w-[12rem] flex-1 space-y-1.5">
      <Label htmlFor={`segment-name-${index}`}>Name</Label>
      <Input
        id={`segment-name-${index}`}
        value={segment.name}
        disabled={isSaving}
        onChange={(event) => onEdit(index, "name", event.target.value)}
      />
    </div>
    <div className="space-y-1.5">
      <Label htmlFor={`segment-start-${index}`}>First day</Label>
      <Input
        id={`segment-start-${index}`}
        type="date"
        value={segment.startDate}
        disabled={isSaving}
        onChange={(event) => onEdit(index, "startDate", event.target.value)}
      />
    </div>
    <div className="space-y-1.5">
      <Label htmlFor={`segment-end-${index}`}>Last day</Label>
      <Input
        id={`segment-end-${index}`}
        type="date"
        value={segment.endDate}
        disabled={isSaving}
        onChange={(event) => onEdit(index, "endDate", event.target.value)}
      />
    </div>
    <div className="flex items-center gap-2 pb-2">
      <Checkbox
        id={`segment-exchangeable-${index}`}
        checked={Boolean(segment.isExchangeable)}
        disabled={isSaving}
        onCheckedChange={(checked) =>
          onEdit(index, "isExchangeable", Boolean(checked))
        }
      />
      <Label htmlFor={`segment-exchangeable-${index}`}>Exchangeable</Label>
    </div>
    <Button
      variant="outline"
      disabled={isSaving}
      onClick={() => onRemove(index)}
    >
      Remove
    </Button>
  </li>
);

export default SegmentRow;
