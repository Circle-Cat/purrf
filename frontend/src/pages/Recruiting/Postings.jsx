import { useCallback, useEffect, useMemo, useState } from "react";
import { useNavigate } from "react-router-dom";
import { toast } from "sonner";
import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogFooter,
} from "@/components/ui/dialog";
import { useAuth } from "@/context/auth/AuthContext";
import {
  listJobs,
  closeJob,
  listApprovers,
  submitForReview,
  requestClose,
  requestReopen,
  deleteJob,
} from "@/api/recruitingApi";
import { ROUTE_PATHS } from "@/constants/RoutePaths";
import PostingsList from "@/pages/Recruiting/components/PostingsList";
import PostingPreviewPage from "@/pages/Recruiting/components/PostingPreviewPage";
import SubmitReviewDialog from "@/pages/Recruiting/components/SubmitReviewDialog";
import HowItWorksDialog from "@/pages/Recruiting/components/HowItWorksDialog";
import { POSTINGS_GUIDE } from "@/pages/Recruiting/components/guideContent";

/** Title and dispatch fn per review action kind. */
const REVIEW_ACTION = {
  submit: {
    title: "Submit for review",
    dispatch: (jobId, body) => submitForReview(jobId, body),
    successMsg: "Submitted for review.",
  },
  close: {
    title: "Request close",
    dispatch: (jobId, body) => requestClose(jobId, body),
    successMsg: "Close requested.",
  },
  reopen: {
    title: "Request reopen",
    dispatch: (jobId, body) => requestReopen(jobId, body),
    successMsg: "Reopen requested.",
  },
};

/** Postings management page: lifecycle + review submission. */
const Postings = () => {
  const { user } = useAuth();
  const navigate = useNavigate();
  const [jobs, setJobs] = useState([]);
  const [submitOpen, setSubmitOpen] = useState(false);
  const [reviewAction, setReviewAction] = useState(null); // { kind, jobId }
  const [approvers, setApprovers] = useState([]);
  const [previewJob, setPreviewJob] = useState(null);
  const [deleteId, setDeleteId] = useState(null);
  const [closingId, setClosingId] = useState(null);
  const [submitting, setSubmitting] = useState(false);

  const refresh = useCallback(async () => {
    const { data } = await listJobs();
    setJobs(data ?? []);
  }, []);

  /** Fetch active approvers and store them for the reviewer picker and the assignee lookup. */
  const loadApprovers = useCallback(async () => {
    const { data } = await listApprovers();
    setApprovers(data ?? []);
  }, []);

  useEffect(() => {
    refresh().catch((e) => toast.error(e.message));
    loadApprovers().catch((e) => toast.error(e.message));
  }, [refresh, loadApprovers]);

  /** userId -> name lookup for rendering "Assigned to" against a job's reviewerId. */
  const approversById = useMemo(
    () => Object.fromEntries(approvers.map((a) => [a.userId, a.name])),
    [approvers],
  );

  /**
   * Generic helper: run an async fn, refresh the list, show a success toast.
   * On error, shows an error toast.
   *
   * @param {() => Promise<unknown>} fn
   * @param {string} ok  Success message
   */
  const run = async (fn, ok) => {
    try {
      await fn();
      await refresh();
      toast.success(ok);
    } catch (e) {
      toast.error(e.message);
    }
  };

  /**
   * Open the review dialog for a given kind (submit | close | reopen).
   * Fetches the approver list first so the dialog is always current.
   *
   * @param {number} jobId
   * @param {"submit"|"close"|"reopen"} kind
   */
  const openReview = async (jobId, kind) => {
    try {
      await loadApprovers();
      setReviewAction({ kind, jobId });
      setSubmitOpen(true);
    } catch (e) {
      toast.error(e.message);
    }
  };

  /** Submit the review dialog, guarded against a double-submit; closes the dialog only on success. */
  const handleReviewSubmit = async (body) => {
    if (submitting || !reviewAction) return;
    const { kind, jobId } = reviewAction;
    const action = REVIEW_ACTION[kind];
    setSubmitting(true);
    try {
      await action.dispatch(jobId, body);
      setSubmitOpen(false);
      await refresh();
      toast.success(action.successMsg);
    } catch (e) {
      toast.error(e.message);
    } finally {
      setSubmitting(false);
    }
  };

  /** Close a draft posting, guarded against a double-submit per job id. */
  const handleCloseJob = (id) => {
    if (closingId != null) return;
    setClosingId(id);
    run(() => closeJob(id), "Posting closed.").finally(() =>
      setClosingId(null),
    );
  };

  const askDelete = (id) => setDeleteId(id);

  const confirmDelete = () => {
    const id = deleteId;
    setDeleteId(null);
    run(() => deleteJob(id), "Posting deleted.");
  };

  const currentTitle = reviewAction
    ? REVIEW_ACTION[reviewAction.kind].title
    : "Submit for review";

  if (previewJob) {
    return (
      <PostingPreviewPage job={previewJob} onBack={() => setPreviewJob(null)} />
    );
  }

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
      <PostingsList
        jobs={jobs}
        approversById={approversById}
        closingId={closingId}
        onEdit={(job) => navigate(ROUTE_PATHS.RECRUITING_POSTING_EDIT(job.id))}
        onSubmit={(id) => openReview(id, "submit")}
        onClose={handleCloseJob}
        onRequestClose={(id) => openReview(id, "close")}
        onRequestReopen={(id) => openReview(id, "reopen")}
        onDelete={askDelete}
        onView={(job) => setPreviewJob(job)}
      />
      <SubmitReviewDialog
        open={submitOpen}
        approvers={approvers}
        currentUserId={user?.userId}
        title={currentTitle}
        submitting={submitting}
        onSubmit={handleReviewSubmit}
        onOpenChange={setSubmitOpen}
      />
      <Dialog open={!!deleteId} onOpenChange={(o) => !o && setDeleteId(null)}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Delete this posting?</DialogTitle>
          </DialogHeader>
          <p className="text-sm text-slate-600">This cannot be undone.</p>
          <DialogFooter>
            <Button variant="outline" onClick={() => setDeleteId(null)}>
              Cancel
            </Button>
            <Button variant="destructive" onClick={confirmDelete}>
              Delete
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
};

export default Postings;
