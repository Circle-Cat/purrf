import { useCallback, useEffect, useRef, useState } from "react";
import { useLocation, useNavigate } from "react-router-dom";
import { ArrowUpRight, Bell, X } from "lucide-react";
import { toast } from "sonner";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import {
  Popover,
  PopoverContent,
  PopoverTrigger,
} from "@/components/ui/popover";
import {
  dismissAllNotifications,
  dismissNotification,
  listNotifications,
  markAllNotificationsRead,
  markNotificationsRead,
} from "@/api/recruitingApi";
import { LEAVE_TYPE_LABELS } from "@/constants/LeaveRequest";
import { serviceOf } from "@/pages/Inbox/inboxDisplay";
import { formatBusinessRange } from "@/pages/Leave/utils/leaveDates";
import { stageLabel } from "@/pages/MentorshipManagement/components/email/emailLabels";

/**
 * What a mentorship approval asks for, from its event's details.
 * @param {{action?: string, roundName?: string, personName?: string,
 *          mentorName?: string, menteeName?: string}} details
 * @returns {string}
 */
const approvalAsk = (details) => {
  const round = details?.roundName?.trim();
  if (details?.action === "exempt_matching") {
    const person = details?.personName?.trim() || "someone";
    return `exempt ${person} from the matching history check${round ? ` in ${round}` : ""}`;
  }
  if (details?.action === "withdraw_participant") {
    const person = details?.personName?.trim() || "someone";
    return `withdraw ${person} from ${round || "their round"}`;
  }
  if (details?.action === "mark_no_show") {
    const person = details?.personName?.trim() || "someone";
    return `mark ${person} as a no show${round ? ` in ${round}` : ""}`;
  }
  if (details?.action === "mark_red_flag") {
    const person = details?.personName?.trim() || "someone";
    return `raise a red flag on ${person}${round ? ` in ${round}` : ""}`;
  }
  if (details?.action === "end_pair") {
    const mentor = details?.mentorName?.trim() || "someone";
    const mentee = details?.menteeName?.trim() || "someone";
    return `end the pair of mentor ${mentor} and mentee ${mentee}${round ? ` in ${round}` : ""}`;
  }
  if (details?.action === "publish_matching") {
    return `publish the matching result${round ? ` for ${round}` : ""}`;
  }
  return "a mentorship change";
};

/**
 * What a leave request was for, from its event's details: "paid leave, Nov 3
 * – Nov 5, 2026".
 * @param {{leaveType?: string, startDate?: string, endDate?: string}} details
 * @returns {string}
 */
const leaveAsk = (details) => {
  const what = (LEAVE_TYPE_LABELS[details?.leaveType] ?? "leave").toLowerCase();
  const when = formatBusinessRange(details?.startDate, details?.endDate);
  return when ? `${what}, ${when}` : what;
};

/**
 * The line shown for a notification nothing else words: an event type the
 * bell has no case for, or a case that cannot word this one. Never blank.
 */
const FALLBACK_LINE = "You have a new notification";

/**
 * Word a notification from its event type and details, or "" when it can't.
 *
 * Two audiences share this switch. Every recruiting line is written from
 * staff's point of view, about someone else ("{actor} moved {applicant}");
 * the mentorship lines below are written to the person they are about. Match
 * the case you are adding, not the surrounding voice.
 */
