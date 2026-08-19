import { useCallback, useEffect, useState } from "react";
import { listMyApplications } from "@/api/recruitingApi";

/**
 * Fetches every application the current user has ever submitted (any job
 * kind) on mount, along with the mentorship role those applications earned
 * them.
 *
 * `hiredMentorshipRole` is read straight off the response, not derived
 * here. Which of several hired mentor/mentee applications governs is the
 * same rule that decides what a mentorship round registration is submitted
 * as, and it is settled server-side; deriving it a second time in the
 * client would let the form a user fills in disagree with the registration
 * it saves.
 *
 * It has no fail-open default — it is `null` while loading, on a load
 * error, or when there genuinely is no hired mentorship application, and
 * only ever `"mentor"`/`"mentee"` once the response has resolved and
 * actually carries one. Consumers that need to distinguish "still loading"
 * from "confirmed not a participant" should also check
 * `isLoading`/`loadError`.
 *
 * @returns {{
 *   applications: Array<{applicationId: number, jobId: number, jobTitle: string, jobKind: string, mentorshipRole: string|null, stage: string}>,
 *   isLoading: boolean,
 *   loadError: boolean,
 *   load: () => void,
 *   hiredMentorshipRole: "mentor" | "mentee" | null,
 * }}
 */
export const useMyApplications = () => {
  const [applications, setApplications] = useState([]);
  const [hiredMentorshipRole, setHiredMentorshipRole] = useState(null);
  const [isLoading, setIsLoading] = useState(true);
  const [loadError, setLoadError] = useState(false);

  const load = useCallback(() => {
    setIsLoading(true);
    setLoadError(false);
    listMyApplications()
      .then(({ data }) => {
        setApplications(data?.applications ?? []);
        setHiredMentorshipRole(data?.lastMentorshipRole ?? null);
      })
      .catch(() => {
        setLoadError(true);
        // A failed reload must not leave a stale role standing: the section
        // it gates would keep rendering against an answer nothing confirms.
        setHiredMentorshipRole(null);
      })
      .finally(() => setIsLoading(false));
  }, []);

  useEffect(() => {
    load();
  }, [load]);

  return {
    applications,
    isLoading,
    loadError,
    load,
    hiredMentorshipRole,
  };
};
