import { toast } from "sonner";

import { Button } from "@/components/ui/button";

/**
 * Description body for the profile/training reminder toasts: the
 * message text followed by a confirm button anchored to the
 * bottom-right. Rendered inside `toast.info`'s description slot, so
 * sonner's default info styling (icon top-left, info color) is
 * preserved while the explicit confirm button replaces the global
 * close button for these toasts.
 */
const ReminderToastBody = ({ toastId, message }) => (
  <div className="flex flex-col gap-3" data-testid={toastId}>
    <div className="whitespace-pre-line">{message}</div>
    <div className="flex justify-end">
      <Button
        size="sm"
        variant="outline"
        onClick={() => toast.dismiss(toastId)}
      >
        Confirm
      </Button>
    </div>
  </div>
);

export default ReminderToastBody;
