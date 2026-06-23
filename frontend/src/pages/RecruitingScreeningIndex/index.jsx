import { useState, useEffect } from "react";
import { Link } from "react-router-dom";
import { Card, CardHeader, CardTitle, CardContent } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { getJobs } from "@/api/recruitingApi";

/**
 * RecruitingScreeningIndex
 *
 * Landing page for screeners. Lists all published job postings so that a
 * user with only `RECRUITING_APPLICATION_READ` (no `RECRUITING_JOB_READ`) can
 * navigate to a specific board without being redirected to access-denied.
 *
 * Each job card links to `/recruiting/screening/<id>`.
 *
 * Route: /recruiting/screening  (gated on RECRUITING_APPLICATION_READ in App.jsx)
 *
 * @returns {JSX.Element}
 */
const RecruitingScreeningIndex = () => {
  const [jobs, setJobs] = useState([]);
  const [isLoading, setIsLoading] = useState(true);

  useEffect(() => {
    let cancelled = false;
    getJobs()
      .then((res) => {
        if (!cancelled) setJobs(res.data);
      })
      .finally(() => {
        if (!cancelled) setIsLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, []);

  return (
    <div className="recruiting-screening-index">
      <Card className="border-gray-200 shadow-sm">
        <CardHeader>
          <CardTitle>Recruiting Screening</CardTitle>
        </CardHeader>

        <CardContent>
          {isLoading ? (
            <div className="py-10 text-center text-gray-500">
              Loading postings…
            </div>
          ) : jobs.length === 0 ? (
            <div className="text-center py-8 text-gray-500">
              No published postings available.
            </div>
          ) : (
            <div className="space-y-3">
              {jobs.map((job) => (
                <JobCard key={job.id} job={job} />
              ))}
            </div>
          )}
        </CardContent>
      </Card>
    </div>
  );
};

/**
 * A single job card showing the posting title and mentorship role, linking to
 * that job's screening board.
 *
 * @param {Object} props
 * @param {Object} props.job - The job posting to display.
 * @param {number} props.job.id - Job posting ID.
 * @param {string} props.job.title - Job posting title.
 * @param {string} props.job.mentorshipRole - "mentor" or "mentee".
 */
function JobCard({ job }) {
  return (
    <Link
      to={`/recruiting/screening/${job.id}`}
      className="flex items-center justify-between rounded-lg border px-4 py-3 gap-4 hover:bg-accent transition-colors"
    >
      <span className="font-medium truncate">{job.title}</span>
      <Badge variant="secondary" className="shrink-0 capitalize">
        {job.mentorshipRole}
      </Badge>
    </Link>
  );
}

export default RecruitingScreeningIndex;
