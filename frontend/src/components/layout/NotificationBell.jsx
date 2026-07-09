import { useCallback, useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { Bell } from "lucide-react";
import { toast } from "sonner";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import {
  Popover,
  PopoverContent,
  PopoverTrigger,
} from "@/components/ui/popover";
import {
  listNotifications,
  markAllNotificationsRead,
  markNotificationRead,
} from "@/api/recruitingApi";
import { ROUTE_PATHS } from "@/constants/RoutePaths";

/** Compose a notification's display text, by type. */
const describe = (n) => {
  switch (n.type) {
    case "assigned_to_evaluate":
      return n.actorName
        ? `${n.actorName} assigned you to evaluate ${n.applicantName} — ${n.jobTitle}`
        : `You were auto-assigned to evaluate ${n.applicantName} — ${n.jobTitle}`;
    case "mentioned":
      return `${n.actorName ?? "Someone"} mentioned you in a comment on ${n.applicantName} — ${n.jobTitle}`;
    case "job_review_requested":
      return `${n.actorName ?? "Someone"} submitted "${n.jobTitle}" for your review`;
    case "job_review_approved":
      return `${n.actorName ?? "Someone"} approved "${n.jobTitle}"`;
    case "job_review_rejected":
      return `${n.actorName ?? "Someone"} rejected "${n.jobTitle}"`;
    default:
      return "";
  }
};

/** Where a notification click should navigate to. */
const targetPath = (n) =>
  n.applicationId != null
    ? ROUTE_PATHS.RECRUITING_APPLICATION_DETAIL(n.applicationId)
    : ROUTE_PATHS.RECRUITING_JOB_DETAIL(n.jobId);

/**
 * Header bell + popover for in-app recruiting notifications.
 *
 * Fetches once on mount only -- no polling, no WebSocket/SSE, per the
 * notification-system design spec. Mark-read/mark-all-read update local
 * state immediately and reconcile the unread count from the response.
 */
const NotificationBell = () => {
  const [notifications, setNotifications] = useState([]);
  const [unreadCount, setUnreadCount] = useState(0);
  const [loadError, setLoadError] = useState(false);
  const navigate = useNavigate();

  const load = useCallback(async () => {
    setLoadError(false);
    try {
      const { data } = await listNotifications();
      setNotifications(data?.notifications ?? []);
      setUnreadCount(data?.unreadCount ?? 0);
    } catch (e) {
      setLoadError(true);
      toast.error(e.message);
    }
  }, []);

  useEffect(() => {
    load();
  }, [load]);

  const handleOpenNotification = async (notification) => {
    navigate(targetPath(notification));
    if (notification.read) return;
    setNotifications((prev) =>
      prev.map((n) => (n.id === notification.id ? { ...n, read: true } : n)),
    );
    try {
      const { data } = await markNotificationRead(notification.id);
      setUnreadCount(data?.unreadCount ?? 0);
    } catch (e) {
      toast.error(e.message);
    }
  };

  const handleMarkAllRead = async () => {
    setNotifications((prev) => prev.map((n) => ({ ...n, read: true })));
    try {
      const { data } = await markAllNotificationsRead();
      setUnreadCount(data?.unreadCount ?? 0);
    } catch (e) {
      toast.error(e.message);
    }
  };

  return (
    <Popover>
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
            disabled={unreadCount === 0}
            onClick={handleMarkAllRead}
          >
            Mark all read
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
            <button
              key={n.id}
              type="button"
              onClick={() => handleOpenNotification(n)}
              className={`block w-full border-b px-4 py-2 text-left text-sm last:border-b-0 hover:bg-accent ${
                n.read ? "text-slate-500" : "font-medium"
              }`}
            >
              {describe(n)}
            </button>
          ))}
        </div>
      </PopoverContent>
    </Popover>
  );
};

export default NotificationBell;
