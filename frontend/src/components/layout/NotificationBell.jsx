import { useCallback, useEffect, useState } from "react";
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

/**
 * Header bell + popover for in-app recruiting notifications.
 *
 * Notifications are light reminders: they don't navigate anywhere.
 * Dismissing one (the X) or "Clear all" deletes it server-side and drops
 * it from the list. Fetches once on mount only -- no polling, no
 * WebSocket/SSE, per the notification-system design spec.
 */
const NotificationBell = () => {
  const [notifications, setNotifications] = useState([]);
  const [unreadCount, setUnreadCount] = useState(0);
  const [loadError, setLoadError] = useState(false);

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

  const handleDismiss = async (notification) => {
    setNotifications((prev) => prev.filter((n) => n.id !== notification.id));
    try {
      const { data } = await dismissNotification(notification.id);
      setUnreadCount(data?.unreadCount ?? 0);
    } catch (e) {
      toast.error(e.message);
    }
  };

  const handleDismissAll = async () => {
    setNotifications([]);
    try {
      const { data } = await dismissAllNotifications();
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
