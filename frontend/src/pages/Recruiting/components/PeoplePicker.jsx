import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";

const NONE = "__none__";

/**
 * A user-picker Select backed by an ApproverDto[]-shaped pool
 * (`{userId, name, email}`). Emits `undefined` when the "— none —" option
 * is chosen.
 *
 * @param {{label: string, pool: {userId: number, name: string, email: string}[],
 *          value: number|undefined, onChange: (userId: number|undefined) => void}} props
 */
const PeoplePicker = ({ label, pool, value, onChange }) => (
  <Select
    value={value != null ? String(value) : NONE}
    onValueChange={(v) => onChange(v === NONE ? undefined : Number(v))}
  >
    <SelectTrigger aria-label={label} className="max-w-xs">
      <SelectValue placeholder="— none —" />
    </SelectTrigger>
    <SelectContent className="z-[110]">
      <SelectItem value={NONE}>— none —</SelectItem>
      {pool.map((u) => (
        <SelectItem key={u.userId} value={String(u.userId)}>
          {u.name} ({u.email})
        </SelectItem>
      ))}
    </SelectContent>
  </Select>
);

export default PeoplePicker;
