import { useCallback, useEffect, useMemo, useState } from "react";
import { useNavigate } from "react-router-dom";
import { toast } from "sonner";
import { Button } from "@/components/ui/button";
import { Checkbox } from "@/components/ui/checkbox";
import { Label } from "@/components/ui/label";
import { useAuth } from "@/context/auth/AuthContext";
import { PERMISSIONS } from "@/constants/Permissions";
import { listJobs, listJobOwners, listMyReviews } from "@/api/recruitingApi";
import { ROUTE_PATHS } from "@/constants/RoutePaths";
import PostingsList from "@/pages/Recruiting/components/PostingsList";
import ReviewQueue from "@/pages/Recruiting/components/ReviewQueue";
import SectionCard from "@/pages/Recruiting/components/SectionCard";

/**
 * Job Postings page: a card of the postings waiting on the viewer's review
 * (approvers only), then a card of all postings with status + Recruiter and a
 * click-through to the unified detail page.
 */
const Postings = () => {
  const { user, permissions = [] } = useAuth();
  const canWrite = permissions.includes(PERMISSIONS.RECRUITING_JOB_WRITE);
  const canApprove = permissions.includes(PERMISSIONS.RECRUITING_JOB_APPROVE);
  const navigate = useNavigate();
  const [jobs, setJobs] = useState([]);
  const [ownersById, setOwnersById] = useState({});
  const [myPostingsOnly, setMyPostingsOnly] = useState(false);
  const [reviews, setReviews] = useState([]);

  const refresh = useCallback(async () => {
    const { data } = await listJobs();
    setJobs(data ?? []);
  }, []);

  const loadOwners = useCallback(async () => {
    const { data } = await listJobOwners();
    setOwnersById(
      Object.fromEntries((data ?? []).map((o) => [o.userId, o.name])),
    );
  }, []);

  // The reviews route 403s without job.approve, and a job.read or job.write
  // viewer has no reviews anyway.
  const loadReviews = useCallback(async () => {
    if (!canApprove) return;
    const { data } = await listMyReviews();
    setReviews(data ?? []);
  }, [canApprove]);

  useEffect(() => {
    refresh().catch((e) => toast.error(e.message));
    loadOwners().catch((e) => toast.error(e.message));
    loadReviews().catch((e) => toast.error(e.message));
  }, [refresh, loadOwners, loadReviews]);

  const visibleJobs = useMemo(() => {
    if (!myPostingsOnly) return jobs;
    return jobs.filter((j) =>
      (j.pipelineConfig?.ownerIds ?? []).includes(user?.userId),
    );
  }, [jobs, myPostingsOnly, user?.userId]);

  return (
    <div className="space-y-6 p-6">
      <h1 className="text-xl font-semibold text-slate-900">Job Postings</h1>
      <ReviewQueue
        reviews={reviews}
        onOpen={(review) =>
          navigate(ROUTE_PATHS.RECRUITING_POSTING_DETAIL(review.jobId))
        }
      />
      {/* New posting sits in the card header, not under the list: starting a
          new posting has nothing to do with what is on the page, so it should
          not be somewhere the reader has to scroll a long list of postings to
          reach. */}
      <SectionCard
        title="Postings"
        right={
          <>
            <div className="flex items-center gap-2">
              <Checkbox
                id="my-postings"
                checked={myPostingsOnly}
                onCheckedChange={(checked) =>
                  setMyPostingsOnly(Boolean(checked))
                }
              />
              <Label htmlFor="my-postings">I&apos;m the recruiter</Label>
            </div>
            <Button
              size="sm"
              disabled={!canWrite}
              onClick={() => navigate(ROUTE_PATHS.RECRUITING_POSTING_NEW)}
            >
              New posting
            </Button>
          </>
        }
      >
        <PostingsList
          jobs={visibleJobs}
          ownersById={ownersById}
          onRowClick={(job) =>
            navigate(ROUTE_PATHS.RECRUITING_POSTING_DETAIL(job.id))
          }
        />
      </SectionCard>
    </div>
  );
};

export default Postings;
