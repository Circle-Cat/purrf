import { useCallback, useEffect, useState } from "react";

import {
  getLeaveHolidayYears,
  getLeaveHolidays,
  replaceLeaveHolidays,
} from "@/api/leaveApi";

/** The message the server sent, which names the segment at fault. */
const refusalMessage = (error) =>
  error?.response?.data?.message ?? "Something went wrong. Try again.";

/** A blank row, ready to be filled in. */
export const blankSegment = () => ({
  name: "",
  startDate: "",
  endDate: "",
  isExchangeable: false,
});

/**
 * One year of the company holiday calendar, held for editing.
 *
 * The year is edited as a whole and saved as a whole, because that is what the
 * endpoint does: anything absent from the payload is deleted. So the rows here
 * are the year, and removing one and saving deletes it -- which is why the page
 * confirms before saving rather than after.
 *
 * Which years exist and which one is current both come from the server. A
 * browser in another timezone would otherwise disagree about the year, and on
 * 1 January that disagreement edits the wrong calendar.
 *
 * Nothing here validates a segment. The server refuses six ways -- an empty
 * year, a nameless holiday, one that ends before it starts, one spanning two
 * years, one in the wrong year, two that cover the same day -- and each message
 * names the holiday at fault. A copy of those rules here would be free to
 * disagree with the one that actually refuses.
 *
 * @param {{enabled?: boolean}} [options]
 * @returns {object} The year list, the rows being edited, and the actions.
 */
export const useLeaveCalendarAdmin = ({ enabled = true } = {}) => {
  const [years, setYears] = useState([]);
  const [year, setYear] = useState(null);
  const [segments, setSegments] = useState([]);
  const [isLoading, setIsLoading] = useState(true);
  const [loadError, setLoadError] = useState(false);
  const [isSaving, setIsSaving] = useState(false);
  const [saveError, setSaveError] = useState(null);
  const [isDirty, setIsDirty] = useState(false);

  useEffect(() => {
    if (!enabled) return;
    getLeaveHolidayYears()
      .then(({ data }) => {
        const offered = Array.from(
          new Set(
            [...(data?.years ?? []), data?.currentYear, data?.nextYear].filter(
              (value) => typeof value === "number",
            ),
          ),
        ).sort();
        setYears(offered);
        setYear((previous) => previous ?? data?.currentYear ?? null);
      })
      .catch(() => setLoadError(true));
  }, [enabled]);

  const load = useCallback(
    (wanted) => {
      if (!enabled || wanted === null || wanted === undefined) return;
      setIsLoading(true);
      setLoadError(false);
      setSaveError(null);
      getLeaveHolidays(wanted)
        .then(({ data }) => {
          setSegments(data?.segments ?? []);
          setIsDirty(false);
        })
        .catch(() => {
          setLoadError(true);
          setSegments([]);
        })
        .finally(() => setIsLoading(false));
    },
    [enabled],
  );

  useEffect(() => {
    load(year);
  }, [year, load]);

  const edit = useCallback((index, field, value) => {
    setSegments((previous) =>
      previous.map((segment, at) =>
        at === index ? { ...segment, [field]: value } : segment,
      ),
    );
    setIsDirty(true);
  }, []);

  const add = useCallback(() => {
    setSegments((previous) => [...previous, blankSegment()]);
    setIsDirty(true);
  }, []);

  const remove = useCallback((index) => {
    setSegments((previous) => previous.filter((_, at) => at !== index));
    setIsDirty(true);
  }, []);

  const save = useCallback(async () => {
    if (isSaving || year === null) return false;
    setIsSaving(true);
    setSaveError(null);
    try {
      await replaceLeaveHolidays(
        year,
        segments.map((segment) => ({
          name: segment.name,
          startDate: segment.startDate,
          endDate: segment.endDate,
          isExchangeable: Boolean(segment.isExchangeable),
        })),
      );
      // Re-read rather than trust the local rows: the server derives the
      // segments back out of the days it stored, so a run entered as two
      // adjacent segments with one name comes back as one.
      load(year);
      return true;
    } catch (error) {
      setSaveError(refusalMessage(error));
      return false;
    } finally {
      setIsSaving(false);
    }
  }, [isSaving, year, segments, load]);

  return {
    years,
    year,
    setYear,
    segments,
    isLoading,
    loadError,
    isSaving,
    saveError,
    isDirty,
    load,
    edit,
    add,
    remove,
    save,
  };
};
