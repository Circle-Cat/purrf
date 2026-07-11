import { useCallback, useEffect, useMemo, useState } from "react";
import { useNavigate } from "react-router-dom";
import { toast } from "sonner";
import { Button } from "@/components/ui/button";
import { Checkbox } from "@/components/ui/checkbox";
import { Label } from "@/components/ui/label";
import { useAuth } from "@/context/auth/AuthContext";
import { listJobs, listJobOwners } from "@/api/recruitingApi";
import { ROUTE_PATHS } from "@/constants/RoutePaths";
import PostingsList from "@/pages/Recruiting/components/PostingsList";
import HowItWorksDialog from "@/pages/Recruiting/components/HowItWorksDialog";
import { POSTINGS_GUIDE } from "@/pages/Recruiting/components/guideContent";

/** Postings browse page: status + Managed-by list, click-through to the unified detail page. */
const Postings = () => {
  const { user } = useAuth();
  const navigate = useNavigate();
  const [jobs, setJobs] = useState([]);
  const [ownersById, setOwnersById] = useState({});
  const [myPostingsOnly, setMyPostingsOnly] = useState(false);

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

  useEffect(() => {
    refresh().catch((e) => toast.error(e.message));
    loadOwners().catch((e) => toast.error(e.message));
  }, [refresh, loadOwners]);

  const visibleJobs = useMemo(() => {
    if (!myPostingsOnly) return jobs;
    return jobs.filter((j) =>
      (j.pipelineConfig?.ownerIds ?? []).includes(user?.userId),
    );
  }, [jobs, myPostingsOnly, user?.userId]);

  return (
    <div className="space-y-4 p-6">
      <div className="flex items-center justify-between">
        <h1 className="text-xl font-semibold text-slate-900">Postings</h1>
        <div className="flex items-center gap-2">
          <HowItWorksDialog {...POSTINGS_GUIDE} />
          <Button onClick={() => navigate(ROUTE_PATHS.RECRUITING_POSTING_NEW)}>
            New posting
          </Button>
        </div>
      </div>
      <div className="flex items-center gap-2">
        <Checkbox
          id="my-postings"
          checked={myPostingsOnly}
          onCheckedChange={(checked) => setMyPostingsOnly(Boolean(checked))}
        />
        <Label htmlFor="my-postings">My postings</Label>
      </div>
      <PostingsList
        jobs={visibleJobs}
        ownersById={ownersById}
        onRowClick={(job) =>
          navigate(ROUTE_PATHS.RECRUITING_POSTING_DETAIL(job.id))
        }
      />
    </div>
  );
};

export default Postings;
