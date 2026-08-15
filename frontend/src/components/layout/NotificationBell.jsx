import { useCallback, useEffect, useRef, useState } from "react";
import { useLocation } from "react-router-dom";
import { Bell, X } from "lucide-react";
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
} from "@/api/recruitingApi";

/**
 * Compose a notification's display text from its event type and details.
 *
 * Two audiences share this switch. Every recruiting line is written from
 * staff's point of view, about someone else ("{actor} moved {applicant}");
 * the mentorship line below is written to the person it happened to. Match
 * the case you are adding, not the surrounding voice.
 */
const describe = (n) => {
  const actor = n.actorName ?? "Someone";
  switch (n.eventType) {
    case "mentorship.mentor_admitted":
      return `You were admitted to ${n.jobTitle}`;
    case "recruiting.reassigned":
      return `${actor} assigned you to evaluate ${n.applicantName} — ${n.jobTitle}`;
    case "recruiting.auto_assigned":
      return `You were auto-assigned to evaluate ${n.applicantName} — ${n.jobTitle}`;
    case "recruiting.mentioned":
      return `${actor} mentioned you in a comment on ${n.applicantName} — ${n.jobTitle}`;
    case "recruiting.review_opened":
      return `${actor} submitted "${n.jobTitle}" for your review`;
    case "recruiting.review_decided":
      return n.details?.decision === "approved"
        ? `${actor} approved "${n.jobTitle}"`
        : `${actor} rejected "${n.jobTitle}"`;
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
    default:
      return "";
  }
};

/**
 * Header bell + popover for in-app recruiting notifications.
 *
 * Notifications are light reminders: they don't navigate anywhere.
 * Dismissing one (the X) or "Clear all" marks it server-side and drops
 * it from the list.
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
  const { pathname } = useLocation();

  // Set synchronously before the first await: visibilitychange and focus both
  // fire when returning to a hidden tab, and state would batch them into two
  // requests.
  const inFlight = useRef(false);
  // Bumped by every dismiss so a refetch that raced it can drop its response
  // instead of resurrecting the row the user just removed.
  const mutations = useRef(0);
  const isFirstLoad = useRef(true);

  const load = useCallback(async ({ showToast }) => {
    if (inFlight.current) return;
    inFlight.current = true;
    const mutationsAtStart = mutations.current;
    setLoadError(false);
    try {
      const { data } = await listNotifications();
      if (mutations.current !== mutationsAtStart) return;
      setNotifications(data?.notifications ?? []);
      setUnreadCount(data?.unreadCount ?? 0);
    } catch (e) {
      if (mutations.current !== mutationsAtStart) return;
      // Keep the last good data; a refetch failing shouldn't blank the list.
      setLoadError(true);
      if (showToast) toast.error(e.message);
    } finally {
      inFlight.current = false;
    }
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
      onOpenChange={(open) => {
        if (open) load({ showToast: false });
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
          <Button
            variant="ghost"
            size="sm"
            disabled={notifications.length === 0}
            onClick={handleDismissAll}
          >
            Clear all
          </Button>
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
          {notifications.map((n) => (
            <div
              key={n.id}
              className="flex items-start gap-2 border-b px-4 py-2 text-sm last:border-b-0"
            >
              <span className="flex-1 font-medium">{describe(n)}</span>
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
          ))}
        </div>
      </PopoverContent>
    </Popover>
  );
};

export default NotificationBell;
