import {
  getAllMentorshipRounds,
  getMyMentorshipPartners,
  getMyMentorshipRegistration,
  postMyMentorshipRegistration,
} from "@/api/mentorshipApi";

import { calculateMentorshipSlots } from "@/pages/PersonalDashboard/utils/mentorshipRounds";
import { useEffect, useState } from "react";

/**
 * React hook for loading and managing mentorship-related data
 * for the Personal Dashboard.
 *
 * Responsibilities:
 * - Fetch all mentorship rounds and determine current registration
 *   and feedback slots.
 * - Load the current user's registration data for the active round.
 * - Lazily load past mentorship partners.
 * - Provide helpers for saving registration data.
 *
 * This hook encapsulates business rules around:
 * - which round is currently actionable
 * - whether registration or feedback actions are enabled
 *
 * @returns {{
 *   regRoundId: string | null,
 *   feedbackRoundId: string | null,
 *   isRegistrationOpen: boolean,
 *   isFeedbackEnabled: boolean,
 *   registration: Object | null,
 *   saveRegistration: (data: Object) => Promise<any> | undefined,
 *   isLoading: boolean,
 *   isPartnersLoading: boolean,
 *   loadPastPartners: () => Promise<void>
 * }}
 */
export const useMentorshipData = () => {
  const [roundStatus, setRoundStatus] = useState({
    regRoundId: null,
    feedbackRoundId: null,
    isRegistrationOpen: false,
    isFeedbackEnabled: false,
  });

  // Current user's registration data for the active round
  const [registration, setRegistration] = useState(null);

  // Loading state for initial mentorship data
  const [isLoading, setIsLoading] = useState(true);

  // Cached list of past mentorship partners
  const [pastPartners, setPastPartners] = useState([]);

  // Loading state for partners data
  const [isPartnersLoading, setIsPartnersLoading] = useState(false);

  /**
   * refreshRegistration
   *
   * Refreshes the current user's registration data if the registration round ID (`regRoundId`) is available.
   * It fetches the registration data associated with the current round and updates the `registration` state.
   * If the `regRoundId` is not set, no API call is made.
   *
   * @returns {Promise<void>} - A promise that resolves when the registration data has been refreshed or an error occurs.
   */
  const refreshRegistration = async () => {
    if (!roundStatus.regRoundId) return;
    try {
      const { data: regData } = await getMyMentorshipRegistration(
        roundStatus.regRoundId,
      );
      setRegistration(regData);
    } catch (err) {
      console.error("Failed to refresh registration", err);
    }
  };

  /**
   * useEffect to initialize and load mentorship data.
   *
   * This effect is run once when the component is mounted. It fetches the available mentorship rounds, calculates
   * the mentorship slot status, and then fetches the user's registration data for the active round (if any).
   * The loading state (`isLoading`) is set to `false` once the data has been fetched (or an error has occurred).
   *
   * @returns {void}
   */
  useEffect(() => {
    const fetchData = async () => {
      try {
        const { data: rounds } = await getAllMentorshipRounds();
        const status = calculateMentorshipSlots(rounds);
        setRoundStatus(status);

        // If there is an actionable round, fetch the user's registration data
        // Note: registration data is fetched based on the registration slot first
        if (status.regRoundId) {
          const { data: regData } = await getMyMentorshipRegistration(
            status.regRoundId,
          );
          setRegistration(regData);
        }
      } catch (err) {
        console.error("Failed to fetch mentorship data", err);
      } finally {
        setIsLoading(false);
      }
    };

    fetchData();
  }, []);

  /**
   * Lazily load the user's past mentorship partners.
   *
   * @returns {Promise<void>}
   */
  const loadPastPartners = async () => {
    setIsPartnersLoading(true);
    try {
      const { data: allPastPartners } = await getMyMentorshipPartners();
      setPastPartners(allPastPartners || []);
    } catch (err) {
      console.error("Failed to fetch partners data", err);
    } finally {
      setIsPartnersLoading(false);
    }
  };

  /**
   * Save or update the user's mentorship registration.
   *
   * This operation is only allowed when:
   * - a valid registration round exists
   * - registration for that round is currently open
   *
   * @param {Object} data - Registration payload submitted by the user.
   * @returns {Promise<any> | undefined} API response when saved, or undefined if not allowed.
   */
  const saveRegistration = async (data) => {
    // Only allow saving when registration is open and a valid round exists
    if (!roundStatus.regRoundId || !roundStatus.isRegistrationOpen) return;
    return postMyMentorshipRegistration(roundStatus.regRoundId, data);
  };

  return {
    ...roundStatus,
    registration,
    saveRegistration,
    isLoading,
    refreshRegistration,
    isPartnersLoading,
    loadPastPartners,
    pastPartners,
  };
};
