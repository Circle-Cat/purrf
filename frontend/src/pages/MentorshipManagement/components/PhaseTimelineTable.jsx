import { useState, useEffect } from "react";
import { format } from "date-fns";
import { CalendarIcon } from "lucide-react";
import { cn } from "@/lib/utils";
import { Calendar } from "@/components/ui/calendar";
import {
  Popover,
  PopoverContent,
  PopoverTrigger,
} from "@/components/ui/popover";
import { Button } from "@/components/ui/button";
import { Label } from "@/components/ui/label";
import { TIMELINE_PHASES } from "@/pages/MentorshipManagement/utils/roundForm";

function DatePickerField({
  label,
  value,
  onChange,
  required,
  error,
  minDate,
  disabled,
}) {
  const today = new Date();
  const [month, setMonth] = useState(value ?? today);

  useEffect(() => {
    if (value) setMonth(value);
  }, [value]);

  return (
    <div className="flex flex-col gap-1">
      <Label className="text-xs text-muted-foreground">
        {label}
        {required && <span className="text-destructive ml-0.5">*</span>}
      </Label>
      <Popover
        onOpenChange={(open) => {
          if (open) setMonth(value ?? today);
        }}
      >
        <PopoverTrigger asChild>
          <Button
            variant="outline"
            disabled={disabled}
            className={cn(
              "w-full justify-start text-left font-normal",
              !value && "text-muted-foreground",
            )}
          >
            <CalendarIcon className="mr-2 h-4 w-4" />
            {value ? format(value, "yyyy / MM / dd") : <span>Pick a date</span>}
          </Button>
        </PopoverTrigger>
        <PopoverContent className="w-auto p-0 z-[201]" align="start">
          <Calendar
            mode="single"
            selected={value}
            onSelect={(date) => onChange(date ?? null)}
            month={month}
            onMonthChange={setMonth}
            captionLayout="dropdown"
            disabled={minDate ? { before: minDate } : undefined}
            startMonth={minDate}
            endMonth={new Date(today.getFullYear() + 2, 11)}
            initialFocus
          />
          <div className="flex justify-end border-t px-3 py-2">
            <Button
              variant="ghost"
              size="sm"
              className="h-7 px-2 text-xs text-muted-foreground hover:text-foreground"
              onClick={() => onChange(null)}
              disabled={!value}
            >
              Clear
            </Button>
          </div>
        </PopoverContent>
      </Popover>
      {error && <span className="text-destructive text-xs">{error}</span>}
    </div>
  );
}

/**
 * Phase timeline configuration table for the round modal.
 *
 * @param {{
 *   form: Object,
 *   errors: Object,
 *   setField: (key: string) => (value: Date | null) => void,
 *   minDate: Date,
 * }} props
 */
export default function PhaseTimelineTable({
  form,
  errors,
  setField,
  minDate,
  readOnly,
}) {
  return (
    <div className="overflow-x-auto rounded-lg overflow-hidden border border-gray-200">
      <table className="w-full text-sm border-collapse table-fixed">
        <thead>
          <tr className="bg-accent text-left text-xs font-semibold text-accent-foreground uppercase tracking-wide">
            <th className="px-3 py-2 border-b border-border w-28">Phase</th>
            <th className="px-3 py-2 border-b border-l border-border w-[46%]">
              Admin Action
            </th>
            <th className="px-3 py-2 border-b border-l border-border w-[46%]">
              Participant Deadline
            </th>
          </tr>
        </thead>
        <tbody>
          {TIMELINE_PHASES.map((row) => (
            <tr
              key={row.phase}
              className="border-b border-border hover:bg-accent/30 transition-colors last:border-b-0"
            >
              <td className="px-3 py-3 font-medium text-gray-700 align-top">
                <div className="flex items-center gap-2">
                  <span
                    className={`w-2 h-2 rounded-full flex-shrink-0 ${row.dotColor}`}
                  />
                  {row.phase}
                </div>
              </td>
              <td className="px-3 py-3 border-l border-gray-200 align-top">
                <DatePickerField
                  label={row.adminAction.label}
                  value={form[row.adminAction.key]}
                  onChange={setField(row.adminAction.key)}
                  required={row.adminAction.required}
                  error={errors[row.adminAction.key]}
                  minDate={minDate}
                  disabled={readOnly}
                />
              </td>
              <td className="px-3 py-3 border-l border-gray-200 align-top">
                <div className="flex flex-col gap-3">
                  {row.participantDeadlines.map((f) => (
                    <DatePickerField
                      key={f.key}
                      label={f.label}
                      value={form[f.key]}
                      onChange={setField(f.key)}
                      required={f.required}
                      error={errors[f.key]}
                      minDate={minDate}
                      disabled={readOnly}
                    />
                  ))}
                </div>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
