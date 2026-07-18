import { Fragment, useCallback, useEffect, useState } from "react";
import { useNavigate, useParams } from "react-router-dom";
import { toast } from "sonner";
import { Button } from "@/components/ui/button";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogFooter,
} from "@/components/ui/dialog";
import { Textarea } from "@/components/ui/textarea";
import { PERMISSIONS } from "@/constants/Permissions";
import { ROUTE_PATHS } from "@/constants/RoutePaths";
import { useAuth } from "@/context/auth/AuthContext";
import {
  getJob,
  listApprovers,
  listJobOwners,
  listInterviewPool,
  listJobActivity,
  listMyReviews,
  submitForReview,
  requestClose,
  requestReopen,
  discardPendingEdit,
  deleteJob,
  decideReview,
} from "@/api/recruitingApi";
import SubmitReviewDialog from "@/pages/Recruiting/components/SubmitReviewDialog";
import PostingStatusBadges from "@/pages/Recruiting/components/PostingStatusBadges";
import PostingConfigSummary from "@/pages/Recruiting/components/PostingConfigSummary";
import PostingApplicantView from "@/pages/Recruiting/components/PostingApplicantView";
import LoadGate from "@/pages/Recruiting/components/LoadGate";

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

/**
 * Unified job posting detail page at `/recruiting/postings/:id`. Visibility
 * is permission-driven, not mode-driven: Overview/Configuration/Review
 * history are shown to every viewer holding any of
 * RECRUITING_JOB_WRITE/RECRUITING_JOB_APPROVE/RECRUITING_JOB_READ. Overview
 * renders the same applicant-facing view used on the live posting
 * (description + profile requirements + question form); Configuration is
 * staff-only rules (pipeline/screening/profile). The write-action
 * "Operate:" block only renders for canWrite (and only when the current
 * status has an available action); within it, "Edit" only
 * shows for the statuses `update_job` actually accepts (DRAFT/PUBLISHED/
 * CLOSED — not PUBLISHED_PENDING_REVISION, which already has a staged
 * edit awaiting its own review). Approve/Reject only for the review's
 * actual assigned reviewer.
 */
