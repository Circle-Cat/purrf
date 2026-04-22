import React from "react";
import { Label } from "@/components/ui/label";
import { RadioGroup, RadioGroupItem } from "@/components/ui/radio-group";

export default function SurveyRadioQuestion({
  label,
  required = false,
  options,
  value,
  onValueChange,
  idPrefix,
  disabled,
  error,
  otherId = "other",
  otherValue = "",
  onOtherChange,
  otherError,
  otherMaxLength = 100,
  otherPlaceholder = "Please specify...",
}) {
  const showOtherInput = onOtherChange && value === otherId;

  return (
    <div className="space-y-3">
      <Label className="text-sm font-semibold">
        {label}
        {required && (
          <>
            {" "}
            <span className="text-destructive">*</span>
          </>
        )}
      </Label>
      <RadioGroup
        disabled={disabled}
        value={value}
        onValueChange={onValueChange}
        className="flex flex-col gap-2"
      >
        {options.map((opt) => (
          <div key={opt.id} className="flex items-center space-x-2">
            <RadioGroupItem value={opt.id} id={`${idPrefix}-${opt.id}`} />
            <Label
              htmlFor={`${idPrefix}-${opt.id}`}
              className="font-normal cursor-pointer text-sm"
            >
              {opt.label}
            </Label>
          </div>
        ))}
      </RadioGroup>
      {error && <span className="text-destructive text-xs">{error}</span>}
      {showOtherInput && (
        <div className="relative">
          <input
            disabled={disabled}
            type="text"
            placeholder={otherPlaceholder}
            value={otherValue}
            onChange={(e) => onOtherChange(e.target.value)}
            maxLength={otherMaxLength}
            className={`w-full p-2 pr-16 border rounded-md text-sm focus:outline-none focus:ring-2 focus:ring-ring${otherError ? " border-destructive" : ""}`}
          />
          <div className="absolute bottom-2 right-2 text-xs text-muted-foreground pointer-events-none">
            {otherValue.length} / {otherMaxLength}
          </div>
        </div>
      )}
      {otherError && (
        <span className="text-destructive text-xs">{otherError}</span>
      )}
    </div>
  );
}
