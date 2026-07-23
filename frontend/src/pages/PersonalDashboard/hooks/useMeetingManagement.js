import { useState, useEffect, useCallback, useRef } from "react";
import { getMyMentorshipPartners } from "@/api/mentorshipApi";
import { partnerDisplayName } from "@/utils/partnerName";
import {
  getMyMentorshipMeetingsV2,
  postMyMentorshipMeetingV2,
  deleteMeeting,
  batchDeleteMeetings,
} from "@/api/meetingApi";

/**
 * React hook for managing mentorship meetings and partner data
 * for a specific mentorship round.
 *
 * Responsibilities:
 * - Fetch and filter upcoming (uncompleted) meetings for the active round.
 * - Maintain a map of available mentorship partners.
 * - Provide wrappers for booking, canceling, and batch-canceling meetings.
 * - Safe state management to guard against updates after unmounting.
 *
 * @param {string | number} roundId - The ID of the targeted mentorship round.
 * @returns {{
 *   upcomingMeetings: Array<Object>,
 *   partners: Map<string, Object>,
 *   isLoading: boolean,
 *   bookMeeting: (payload: Object) => Promise<{created: Array, failed: Array}|undefined>,
 *   cancelMeetings: (meetingsToCancel: Array<Object>) => Promise<void>,
 *   refresh: () => Promise<void>
 * }}
 */
export function useMeetingManagement(roundId) {
  const [upcomingMeetings, setUpcomingMeetings] = useState([]);
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
   * Fetches meetings and partners data from the APIs, processes the information,
   * and populates the upcoming meetings list and partners map.
   *
   * @returns {Promise<void>}
   */
  const fetchPageData = useCallback(async () => {
    if (!roundId) {
      setUpcomingMeetings([]);
      setPartners(new Map());
      return;
    }
    setIsLoading(true);
    try {
      // Fetch both V2 meetings and partners concurrently in accordance with business requirements
      const [meetingsRes, partnersRes] = await Promise.all([
        getMyMentorshipMeetingsV2({ roundId, includeDetails: false }),
        getMyMentorshipPartners(roundId),
      ]);

      if (!isMounted.current) return;

      const partnersInfo = partnersRes?.data ?? [];
      const meetingLog = meetingsRes?.data ?? {};

      // 1. Build Partner Map for quick lookup
      const partnerMap = new Map();
      if (Array.isArray(partnersInfo)) {
        partnersInfo.forEach((p) => {
          if (p?.id) partnerMap.set(String(p.id), p);
        });
      }
      setPartners(partnerMap);

      // 2. Filter and extract upcoming (uncompleted) meetings
      const upcoming = [];
      const meetingInfoList = meetingLog?.meetingInfo ?? [];

      for (const partnerEntry of meetingInfoList) {
        if (!partnerEntry || !partnerEntry.partnerId) continue;
        const pId = String(partnerEntry.partnerId || "");
        const pInfo = partnerMap.get(pId) || {};
        const timeList = partnerEntry.meetingTimeList ?? [];

        for (const m of timeList) {
          if (!m || m.isCompleted) continue;

          upcoming.push({
            meetingId: m.meetingId,
            partnerId: partnerEntry.partnerId,
            partnerRole: partnerEntry.participantRole,
            partnerName: partnerDisplayName(pInfo) || "Unknown",
            partnerEmail: pInfo.email || "",
            startDatetime: m.startDatetime,
            endDatetime: m.endDatetime,
          });
        }
      }

      setUpcomingMeetings(upcoming);
    } catch (error) {
      console.error("Failed to fetch meeting log", error);
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

  /**
   * Cancel single or multiple mentorship meetings.
   * If a single meeting is provided, it uses the standard deletion endpoint.
   * If multiple meetings are provided, it groups them by partner and calls the batch deletion endpoint.
   *
   * @param {Array<Object>} meetingsToCancel - Array of meeting objects to be canceled.
   * @returns {Promise<void>}
   */
  const cancelMeetings = useCallback(
    async (meetingsToCancel) => {
      if (!Array.isArray(meetingsToCancel) || meetingsToCancel.length === 0) {
        return;
      }

      setIsLoading(true);

      try {
        if (meetingsToCancel.length === 1) {
          // Handle single meeting cancellation
          const m = meetingsToCancel[0];
          if (m && m.meetingId && m.partnerId) {
            await deleteMeeting(m.meetingId, roundId, m.partnerId);
          }
        } else {
          // Handle batch meeting cancellation grouped by partner
          const byPartner = new Map();
          for (const m of meetingsToCancel) {
            if (!m || !m.partnerId || !m.meetingId) continue;
            const groupKey = m.partnerId;
            if (!byPartner.has(groupKey)) {
              byPartner.set(groupKey, []);
            }
            byPartner.get(groupKey).push(m.meetingId);
          }

          // Format payload for batch deletion API
          const deletions = [...byPartner.entries()].map(
            ([partnerId, meetingIds]) => ({
              roundId: roundId,
              partnerId,
              meetingIds,
            }),
          );

          if (deletions.length > 0) {
            await batchDeleteMeetings(deletions);
          }
        }

        await fetchPageData();
      } catch (error) {
        console.error("Cancel meetings failed:", error);
        throw error;
      } finally {
        if (isMounted.current) setIsLoading(false);
      }
    },
    [roundId, fetchPageData],
  );

  return {
    upcomingMeetings,
    partners,
    isLoading,
    bookMeeting,
    cancelMeetings,
    refresh: fetchPageData,
  };
}