const PostingDetailPage = () => {
  const { id } = useParams();
  const navigate = useNavigate();
  const { user, permissions = [] } = useAuth();
  const canWrite = permissions.includes(PERMISSIONS.RECRUITING_JOB_WRITE);
  const canApprove = permissions.includes(PERMISSIONS.RECRUITING_JOB_APPROVE);

  const [job, setJob] = useState(null);
  const [approversById, setApproversById] = useState({});
  const [ownersById, setOwnersById] = useState({});
  const [jobOwners, setJobOwners] = useState([]);
  const [interviewPool, setInterviewPool] = useState([]);
  const [activity, setActivity] = useState([]);
  const [myOpenReview, setMyOpenReview] = useState(null);
  const [loadError, setLoadError] = useState(false);

  const [reviewAction, setReviewAction] = useState(null); // "submit" | "close" | "reopen"
  const [submitOpen, setSubmitOpen] = useState(false);
  const [approvers, setApprovers] = useState([]);
  const [submitting, setSubmitting] = useState(false);
  const [deleteConfirmOpen, setDeleteConfirmOpen] = useState(false);
  const [deleting, setDeleting] = useState(false);
  const [discardConfirmOpen, setDiscardConfirmOpen] = useState(false);
  const [discarding, setDiscarding] = useState(false);
  const [rejectComment, setRejectComment] = useState("");
  const [deciding, setDeciding] = useState(false);

  const load = useCallback(() => {
    setLoadError(false);
    // listMyReviews requires RECRUITING_JOB_APPROVE -- the backend route
    // 403s for anyone without it, so only fetch it for a canApprove viewer.
    // It's how this page learns the *actual* review_id to decide on: JobDto
    // only exposes reviewerId (the assigned user), never the review cycle's
    // own id, and only the assigned reviewer's own listMyReviews() call can
    // see it (mirrors MyReviews.jsx's existing self-scoped fetch).
    Promise.all([
      getJob(id),
      listApprovers(),
      listJobOwners(),
      listInterviewPool(),
      listJobActivity(id),
      canApprove ? listMyReviews() : Promise.resolve({ data: [] }),
    ])
      .then(
        ([
          jobRes,
          approversRes,
          ownersRes,
          interviewPoolRes,
          activityRes,
          myReviewsRes,
        ]) => {
          setJob(jobRes.data);
          setApproversById(
            Object.fromEntries(
              (approversRes.data ?? []).map((a) => [a.userId, a.name]),
            ),
          );
          setOwnersById(
            Object.fromEntries(
              (ownersRes.data ?? []).map((o) => [o.userId, o.name]),
            ),
          );
          setJobOwners(ownersRes.data ?? []);
          setInterviewPool(interviewPoolRes.data ?? []);
          setActivity(activityRes.data ?? []);
          setMyOpenReview(
            (myReviewsRes.data ?? []).find((r) => r.jobId === Number(id)) ??
              null,
          );
        },
      )
      .catch((e) => {
        setLoadError(true);
        toast.error(e.message);
      });
  }, [id, canApprove]);

  useEffect(() => {
    load();
  }, [load]);

  if (!job) {
    return (
      <LoadGate
        error={loadError}
        errorMessage="Couldn't load this posting."
        onRetry={load}
      />
    );
  }

  const isDraft = job.status === "draft";
  const isPublished = job.status === "published";
  const isClosed = job.status === "closed";
  const hasOperateAction = isDraft || isPublished || isClosed;
  // Mirrors JobService.update_job's allowed_from check on the backend:
  // editing is only accepted from DRAFT/PUBLISHED/CLOSED, never from
  // PUBLISHED_PENDING_REVISION (a revision is already staged and pending
  // its own review).
  const canEditConfig = canWrite && (isDraft || isPublished || isClosed);
  const isAssignedReviewer =
    canApprove && myOpenReview != null && job.reviewerId === user?.userId;
  const reviewerName = job.reviewerId
    ? (approversById[job.reviewerId] ?? `Reviewer #${job.reviewerId}`)
    : null;
  const ownerIds = job.pipelineConfig?.ownerIds ?? [];
  /** The staged edit merged onto the live job, or null when nothing is staged. */
  const proposedJob = job.pendingPayload
    ? { ...job, ...job.pendingPayload }
    : null;
  // Mirrors JobService._revalidate_job_config's publish gate: whatever
  // approval would put live (the staged pipeline when an edit is staged,
  // else the live one) needs >=1 stage and >=1 Managed by owner, or every
  // application would land outside all board lanes with no one to see it.
  const effectivePipeline =
    (job.pendingPayload
      ? job.pendingPayload.pipelineConfig
      : job.pipelineConfig) ?? {};
  const effectiveOwnerIds =
    effectivePipeline.ownerIds ??
    (effectivePipeline.ownerId != null ? [effectivePipeline.ownerId] : []);
  const submitBlocker = !effectivePipeline.stages?.length
    ? "Add at least one pipeline stage before submitting for review."
    : effectiveOwnerIds.length === 0
      ? "Add at least one manager (Managed by) before submitting for review."
      : null;

  const formatActivity = (entry) => {
    const { eventType, actorName, details = {} } = entry;
    const reviewerName = details.reviewerId
      ? (approversById[details.reviewerId] ?? `Reviewer #${details.reviewerId}`)
      : null;
    if (eventType === "job_created") {
      return `${actorName} created this posting as a draft`;
    }
    if (eventType === "review_opened") {
      const verb =
        {
          initial: "submitted for review",
          revision: "submitted a revision for review",
          close: "requested to close",
          reopen: "requested to reopen",
        }[details.kind] ?? "submitted for review";
      return reviewerName
        ? `${actorName} ${verb}, assigned to ${reviewerName}`
        : `${actorName} ${verb}`;
    }
    if (eventType === "review_decided") {
      const templates = {
        initial: {
          approved: `${actorName} approved the review — posting published`,
          rejected: `${actorName} rejected the review: "${details.comment}" — sent back to draft`,
        },
        revision: {
          approved: `${actorName} approved the revision — changes published`,
          rejected: `${actorName} rejected the revision: "${details.comment}" — posting stays published`,
        },
        close: {
          approved: `${actorName} approved the close request — posting closed`,
          rejected: `${actorName} rejected the close request: "${details.comment}" — posting stays published`,
        },
        reopen: {
          approved: `${actorName} approved the reopen request — posting republished`,
          rejected: `${actorName} rejected the reopen request: "${details.comment}" — posting stays closed`,
        },
      };
      return (
        templates[details.kind]?.[details.decision] ??
        `${actorName} ${eventType}`
      );
    }
    if (eventType === "pending_edit_discarded") {
      return `${actorName} discarded a staged edit`;
    }
    return `${actorName} ${eventType}`;
  };

  const openReview = async (kind) => {
    try {
      const { data } = await listApprovers();
      setApprovers(data ?? []);
      setReviewAction(kind);
      setSubmitOpen(true);
    } catch (e) {
      toast.error(e.message);
    }
  };

  const handleReviewSubmit = async (body) => {
    if (submitting || !reviewAction) return;
    const action = REVIEW_ACTION[reviewAction];
    setSubmitting(true);
    try {
      await action.dispatch(id, body);
      toast.success(action.successMsg);
      navigate(ROUTE_PATHS.RECRUITING_POSTINGS);
    } catch (e) {
      toast.error(e.message);
      setSubmitting(false);
    }
  };

  const handleDelete = async () => {
    if (deleting) return;
    setDeleting(true);
    try {
      await deleteJob(id);
      toast.success("Posting deleted.");
      window.location.assign(ROUTE_PATHS.RECRUITING_POSTINGS);
    } catch (e) {
      toast.error(e.message);
      setDeleting(false);
    }
  };

  const handleDiscard = async () => {
    if (discarding) return;
    setDiscarding(true);
    try {
      await discardPendingEdit(id);
      toast.success("Staged edit discarded.");
      setDiscardConfirmOpen(false);
      load();
    } catch (e) {
      toast.error(e.message);
    } finally {
      setDiscarding(false);
    }
  };

  const handleApprove = async () => {
    if (deciding || !myOpenReview) return;
    setDeciding(true);
    try {
      await decideReview(myOpenReview.reviewId, { decision: "approve" });
      toast.success("Review approved.");
      load();
    } catch (e) {
      toast.error(e.message);
    } finally {
      setDeciding(false);
    }
  };

  const handleReject = async () => {
    if (deciding || !rejectComment.trim() || !myOpenReview) return;
    setDeciding(true);
    try {
      await decideReview(myOpenReview.reviewId, {
        decision: "reject",
        comment: rejectComment.trim(),
      });
      toast.success("Review rejected.");
      setRejectComment("");
      load();
    } catch (e) {
      toast.error(e.message);
    } finally {
      setDeciding(false);
    }
  };

  return (
    <div className="space-y-6 p-6">
      <div className="space-y-1">
        <div className="flex flex-wrap items-center gap-2">
          <h1 className="text-xl font-semibold text-slate-900">{job.title}</h1>
          <PostingStatusBadges job={job} />
        </div>
        <p className="text-sm text-slate-600">{job.description}</p>
        {ownerIds.length > 0 && (
          <p className="text-sm text-slate-500">
            Managed by:
            {ownerIds.map((oid, i) => (
              <Fragment key={oid}>
                {i === 0 ? " " : ", "}
                {ownersById[oid] == null ? (
                  <span className="text-red-600">
                    {`#${oid} — no permission, remove`}
                  </span>
                ) : (
                  ownersById[oid]
                )}
              </Fragment>
            ))}
          </p>
        )}
        {reviewerName && (
          <p className="text-sm text-slate-500">
            Assigned reviewer: {reviewerName}
          </p>
        )}
      </div>

      {canWrite && hasOperateAction && (
        <div className="flex flex-wrap items-center gap-2">
          <span className="text-sm font-medium text-slate-700">Operate:</span>
          {canEditConfig && (
            <Button
              size="sm"
              variant="outline"
              onClick={() =>
                window.location.assign(ROUTE_PATHS.RECRUITING_POSTING_EDIT(id))
              }
            >
              Edit
            </Button>
          )}
          {isDraft && (
            <>
              <Button
                size="sm"
                disabled={submitBlocker != null}
                onClick={() => openReview("submit")}
              >
                Submit for review
              </Button>
              <Button
                size="sm"
                variant="outline"
                onClick={() => setDeleteConfirmOpen(true)}
              >
                Delete
              </Button>
            </>
          )}
          {isPublished && job.pendingPayload == null && (
            <Button
              size="sm"
              variant="outline"
              onClick={() => openReview("close")}
            >
              Request close
            </Button>
          )}
          {isPublished && job.pendingPayload != null && (
            <>
              <Button
                size="sm"
                disabled={submitBlocker != null}
                onClick={() => openReview("submit")}
              >
                Submit for review
              </Button>
              <Button
                size="sm"
                variant="outline"
                onClick={() => setDiscardConfirmOpen(true)}
              >
                Discard draft
              </Button>
            </>
          )}
          {isClosed && job.wasPublished && (
            <Button
              size="sm"
              variant="outline"
              onClick={() => openReview("reopen")}
            >
              Request reopen
            </Button>
          )}
          {isClosed && job.wasPublished && job.pendingPayload != null && (
            <Button
              size="sm"
              variant="outline"
              onClick={() => setDiscardConfirmOpen(true)}
            >
              Discard draft
            </Button>
          )}
          {isClosed && !job.wasPublished && (
            <Button
              size="sm"
              variant="outline"
              onClick={() => setDeleteConfirmOpen(true)}
            >
              Delete
            </Button>
          )}
          {submitBlocker != null &&
            (isDraft || (isPublished && job.pendingPayload != null)) && (
              <span className="text-xs text-amber-600">{submitBlocker}</span>
            )}
        </div>
      )}

      {isAssignedReviewer && (
        <div className="space-y-2 rounded border p-3">
          <span className="text-sm font-medium text-slate-700">
            Review decision:
          </span>
          <div className="flex gap-2">
            <Button size="sm" disabled={deciding} onClick={handleApprove}>
              Approve
            </Button>
          </div>
          <Textarea
            placeholder="Rejection comment (required to reject)"
            value={rejectComment}
            onChange={(e) => setRejectComment(e.target.value)}
          />
          <Button
            size="sm"
            variant="destructive"
            disabled={!rejectComment.trim() || deciding}
            onClick={handleReject}
          >
            Reject
          </Button>
        </div>
      )}

      <Tabs defaultValue="overview">
        <TabsList>
          <TabsTrigger value="overview">Overview</TabsTrigger>
          <TabsTrigger value="configuration">Configuration</TabsTrigger>
          <TabsTrigger value="history">Review history</TabsTrigger>
        </TabsList>
        <TabsContent value="overview">
          {proposedJob ? (
            <div className="grid grid-cols-1 gap-6 md:grid-cols-2">
              <div className="space-y-2">
                <h3 className="text-sm font-medium text-slate-700">Current</h3>
                <PostingApplicantView
                  title={job.title}
                  description={job.description}
                  questions={job.formSchema?.questions ?? []}
                  profileConfig={job.profileConfig}
                />
              </div>
              <div className="space-y-2">
                <h3 className="text-sm font-medium text-slate-700">Proposed</h3>
                <PostingApplicantView
                  title={proposedJob.title}
                  description={proposedJob.description}
                  questions={proposedJob.formSchema?.questions ?? []}
                  profileConfig={proposedJob.profileConfig}
                />
              </div>
            </div>
          ) : (
            <PostingApplicantView
              description={job.description}
              questions={job.formSchema?.questions ?? []}
              profileConfig={job.profileConfig}
            />
          )}
        </TabsContent>
        <TabsContent value="configuration">
          {proposedJob ? (
            <div className="grid grid-cols-1 gap-6 md:grid-cols-2">
              <div className="space-y-2">
                <h3 className="text-sm font-medium text-slate-700">Current</h3>
                <PostingConfigSummary
                  job={job}
                  interviewPool={interviewPool}
                  jobOwners={jobOwners}
                />
              </div>
              <div className="space-y-2">
                <h3 className="text-sm font-medium text-slate-700">Proposed</h3>
                <PostingConfigSummary
                  job={proposedJob}
                  interviewPool={interviewPool}
                  jobOwners={jobOwners}
                />
              </div>
            </div>
          ) : (
            <PostingConfigSummary
              job={job}
              interviewPool={interviewPool}
              jobOwners={jobOwners}
            />
          )}
        </TabsContent>
        <TabsContent value="history">
          {activity.length === 0 ? (
            <p className="text-sm text-slate-400">No activity yet.</p>
          ) : (
            <ul className="space-y-1">
              {activity.map((entry) => (
                <li key={entry.id} className="text-sm text-slate-700">
                  <span className="text-slate-500">
                    {new Date(entry.createdAt).toLocaleString()}
                  </span>{" "}
                  — {formatActivity(entry)}
                </li>
              ))}
            </ul>
          )}
        </TabsContent>
      </Tabs>

      <SubmitReviewDialog
        open={submitOpen}
        approvers={approvers}
        currentUserId={user?.userId}
        title={
          reviewAction ? REVIEW_ACTION[reviewAction].title : "Submit for review"
        }
        submitting={submitting}
        onSubmit={handleReviewSubmit}
        onOpenChange={setSubmitOpen}
      />

      <Dialog
        open={deleteConfirmOpen}
        onOpenChange={(o) => !o && setDeleteConfirmOpen(false)}
      >
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Delete this posting?</DialogTitle>
          </DialogHeader>
          <p className="text-sm text-slate-600">This cannot be undone.</p>
          <DialogFooter>
            <Button
              variant="outline"
              onClick={() => setDeleteConfirmOpen(false)}
            >
              Cancel
            </Button>
            <Button
              variant="destructive"
              disabled={deleting}
              onClick={handleDelete}
            >
              Delete
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      <Dialog
        open={discardConfirmOpen}
        onOpenChange={(o) => !o && setDiscardConfirmOpen(false)}
      >
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Discard your staged edit?</DialogTitle>
          </DialogHeader>
          <p className="text-sm text-slate-600">
            This discards your staged edit; the live posting is unaffected.
          </p>
          <DialogFooter>
            <Button
              variant="outline"
              onClick={() => setDiscardConfirmOpen(false)}
            >
              Cancel
            </Button>
            <Button
              variant="destructive"
              disabled={discarding}
              onClick={handleDiscard}
            >
              Confirm discard
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
};

export default PostingDetailPage;
