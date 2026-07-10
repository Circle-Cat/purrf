import { useCallback, useEffect, useState } from "react";
import { listMyApplications } from "@/api/recruitingApi";

/**
 * Fetches every application the current user has ever submitted (any job
 * kind) on mount, and derives the role of their HIRED mentorship (ACTIVITY
 * + mentor/mentee role) application, if any.
 *
 * `hiredMentorshipRole` has no fail-open default — it is `null` while
 * loading, on a load error, or when there genuinely is no hired mentorship
 * application, and only ever `"mentor"`/`"mentee"` once the list has
 * resolved and actually contains one. Consumers that need to distinguish
 * "still loading" from "confirmed not a participant" should also check
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
  const [isLoading, setIsLoading] = useState(true);
  const [loadError, setLoadError] = useState(false);

  const load = useCallback(() => {
    setIsLoading(true);
    setLoadError(false);
    listMyApplications()
      .then(({ data }) => setApplications(data ?? []))
      .catch(() => setLoadError(true))
      .finally(() => setIsLoading(false));
  }, []);

  useEffect(() => {
    load();
  }, [load]);

  const hiredApplication = applications.find(
    (a) =>
      a.jobKind === "activity" &&
      a.stage === "hired" &&
      (a.mentorshipRole === "mentor" || a.mentorshipRole === "mentee"),
  );
  const hiredMentorshipRole = hiredApplication?.mentorshipRole ?? null;

  return {
    applications,
    isLoading,
    loadError,
    load,
    hiredMentorshipRole,
  };
};