const wordOf = (n) => {
  // `||`, not `??`: actorName carries three states. A name renders as
  // itself, null means the system acted under its own rules (those lines
  // never read this value), and "" means a person acted but their user row
  // no longer resolves -- which still reads as "Someone", not as a blank.
  const actor = n.actorName || "Someone";
  switch (n.eventType) {
    case "mentorship.mentor_admitted":
      return `You were admitted to ${n.jobTitle}`;
    // Told to the admin who started the run. The round is a mentorship round,
    // not a posting, so the name comes from details and jobTitle is blank.
    case "mentorship.matching_run_completed": {
      const round = n.details?.roundName?.trim();
      const started = `The matching run you started${round ? ` for ${round}` : ""}`;
      return n.details?.status === "failed"
        ? `${started} did not finish`
        : `${started} has finished`;
    }
    // Told to the admin who created a Kit send, once Kit has it scheduled or
    // preparing gave up. Subject type is the send, so everything is in details.
    case "mentorship.email_send_prepared": {
      const what = [
        n.details?.stage ? stageLabel(n.details.stage) : "",
        n.details?.roundName?.trim() ?? "",
      ]
        .filter(Boolean)
        .join(" · ");
      if (n.details?.status === "scheduled") {
        return `Kit email scheduled${what ? `: ${what}` : ""}`;
      }
      return `Kit email not scheduled${what ? `: ${what}` : ""} — ${
        n.details?.mayStillBeScheduled
          ? "check Kit, it may still be sent"
          : "no email was sent"
      }`;
    }
    // Mentorship approval requests: told to the reviewer named, the new one
    // on a handover, the raiser when it is decided and the reviewer when it is
    // withdrawn. What is asked for comes from details.
    case "mentorship.approval_requested":
      return `${actor} asked you to approve: ${approvalAsk(n.details)}`;
    case "mentorship.approval_reassigned":
      return `${actor} moved to you a request to approve: ${approvalAsk(n.details)}`;
    case "mentorship.approval_decided": {
      const ask = approvalAsk(n.details);
      switch (n.details?.decision) {
        case "approved":
          return `${actor} approved your request: ${ask}`;
        case "rejected":
          return `${actor} rejected your request: ${ask}`;
        case "withdrawn":
          return `${actor} withdrew the request: ${ask}`;
        default:
          return "";
      }
    }
    // Leave requests: the manager is told one was filed or withdrawn, the
    // employee how it was decided. What it was for comes from details.
    case "leave.request_submitted":
      return `${actor} asked for ${leaveAsk(n.details)}`;
    case "leave.request_decided":
      switch (n.details?.decision) {
        case "approved":
          return `${actor} approved your ${leaveAsk(n.details)}`;
        case "rejected":
          return `${actor} rejected your ${leaveAsk(n.details)}`;
        case "withdrawn":
          return `${actor} withdrew their request for ${leaveAsk(n.details)}`;
        default:
          return "";
      }
    // Told to ops.maintain holders; the kind comes from details.
    case "ops.gmail_sync_alert":
      return `Gmail sync needs attention: ${(n.details?.kind ?? "unknown").replaceAll("_", " ")}`;
    // Told to whoever can handle that service's Inbox threads, for new mail
    // or for a thread moved in from another service.
    case "inbox.needs_reply": {
      const subject = n.details?.subject || "(no subject)";
      return n.details?.movedFrom
        ? `${actor} transferred an email from ${serviceOf(n.details.movedFrom).label} that needs a reply: ${subject}`
        : `New email needs a reply: ${subject}`;
    }
    // Told to the person who sent the email that bounced.
    case "inbox.bounced":
      return n.details?.bouncedTo
        ? `Your email to ${n.details.bouncedTo} was not delivered`
        : "Your email was not delivered";
    // Told to whoever wrote into the thread through Purrf, else every
    // mentorship admin writer.
    case "mentorship.email_received": {
      const who = n.details?.personName?.trim() || "A participant";
      const round = n.details?.roundName?.trim();
      const subject = n.details?.subject || "(no subject)";
      return `${who} replied by email${round ? ` (${round})` : ""}: ${subject}`;
    }
    // Told to whoever wrote into the thread.
    case "mentorship.email_bounced": {
      const subject = n.details?.subject || "(no subject)";
      return n.details?.bouncedTo
        ? `Your email to ${n.details.bouncedTo} about ${subject} was not delivered`
        : `Your email about ${subject} was not delivered`;
    }
    // Told to the posting owners as well as the evaluator, so it cannot say
    // "you".
    case "recruiting.reassigned":
      return `${actor} assigned an evaluator for ${n.applicantName} — ${n.jobTitle}`;
    case "recruiting.auto_assigned":
      return `You were auto-assigned to evaluate ${n.applicantName} — ${n.jobTitle}`;
    case "recruiting.mentioned":
      return `${actor} mentioned you in a comment on ${n.applicantName} — ${n.jobTitle}`;
    // Goes to whoever sent into the thread, or the job owners when nobody has.
    // The reply may come from someone on CC, so the line names the application
    // rather than who wrote.
    case "recruiting.email_received":
      return `New reply on the email thread about ${n.applicantName} — ${n.jobTitle}`;
    // Told to the same people as a reply: it is their message that failed.
    case "recruiting.email_bounced":
      return `Your email about ${n.applicantName} — ${n.jobTitle} could not be delivered`;
    // Posting reviews are worded by the backend from the same phrases as
    // their email, so the two channels say the same thing. The opened and
    // reassigned lines go to the reviewer, the decided ones to the submitter
    // (withdrawn to the reviewer it was waiting on).
    case "recruiting.review_opened":
    case "recruiting.review_reassigned":
    case "recruiting.review_decided":
      return n.summary ?? "";
    case "recruiting.application_submitted":
      return n.details?.screenAutoHireRuleId
        ? `${n.applicantName} applied to ${n.jobTitle} and was ${
            n.jobKind === "activity" ? "admitted" : "hired"
          } automatically`
        : `${n.applicantName} applied to ${n.jobTitle}`;
    case "recruiting.auto_rejected":
      return `${n.applicantName} applied to ${n.jobTitle} and was rejected automatically`;
    case "recruiting.blacklisted":
      return `${actor} blacklisted ${n.applicantName} — ${n.jobTitle}`;
    case "recruiting.stage_changed":
      return `${actor} moved ${n.applicantName} to a new stage — ${n.jobTitle}`;
    case "recruiting.round_advanced":
      return `${actor} advanced ${n.applicantName} to another session — ${n.jobTitle}`;
    case "recruiting.sub_status_changed":
      return `${actor} changed the status of ${n.applicantName} — ${n.jobTitle}`;
    case "recruiting.evaluation_confirmed":
      return `${actor} confirmed an evaluation for ${n.applicantName} — ${n.jobTitle}`;
    case "recruiting.interview_scheduled":
      return `${actor} scheduled an interview with ${n.applicantName} — ${n.jobTitle}`;
    case "recruiting.interview_updated":
      return `${actor} changed the interview with ${n.applicantName} — ${n.jobTitle}`;
    case "recruiting.interview_cancelled":
      return `${actor} cancelled the interview with ${n.applicantName} — ${n.jobTitle}`;
    // The block-request lines are about a person, not an application, so they
    // read subjectName and never jobTitle/applicantName, which are always
    // blank here. Their audiences differ per case: the reviewer is told a
    // request arrived, the raiser is told how it ended.
    case "user.block_requested":
      return `${actor} asked you to block ${n.subjectName}`;
    case "user.block_request_reassigned":
      // One line for two audiences -- the reviewer it left and the one it
      // reached. Neither is named, because the row carries only the actor.
      return `${actor} reassigned the block request about ${n.subjectName}`;
    case "user.block_request_decided":
      // The raiser is told a decision; the reviewer is told a withdrawal;
      // both are told when a direct block closed it undecided.
      if (n.details?.decision === "withdrawn") {
        return `${actor} withdrew the block request about ${n.subjectName}`;
      }
      if (n.details?.decision === "superseded") {
        return `${actor} blocked ${n.subjectName} directly, closing the block request about them`;
      }
      return n.details?.decision === "approved"
        ? `${actor} approved the block request you raised about ${n.subjectName}`
        : `${actor} rejected the block request you raised about ${n.subjectName}`;
    default:
      return "";
  }
};

