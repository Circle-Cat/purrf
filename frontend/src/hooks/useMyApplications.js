import { useCallback, useEffect, useState } from "react";
import { listMyApplications } from "@/api/recruitingApi";

/**
 * Fetches every application the current user has ever submitted (any job
 * kind) on mount, along with every mentorship role those applications
 * qualify them to register a round under.
 *
 * `hiredMentorshipRoles` is read straight off the response, not derived
 * here. Which roles a user may register as is validated server-side by the
 * registration endpoints; filtering the rows in the client would let the
 * buttons on screen offer something the save will reject.
 *
 * It has no fail-open default — it is `[]` while loading, on a load error,
 * and when the user holds no admission at all. Consumers that need to
 * distinguish "still loading" from "confirmed not a participant" should
 * also check `isLoading`/`loadError`.
 *
 * @returns {{
 *   applications: Array<{applicationId: number, jobId: number, jobTitle: string, jobKind: string, mentorshipRole: string|null, stage: string}>,
 *   isLoading: boolean,
 *   loadError: boolean,
 *   load: () => void,
 *   hiredMentorshipRoles: Array<"mentor" | "mentee">,
 * }}
 */
export const useMyApplications = () => {
  const [applications, setApplications] = useState([]);
  const [hiredMentorshipRoles, setHiredMentorshipRoles] = useState([]);
  const [isLoading, setIsLoading] = useState(true);
  const [loadError, setLoadError] = useState(false);

  const load = useCallback(() => {
    setIsLoading(true);
    setLoadError(false);
    listMyApplications()
      .then(({ data }) => {
        setApplications(data?.applications ?? []);
        setHiredMentorshipRoles(data?.mentorshipRoles ?? []);
      })
      .catch(() => {
        setLoadError(true);
        // A failed reload must not leave stale roles standing: the section
        // they gate would keep offering entry points nothing confirms.
        setHiredMentorshipRoles([]);
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
    hiredMentorshipRoles,
  };
};
