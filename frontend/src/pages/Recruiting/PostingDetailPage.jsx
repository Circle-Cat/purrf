import { useCallback, useEffect, useState } from "react";
import { useNavigate, useParams } from "react-router-dom";
import { toast } from "sonner";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import {
  Popover,
  PopoverContent,
  PopoverTrigger,
} from "@/components/ui/popover";
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
  deleteJob,
  decideReview,
} from "@/api/recruitingApi";
import SubmitReviewDialog from "@/pages/Recruiting/components/SubmitReviewDialog";
import PostingConfigSummary from "@/pages/Recruiting/components/PostingConfigSummary";
import PostingApplicantView from "@/pages/Recruiting/components/PostingApplicantView";
import LoadGate from "@/pages/Recruiting/components/LoadGate";

/** Human labels + badge variants per JobStatus (mirrors PostingsList). */
const STATUS_LABELS = {
  draft: "Draft",
  pending_review: "Pending review",
  published: "Published",
  published_pending_revision: "Revision pending review",
  pending_close: "Pending close",
  pending_reopen: "Pending reopen",
  closed: "Closed",
};

const STATUS_VARIANT = {
  draft: "secondary",
  pending_review: "outline",
  published: "default",
  published_pending_revision: "outline",
  pending_close: "outline",
  pending_reopen: "outline",
  closed: "secondary",
};

const REJECT_KIND_LABEL = {
  initial: "Initial submission rejected",
  revision: "Revision rejected",
  close: "Close request rejected",
  reopen: "Reopen request rejected",
};

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
  const isPendingRevision = job.status === "published_pending_revision";
  const isClosed = job.status === "closed";
  const hasOperateAction =
    isDraft || isPublished || isPendingRevision || isClosed;
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
  const ownerNames = (job.pipelineConfig?.ownerIds ?? [])
    .map((oid) => ownersById[oid] ?? `User ${oid}`)
    .join(", ");

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
          rejected: `${actorName} rejected the revision: "${details.comment}" — changes discarded`,
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
          <Badge variant={STATUS_VARIANT[job.status]}>
            {STATUS_LABELS[job.status]}
          </Badge>
          {job.lastRejectComment && (
            <Popover>
              <PopoverTrigger asChild>
                <button type="button" className="cursor-pointer">
                  <Badge variant="destructive">
                    {REJECT_KIND_LABEL[job.lastRejectKind] ?? "Sent back"}
                  </Badge>
                </button>
              </PopoverTrigger>
              <PopoverContent className="w-72">
                <p className="text-sm font-medium text-slate-700">
                  {REJECT_KIND_LABEL[job.lastRejectKind] ?? "Rejected"}
                </p>
                <p className="text-sm text-red-600">{job.lastRejectComment}</p>
              </PopoverContent>
            </Popover>
          )}
        </div>
        <p className="text-sm text-slate-600">{job.description}</p>
        {ownerNames && (
          <p className="text-sm text-slate-500">Managed by: {ownerNames}</p>
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
              <Button size="sm" onClick={() => openReview("submit")}>
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
          {isPublished && (
            <Button
              size="sm"
              variant="outline"
              onClick={() => openReview("close")}
            >
              Request close
            </Button>
          )}
          {isPendingRevision && (
            <Button size="sm" onClick={() => openReview("submit")}>
              Submit for review
            </Button>
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
          {isClosed && !job.wasPublished && (
            <Button
              size="sm"
              variant="outline"
              onClick={() => setDeleteConfirmOpen(true)}
            >
              Delete
            </Button>
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
          <PostingApplicantView
            description={job.description}
            questions={job.formSchema?.questions ?? []}
            profileConfig={job.profileConfig}
          />
        </TabsContent>
        <TabsContent value="configuration">
          <PostingConfigSummary
            job={job}
            interviewPool={interviewPool}
            jobOwners={jobOwners}
          />
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
    </div>
  );
};

export default PostingDetailPage;
