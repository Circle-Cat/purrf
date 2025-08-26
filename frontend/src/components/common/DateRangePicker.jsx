import "@/components/common/DateRangePicker.css";

import { useState, useEffect } from "react";

/**
 * DateRangePicker Component
 *
 * A pure React date range picker component using native <input type="date">.
 * Allows selecting a start date and an end date, automatically ensuring
 * a valid date range (startDate <= endDate).
 *
 * Props:
 * @param {string} defaultStartDate - Optional. Initial start date in "yyyy-MM-dd" format. Default is "".
 * @param {string} defaultEndDate - Optional. Initial end date in "yyyy-MM-dd" format. Default is "".
 * @param {function} onChange - Optional. Callback triggered when start or end date changes.
 *        Receives an object: { startDate: string, endDate: string }.
 *
 * Features:
 * - If the user changes the start date to be after the current end date,
 *   the end date is automatically updated to match the new start date.
 * - Changing the end date does not reduce the start date.
 * - Maximum selectable date is today.
 * - Supports dynamically updating default values from parent components.
 */

export default function DateRangePicker({
  defaultStartDate = "",
  defaultEndDate = "",
  onChange,
}) {
  const today = new Date().toISOString().split("T")[0];
  const [startDate, setStartDate] = useState(defaultStartDate || "");
  const [endDate, setEndDate] = useState(defaultEndDate || "");

  useEffect(() => {
    if (defaultStartDate) setStartDate(defaultStartDate);
    if (defaultEndDate) setEndDate(defaultEndDate);
  }, [defaultStartDate, defaultEndDate]);

  const handleChange = (newStart, newEnd) => {
    if (onChange) {
      onChange({ startDate: newStart, endDate: newEnd });
    }
  };

  const handleStartChange = (e) => {
    const newStart = e.target.value;
    setStartDate(newStart);
    let newEnd = endDate;
    if (endDate && newStart > endDate) {
      newEnd = newStart;
      setEndDate(newEnd);
    }
    handleChange(newStart, newEnd);
  };

  const handleEndChange = (e) => {
    const newEnd = e.target.value;
    setEndDate(newEnd);
    handleChange(startDate, newEnd);
  };

  return (
    <div className="date-range-picker">
      <input
        type="date"
        id="startDateInput"
        data-testid="start-date-input"
        className="start-date"
        value={startDate}
        onChange={handleStartChange}
        max={today}
      />

      <span className="date-separator">-</span>

      <input
        type="date"
        id="endDateInput"
        data-testid="end-date-input"
        className="end-date"
        value={endDate}
        onChange={handleEndChange}
        min={startDate || "1970-01-01"}
        max={today}
      />
    </div>
  );
}
