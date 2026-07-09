import { useCallback, useEffect, useState } from "react";
import { listMyApplications } from "@/api/recruitingApi";

/**
 * Fetches every application the current user has ever submitted (any job
 * kind) on mount, and derives whether they have at least one HIRED
 * mentorship (ACTIVITY + mentor/mentee role) application.
 *
 * `hasHiredMentorshipApplication` fails open (defaults to `true`) while
 * loading or on a load error, so a slow/failed fetch never hides a real
 * mentor/mentee's participation cards — it only turns `false` once the
 * list has resolved and genuinely contains no hired mentorship application.
 *
 * @returns {{
 *   applications: Array<{applicationId: number, jobId: number, jobTitle: string, jobKind: string, mentorshipRole: string|null, stage: string}>,
 *   isLoading: boolean,
 *   loadError: boolean,
 *   load: () => void,
 *   hasHiredMentorshipApplication: boolean,
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

  const hasHiredMentorshipApplication =
    isLoading || loadError
      ? true
      : applications.some(
          (a) =>
            a.jobKind === "activity" &&
            a.stage === "hired" &&
            (a.mentorshipRole === "mentor" || a.mentorshipRole === "mentee"),
        );

  return { applications, isLoading, loadError, load, hasHiredMentorshipApplication };
};
