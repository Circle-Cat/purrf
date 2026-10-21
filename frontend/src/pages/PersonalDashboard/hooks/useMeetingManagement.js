import { useState, useEffect, useCallback, useRef } from "react";
import { getMyMentorshipPartners } from "@/api/mentorshipApi";
import { postMyMentorshipMeetingV2 } from "@/api/meetingApi";

/**
 * React hook for the mentorship partners of one round and for booking
 * meetings with them.
 *
 * Responsibilities:
 * - Maintain a map of available mentorship partners.
 * - Provide a wrapper for booking a meeting.
 * - Safe state management to guard against updates after unmounting.
 *
 * The meetings themselves are not read here: they are shown, and cancelled,
 * on the participation card, which loads them with the rest of the round.
 *
 * @param {string | number} roundId - The ID of the targeted mentorship round.
 * @returns {{
 *   partners: Map<string, Object>,
 *   isLoading: boolean,
 *   bookMeeting: (payload: Object) => Promise<{created: Array, failed: Array}|undefined>,
 *   refresh: () => Promise<void>
 * }}
 */
export function useMeetingManagement(roundId) {
  const [partners, setPartners] = useState(new Map());
  const [isLoading, setIsLoading] = useState(false);

  // Track the component's mount status to prevent memory leaks / state updates after unmount
  const isMounted = useRef(true);
  useEffect(() => {
    isMounted.current = true;
    return () => {
      isMounted.current = false;
    };
  }, []);

  /**
   * Fetches the round's partners and populates the partner map.
   *
   * @returns {Promise<void>}
   */
  const fetchPageData = useCallback(async () => {
    if (!roundId) {
      setPartners(new Map());
      return;
    }
    setIsLoading(true);
    try {
      const partnersRes = await getMyMentorshipPartners(roundId);

      if (!isMounted.current) return;

      const partnersInfo = partnersRes?.data ?? [];

      // Build Partner Map for quick lookup
      const partnerMap = new Map();
      if (Array.isArray(partnersInfo)) {
        partnersInfo.forEach((p) => {
          if (p?.id) partnerMap.set(String(p.id), p);
        });
      }
      setPartners(partnerMap);
    } catch (error) {
      console.error("Failed to fetch mentorship partners", error);
    } finally {
      if (isMounted.current) setIsLoading(false);
    }
  }, [roundId]);

  // Automatically trigger data fetch when the round ID or fetch function changes
  useEffect(() => {
    fetchPageData();
  }, [roundId]);

  /**
   * Book a new mentorship meeting.
   *
   * @param {Object} payload - Meeting scheduling payload.
   * @returns {Promise<{created: Array, failed: Array}|undefined>}
   */
  const bookMeeting = useCallback(
    async (payload) => {
      setIsLoading(true);
      try {
        const res = await postMyMentorshipMeetingV2(payload);
        await fetchPageData();
        return res?.data;
      } catch (error) {
        console.error("Book meeting failed:", error);
        throw error;
      } finally {
        if (isMounted.current) setIsLoading(false);
      }
    },
    [fetchPageData],
  );

  return {
    partners,
    isLoading,
    bookMeeting,
    refresh: fetchPageData,
  };
}
