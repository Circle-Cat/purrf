import { formatBusinessDate } from "@/pages/Leave/utils/leaveDates";

/**
 * What is wrong with each holiday on the calendar page, before it is saved.
 *
 * The same rules the server refuses a year with, checked as the admin types so
 * the row at fault can be marked where it is. The server still checks: if the
 * two ever disagree, its refusal is shown as before and nothing is written.
 *
 * Dates are compared as `YYYY-MM-DD` strings, which sort as dates do, so
 * nothing here constructs a Date.
 *
 * @param {number|null} year The year being edited.
 * @param {Array<{name: string, startDate: string, endDate: string}>} segments
 *   The rows on the page, in order.
 * @returns {{byIndex: Object<number, string[]>, hasProblems: boolean}} The
 *   problems of each row that has any, and whether the year can be saved.
 */
export const calendarProblems = (year, segments) => {
  const byIndex = {};
  const add = (index, problem) => {
    byIndex[index] = [...(byIndex[index] ?? []), problem];
  };

  segments.forEach((segment, index) => {
    // A row just added says one thing, not three.
    if (!segment.name?.trim() && !segment.startDate && !segment.endDate) {
      add(index, "Fill in this holiday, or remove it.");
      return;
    }
    if (!segment.name?.trim()) add(index, "Give the holiday a name.");
    if (!segment.startDate || !segment.endDate) {
      add(index, "Give its first and last day.");
      return;
    }
    if (segment.endDate < segment.startDate) {
      add(index, "It ends before it starts.");
      return;
    }
    const startYear = Number(segment.startDate.slice(0, 4));
    const endYear = Number(segment.endDate.slice(0, 4));
    if (startYear !== endYear) {
      add(index, "It spans two years. Enter it as two holidays, one per year.");
    } else if (year !== null && startYear !== year) {
      add(index, `It falls in ${startYear}, not ${year}.`);
    }
  });

  // Overlaps only between rows whose own dates make sense.
  const sound = segments.map((_, index) => !byIndex[index]);
  segments.forEach((segment, index) => {
    if (!sound[index]) return;
    segments.forEach((other, otherIndex) => {
      if (otherIndex === index || !sound[otherIndex]) return;
      if (
        segment.startDate > other.endDate ||
        other.startDate > segment.endDate
      )
        return;
      const firstShared =
        segment.startDate > other.startDate
          ? segment.startDate
          : other.startDate;
      add(
        index,
        `It overlaps ${other.name.trim()} on ${formatBusinessDate(firstShared)}.`,
      );
    });
  });

  return {
    byIndex,
    hasProblems: segments.length === 0 || Object.keys(byIndex).length > 0,
  };
};
