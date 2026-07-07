import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { RadioGroup, RadioGroupItem } from "@/components/ui/radio-group";
import { Label } from "@/components/ui/label";

const NONE = "__none__";

/**
 * A user-picker backed by an ApproverDto[]-shaped pool
 * (`{userId, name, email}`). Emits `undefined` when the "none" option is
 * chosen. Defaults to a dropdown Select; pass `variant="list"` to render
 * every pool member as a single-select radio list instead (set
 * `allowNone={false}` to drop the "none" choice when a pick is required,
 * and `noneLabel` to relabel it, e.g. "Decide later").
 *
 * @param {{label: string, pool: {userId: number, name: string, email: string}[],
 *          value: number|undefined, onChange: (userId: number|undefined) => void,
 *          variant?: "select"|"list", allowNone?: boolean, noneLabel?: string}} props
 */
const PeoplePicker = ({
  label,
  pool,
  value,
  onChange,
  variant = "select",
  allowNone = true,
  noneLabel = "— none —",
}) => {
  if (variant === "list") {
    return (
      <div className="flex flex-col gap-2">
        <p className="text-sm font-medium text-slate-700">{label}</p>
        <RadioGroup
          aria-label={label}
          value={value != null ? String(value) : allowNone ? NONE : undefined}
          onValueChange={(v) => onChange(v === NONE ? undefined : Number(v))}
        >
          {allowNone && (
            <Label className="flex items-center gap-2 text-sm font-normal">
              <RadioGroupItem value={NONE} aria-label={noneLabel} />
              {noneLabel}
            </Label>
          )}
          {pool.map((u) => (
            <Label
              key={u.userId}
              className="flex items-center gap-2 text-sm font-normal"
            >
              <RadioGroupItem
                value={String(u.userId)}
                aria-label={`${u.name} (${u.email})`}
              />
              {u.name} ({u.email})
            </Label>
          ))}
        </RadioGroup>
      </div>
    );
  }

  return (
    <Select
      value={value != null ? String(value) : NONE}
      onValueChange={(v) => onChange(v === NONE ? undefined : Number(v))}
    >
      <SelectTrigger aria-label={label} className="max-w-xs">
        <SelectValue placeholder={noneLabel} />
      </SelectTrigger>
      <SelectContent className="z-[110]">
        <SelectItem value={NONE}>{noneLabel}</SelectItem>
        {pool.map((u) => (
          <SelectItem key={u.userId} value={String(u.userId)}>
            {u.name} ({u.email})
          </SelectItem>
        ))}
      </SelectContent>
    </Select>
  );
};

export default PeoplePicker;
