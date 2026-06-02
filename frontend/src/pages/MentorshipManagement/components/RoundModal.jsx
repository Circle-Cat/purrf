import { useState, useEffect } from "react";
import { Calendar, RotateCcw } from "lucide-react";
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogFooter,
} from "@/components/ui/dialog";
import { Button } from "@/components/ui/button";
import { Label } from "@/components/ui/label";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import {
  EMPTY_FORM,
  getSeasonDefaults,
  mapRoundToForm,
  buildUpsertPayload,
  validateForm,
} from "@/pages/MentorshipManagement/utils/roundForm";
import PhaseTimelineTable from "@/pages/MentorshipManagement/components/PhaseTimelineTable";

const SEASONS = ["Spring", "Summer", "Fall"];

const EMPTY_TEMPLATE = { season: "", year: "" };

/**
 * Modal for creating or editing a mentorship round.
 *
 * - Create mode: open === true, round === null
 * - Edit mode: open === true, round === { id, name, ... }
 *
 * @param {{
 *   open: boolean,
 *   round: Object|null,
 *   onClose: () => void,
 *   onSave: (payload: Object) => Promise<void>,
 *   rounds?: Object[],
 * }} props
 */
export default function RoundModal({
  open,
  round,
  onClose,
  onSave,
  rounds = [],
}) {
  const isEdit = round != null;
  const currentYear = new Date().getFullYear();
  // Spring rounds can include dates from the previous year (e.g. sign-up in Dec).
  // Editing is limited to the historical range of existing rounds (earliest: 2024).
  const minDate = isEdit
    ? new Date(2024, 0, 1)
    : new Date(currentYear - 1, 0, 1);
  const yearOptions = [
    String(currentYear),
    String(currentYear + 1),
    String(currentYear + 2),
  ];

  const [form, setForm] = useState(EMPTY_FORM);
  const [initialForm, setInitialForm] = useState(EMPTY_FORM);
  const [template, setTemplate] = useState(EMPTY_TEMPLATE);
  const [formError, setFormError] = useState({});
  const [apiError, setApiError] = useState(null);
  const [isSaving, setIsSaving] = useState(false);

  const initializeEditForm = (r) => {
    if (!r) return;
    const initial = mapRoundToForm(r);
    setForm(initial);
    setInitialForm({ ...initial });
  };

  const initializeCreateForm = () => {
    setTemplate(EMPTY_TEMPLATE);
    setForm({ ...EMPTY_FORM });
    setInitialForm({ ...EMPTY_FORM });
  };

  useEffect(() => {
    if (!open) return;
    if (isEdit) {
      initializeEditForm(round);
    } else {
      initializeCreateForm();
    }
    setFormError({});
    setApiError(null);
    setIsSaving(false);
  }, [open, round, isEdit]);

  const resetForm = () => {
    setForm(initialForm);
    setFormError({});
    setApiError(null);
    if (!isEdit) setTemplate(EMPTY_TEMPLATE);
  };

  const setField = (key) => (value) => setForm((f) => ({ ...f, [key]: value }));

  const applyTemplate = (season, year) => {
    setTemplate({ season, year });
    if (season && year) {
      const defaults = getSeasonDefaults(season, year) ?? {};
      setForm((f) => ({
        ...f,
        ...defaults,
        name: `Mentorship ${year} ${season}`,
      }));
    }
  };

  const handleSeasonChange = (s) => applyTemplate(s, template.year);
  const handleYearChange = (y) => applyTemplate(template.season, y);

  const submitForm = async () => {
    const existingNames = rounds
      .filter((r) => r.id !== form.id)
      .map((r) => r.name);
    const errs = validateForm(form, existingNames);
    if (Object.keys(errs).length > 0) {
      setFormError(errs);
      return;
    }
    setFormError({});
    setApiError(null);
    setIsSaving(true);
    try {
      await onSave(buildUpsertPayload(form));
    } catch (err) {
      const msg = err?.response?.data?.message || err?.message;
      setApiError(msg ?? "Failed to save round. Please try again.");
    } finally {
      setIsSaving(false);
    }
  };

  return (
    <Dialog
      open={open}
      onOpenChange={(v) => {
        if (!v) onClose();
      }}
    >
      <DialogContent
        className="sm:max-w-3xl max-h-[90vh] flex flex-col z-[200]"
        onOpenAutoFocus={(e) => e.preventDefault()}
        onInteractOutside={(e) => e.preventDefault()}
      >
        <DialogHeader className="flex-row items-center justify-between">
          <DialogTitle className="text-xl">
            {isEdit ? "Edit Round" : "Create New Round"}
          </DialogTitle>
          <div className="relative inline-block group mr-5">
            <Button
              variant="outline"
              size="sm"
              onClick={resetForm}
              disabled={isSaving}
            >
              <RotateCcw className="h-4 w-4" />
              Reset
            </Button>
            <span className="invisible group-hover:visible opacity-0 group-hover:opacity-100 transition-opacity absolute top-full right-0 mt-1 px-3 py-1.5 bg-white text-muted-foreground text-sm rounded shadow-lg w-72 z-10 pointer-events-none">
              {isEdit
                ? "Restore all fields to their last saved values."
                : "Clear all fields and reset the season and year selection."}
            </span>
          </div>
        </DialogHeader>

        <div className="flex-1 overflow-y-auto px-1">
          <div className="space-y-4 py-2">
            {!isEdit && (
              <div className="flex flex-col gap-1.5">
                <Label className="text-sm font-medium">Quick Fill</Label>
                <p className="text-sm text-muted-foreground">
                  Select a season and year to auto-fill all fields below.
                </p>
                <div className="flex gap-3 items-center flex-wrap">
                  <Select
                    value={template.season}
                    onValueChange={handleSeasonChange}
                  >
                    <SelectTrigger className="w-auto min-w-[7rem]">
                      <SelectValue placeholder="Select season" />
                    </SelectTrigger>
                    <SelectContent className="z-[201]">
                      {SEASONS.map((s) => (
                        <SelectItem key={s} value={s}>
                          {s}
                        </SelectItem>
                      ))}
                    </SelectContent>
                  </Select>
                  <Select
                    value={template.year}
                    onValueChange={handleYearChange}
                  >
                    <SelectTrigger className="w-auto min-w-[7rem]">
                      <SelectValue placeholder="Select year" />
                    </SelectTrigger>
                    <SelectContent className="z-[201]">
                      {yearOptions.map((y) => (
                        <SelectItem key={y} value={y}>
                          {y}
                        </SelectItem>
                      ))}
                    </SelectContent>
                  </Select>
                </div>
              </div>
            )}

            <div className="grid grid-cols-2 gap-4">
              <div className="flex flex-col gap-1">
                <Label htmlFor="round-name">
                  Round Name <span className="text-red-500">*</span>
                </Label>
                <input
                  id="round-name"
                  type="text"
                  value={form.name}
                  onChange={(e) => setField("name")(e.target.value)}
                  placeholder="e.g. Mentorship 2026 Spring"
                  className="w-full border rounded-md px-3 py-1.5 text-sm focus:outline-none focus:ring-2 focus:ring-ring placeholder:text-muted-foreground"
                />
                {formError.name && (
                  <span className="text-destructive text-xs">
                    {formError.name}
                  </span>
                )}
              </div>
              <div className="flex flex-col gap-1">
                <Label>
                  Required Meetings <span className="text-red-500">*</span>
                </Label>
                <Select
                  value={String(form.requiredMeetings)}
                  onValueChange={(v) => setField("requiredMeetings")(Number(v))}
                >
                  <SelectTrigger className="w-auto min-w-[7rem]">
                    <SelectValue placeholder="Select" />
                  </SelectTrigger>
                  <SelectContent className="z-[201]">
                    {Array.from({ length: 11 }, (_, i) => (
                      <SelectItem key={i} value={String(i)}>
                        {String(i)}
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
                {formError.requiredMeetings && (
                  <span className="text-destructive text-xs">
                    {formError.requiredMeetings}
                  </span>
                )}
              </div>
            </div>

            <div className="space-y-2">
              <div className="flex items-center gap-2">
                <Calendar className="h-5 w-5 text-primary" />
                <Label className="text-sm font-semibold text-gray-700">
                  Phase Timeline
                </Label>
                <span className="text-xs font-normal text-muted-foreground">
                  (All dates in Pacific Time 23:59:59)
                </span>
              </div>
              <p className="text-sm text-muted-foreground">
                Please ensure each date is later than the previous step.
              </p>
              <PhaseTimelineTable
                form={form}
                errors={formError}
                setField={setField}
                minDate={minDate}
              />
            </div>

            {apiError && (
              <span className="text-destructive text-xs">{apiError}</span>
            )}
          </div>
          <div className="pointer-events-none sticky bottom-0 h-8 bg-gradient-to-t from-background to-transparent" />
        </div>

        <DialogFooter>
          <Button variant="outline" onClick={onClose} disabled={isSaving}>
            Cancel
          </Button>
          <Button onClick={submitForm} disabled={isSaving}>
            {isSaving ? "Saving..." : "Save"}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