/**
 * Compose a notification's display text, falling back to a generic line so
 * a row is never blank.
 * @param {object} n The notification.
 * @returns {string}
 */
const describe = (n) => wordOf(n) || FALLBACK_LINE;

/**
 * Header bell + popover for in-app recruiting notifications.
 *
 * Clicking an unread row marks it read on the server and goes nowhere. A row
 * whose notification has a `link` (an app path the backend worked out for
 * this reader) also gets an Open button: it marks the row read the same way,
 * closes the panel and navigates there. "Mark all as read"
 * marks every one, including any beyond the rows listed. Read rows stay
 * listed in grey, below the unread ones, and the badge counts only unread
 * rows. Dismissing one (the X) or "Clear all" takes it off the list.
 *
 * Refetches on three user-driven triggers: the tab/window becoming visible
 * again, a route pathname change, and the panel opening. The bell lives in
 * Header, which sits inside <Router> but outside <Routes>, so navigating never
 * remounts it -- without these triggers it would only update on a full page
 * reload.
 *
 * There is deliberately no timer and no SSE/WebSocket here. Polling was
 * rejected because the only case these three triggers miss is a user sitting
 * on an idle page touching nothing, and a timer adds a period to tune where
 * these add no parameters; SSE was deferred until the Cloudflare tunnel is
 * proven not to buffer and replicas > 1 is handled. Reasoning in full:
 * docs/superpowers/specs/2026-08-05-notification-bell-refresh-design.md.
 * Please don't "fix" this by adding setInterval.
 */
