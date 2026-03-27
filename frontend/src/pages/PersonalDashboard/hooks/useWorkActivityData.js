import { useState, useEffect, useCallback } from "react";
import { getMySummary } from "@/api/dashboardApi";

/**
 * Fetches and manages the current user's work activity summary for a given date range.
 *
 * Defaults to the current calendar month (local time). The fetch is skipped
 * when `enabled` is false, avoiding unnecessary requests for non-internal users.
 *
 * @param {{ enabled?: boolean }} options
 * @param {boolean} [options.enabled=true] - Whether to fetch on mount. Pass `false` to suppress the initial request.
 *
 * @returns {{
 *   summary: {
 *     startDate: string,
 *     endDate: string,
 *     summary: {
 *       jiraTickets: number,
 *       mergedCLs: number,
 *       mergedLOC: number,
 *       meetingHours: number,
 *       chatMessages: number,
 *     }
 *   },
 *   isPersonalSummaryLoading: boolean,
 *   fetchPersonalSummary: (startDate: string, endDate: string) => Promise<void>
 * }}
 */
export const useWorkActivityData = ({ enabled = true } = {}) => {
  const [summary, setSummary] = useState(() => {
    const toLocalDateString = (d) =>
      `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}-${String(d.getDate()).padStart(2, "0")}`;

    const today = new Date();
    const firstOfMonth = new Date(today.getFullYear(), today.getMonth(), 1);

    return {
      startDate: toLocalDateString(firstOfMonth),
      endDate: toLocalDateString(today),
      summary: {
        jiraTickets: 0,
        mergedCLs: 0,
        mergedLOC: 0,
        meetingHours: 0,
        chatMessages: 0,
      },
    };
  });

  const [isPersonalSummaryLoading, setIsPersonalSummaryLoading] =
    useState(false);

  const fetchPersonalSummary = useCallback(async (startDate, endDate) => {
    try {
      setIsPersonalSummaryLoading(true);

      const res = await getMySummary({ startDate, endDate });
      const data = res?.data;

      setSummary({
        startDate,
        endDate,
        summary: {
          jiraTickets: data.jiraIssueDone ?? 0,
          mergedCLs: data.clMerged ?? 0,
          mergedLOC: data.locMerged ?? 0,
          meetingHours: data.meetingHours ?? 0,
          chatMessages: data.chatCount ?? 0,
        },
      });
    } catch (err) {
      console.error("Failed to fetch summary", err);
    } finally {
      setIsPersonalSummaryLoading(false);
    }
  }, []);

  useEffect(() => {
    if (!enabled) return;
    fetchPersonalSummary(summary.startDate, summary.endDate);
  }, [enabled, fetchPersonalSummary]);

  return {
    summary,
    isPersonalSummaryLoading,
    fetchPersonalSummary,
  };
};
