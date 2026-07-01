import { useCallback, useEffect, useState } from "react";
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

  const refresh = useCallback(async () => {
    const { data } = await listJobs();
    setJobs(data ?? []);
  }, []);

  useEffect(() => {
    refresh().catch((e) => toast.error(e.message));
  }, [refresh]);

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
      const { data } = await listApprovers();
      setApprovers(data ?? []);
      setReviewAction({ kind, jobId });
      setSubmitOpen(true);
    } catch (e) {
      toast.error(e.message);
    }
  };

  const handleReviewSubmit = (body) => {
    setSubmitOpen(false);
    if (!reviewAction) return;
    const { kind, jobId } = reviewAction;
    const action = REVIEW_ACTION[kind];
    run(() => action.dispatch(jobId, body), action.successMsg);
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
        <Button onClick={() => navigate(ROUTE_PATHS.RECRUITING_POSTING_NEW)}>
          New posting
        </Button>
      </div>
      <PostingsList
        jobs={jobs}
        onEdit={(job) => navigate(ROUTE_PATHS.RECRUITING_POSTING_EDIT(job.id))}
        onSubmit={(id) => openReview(id, "submit")}
        onClose={(id) => run(() => closeJob(id), "Posting closed.")}
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