const NotificationBell = () => {
  const [notifications, setNotifications] = useState([]);
  const [unreadCount, setUnreadCount] = useState(0);
  const [loadError, setLoadError] = useState(false);
  const [open, setOpen] = useState(false);
  const { pathname } = useLocation();
  const navigate = useNavigate();

  // The fetch in progress, if any. Set synchronously before the first await:
  // visibilitychange and focus both fire when returning to a hidden tab, and
  // state would batch them into two requests. A caller arriving mid-fetch
  // shares this one instead of starting another.
  const inFlight = useRef(null);
  // Bumped by every write (dismiss, Clear all, mark read) so a refetch that
  // raced it drops its response instead of resurrecting a removed row or an
  // old count.
  const mutations = useRef(0);
  const isFirstLoad = useRef(true);

  /**
   * Fetch the list and the unread count, or join the fetch already running.
   * @param {{showToast: boolean}} options
   * @returns {Promise<object[]|null>} The rows fetched, or null when the
   *   fetch failed or a write raced it.
   */
  const load = useCallback(({ showToast }) => {
    if (inFlight.current) return inFlight.current;
    const run = async () => {
      const mutationsAtStart = mutations.current;
      setLoadError(false);
      try {
        const { data } = await listNotifications();
        if (mutations.current !== mutationsAtStart) return null;
        const rows = data?.notifications ?? [];
        setNotifications(rows);
        setUnreadCount(data?.unreadCount ?? 0);
        return rows;
      } catch (e) {
        if (mutations.current !== mutationsAtStart) return null;
        // Keep the last good data; a refetch failing shouldn't blank the list.
        setLoadError(true);
        if (showToast) toast.error(e.message);
        return null;
      } finally {
        inFlight.current = null;
      }
    };
    inFlight.current = run();
    return inFlight.current;
  }, []);

  // Covers both the initial mount and every later pathname change. Deliberately
  // not split into a separate mount effect -- that would fire two requests on
  // mount. search/hash are excluded: board keeps UI state in query params.
  useEffect(() => {
    const showToast = isFirstLoad.current;
    isFirstLoad.current = false;
    load({ showToast });
  }, [pathname, load]);

  useEffect(() => {
    const refetch = () => load({ showToast: false });
    // visibilitychange covers switching browser tabs; focus covers switching
    // to another application entirely, which never fires visibilitychange.
    const onVisibilityChange = () => {
      if (document.visibilityState === "visible") refetch();
    };
    document.addEventListener("visibilitychange", onVisibilityChange);
    window.addEventListener("focus", refetch);
    return () => {
      document.removeEventListener("visibilitychange", onVisibilityChange);
      window.removeEventListener("focus", refetch);
    };
  }, [load]);

  /** Set isRead on the listed rows whose ids are given. */
  const setRead = (ids, isRead) =>
    setNotifications((prev) =>
      prev.map((n) => (ids.includes(n.id) ? { ...n, isRead } : n)),
    );

  /**
   * Mark one row read when the user clicks it. The row greys and the badge
   * drops at once; a failure puts both back. The write counter is bumped on
   * both sides of the request: a refetch started before it, or while it was
   * in flight, may carry the state from before it committed.
   */
  const handleMarkRead = async (notification) => {
    if (notification.isRead) return;
    mutations.current += 1;
    setRead([notification.id], true);
    setUnreadCount((c) => Math.max(0, c - 1));
    try {
      const { data } = await markNotificationsRead([notification.id]);
      mutations.current += 1;
      setUnreadCount(data?.unreadCount ?? 0);
    } catch (e) {
      setRead([notification.id], false);
      setUnreadCount((c) => c + 1);
      toast.error(e.message);
    }
  };

  /**
   * Go to where the reader acts on a notification. Marking read is not
   * awaited: it is optimistic and puts the row back itself if it fails.
   */
  const handleOpen = (notification) => {
    handleMarkRead(notification);
    setOpen(false);
    navigate(notification.link);
  };

  /** Mark every unread notification read, listed or not. */
  const handleMarkAllRead = async () => {
    const unreadIds = notifications.filter((n) => !n.isRead).map((n) => n.id);
    const countBefore = unreadCount;
    mutations.current += 1;
    setRead(unreadIds, true);
    setUnreadCount(0);
    try {
      const { data } = await markAllNotificationsRead();
      mutations.current += 1;
      setUnreadCount(data?.unreadCount ?? 0);
    } catch (e) {
      setRead(unreadIds, false);
      setUnreadCount(countBefore);
      toast.error(e.message);
    }
  };

  const handleDismiss = async (notification) => {
    mutations.current += 1;
    setNotifications((prev) => prev.filter((n) => n.id !== notification.id));
    try {
      const { data } = await dismissNotification(notification.id);
      setUnreadCount(data?.unreadCount ?? 0);
    } catch (e) {
      toast.error(e.message);
    }
  };

  const handleDismissAll = async () => {
    mutations.current += 1;
    setNotifications([]);
    try {
      const { data } = await dismissAllNotifications();
      setUnreadCount(data?.unreadCount ?? 0);
    } catch (e) {
      toast.error(e.message);
    }
  };

  return (
    <Popover
      open={open}
      onOpenChange={(next) => {
        setOpen(next);
        if (next) load({ showToast: false });
      }}
    >
      <PopoverTrigger asChild>
        <Button
          variant="ghost"
          size="icon"
          aria-label="Notifications"
          className="relative"
        >
          <Bell size={20} />
          {unreadCount > 0 && (
            <Badge
              variant="destructive"
              className="absolute -right-1 -top-1 h-5 min-w-5 justify-center rounded-full px-1 text-xs"
            >
              {unreadCount}
            </Badge>
          )}
        </Button>
      </PopoverTrigger>
      <PopoverContent align="end" className="w-80 p-0">
        <div className="flex items-center justify-between border-b p-2">
          <span className="text-sm font-medium">Notifications</span>
          <div className="flex items-center">
            <Button
              variant="ghost"
              size="sm"
              disabled={unreadCount === 0}
              onClick={handleMarkAllRead}
            >
              Mark all as read
            </Button>
            <Button
              variant="ghost"
              size="sm"
              disabled={notifications.length === 0}
              onClick={handleDismissAll}
            >
              Clear all
            </Button>
          </div>
        </div>
        <div className="max-h-96 overflow-y-auto">
          {loadError && (
            <p className="p-4 text-sm text-red-600">
              Couldn't load notifications.
            </p>
          )}
          {!loadError && notifications.length === 0 && (
            <p className="p-4 text-sm text-slate-500">No notifications yet.</p>
          )}
          {notifications.map((n) => {
            const text = (
              <>
                <span
                  aria-label={n.isRead ? undefined : "Unread"}
                  className={`mt-1.5 h-2 w-2 shrink-0 rounded-full ${
                    n.isRead ? "invisible" : "bg-blue-500"
                  }`}
                />
                <span
                  className={`flex-1 ${
                    n.isRead ? "text-slate-400" : "font-medium text-slate-900"
                  }`}
                >
                  {describe(n)}
                </span>
              </>
            );
            return (
              <div
                key={n.id}
                data-read={n.isRead ? "true" : "false"}
                className="flex items-start gap-2 border-b px-4 py-2 text-sm last:border-b-0"
              >
                {n.isRead ? (
                  <div className="flex flex-1 items-start gap-2">{text}</div>
                ) : (
                  // Its own button, beside the X rather than around it, so a
                  // dismiss never also marks the row read.
                  <button
                    type="button"
                    title="Mark as read"
                    onClick={() => handleMarkRead(n)}
                    className="-mx-1 flex flex-1 cursor-pointer items-start gap-2 rounded px-1 text-left hover:bg-slate-50"
                  >
                    {text}
                  </button>
                )}
                {n.link && (
                  <Button
                    variant="ghost"
                    size="icon"
                    aria-label="Open"
                    title="Open"
                    className="h-5 w-5 shrink-0 text-slate-500"
                    onClick={() => handleOpen(n)}
                  >
                    <ArrowUpRight size={14} />
                  </Button>
                )}
                <Button
                  variant="ghost"
                  size="icon"
                  aria-label="Dismiss notification"
                  className="h-5 w-5 shrink-0 text-slate-500"
                  onClick={() => handleDismiss(n)}
                >
                  <X size={14} />
                </Button>
              </div>
            );
          })}
        </div>
      </PopoverContent>
    </Popover>
  );
};

export default NotificationBell;
