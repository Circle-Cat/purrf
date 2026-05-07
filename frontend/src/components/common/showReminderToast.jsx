import { toast } from "sonner";

import ReminderToastBody from "@/components/common/ReminderToastBody";

/**
 * Fire a sonner toast styled as a reminder: icon top-left, no close
 * button, an explicit "Confirm" action anchored to the bottom-right
 * of the description, and stays open until the user confirms
 * (`duration: Infinity`).
 *
 * Pass a stable `id` so repeated calls replace the existing toast
 * rather than stacking duplicates. `type` chooses sonner's icon and
 * rich-color palette (defaults to `info`); use `success` for the
 * post-registration confirmation, `info` for the profile/training
 * reminders.
 */
export const showReminderToast = ({ id, title, message, type = "info" }) => {
  toast[type](title, {
    id,
    // Override sonner's default `align-items: center` so the icon
    // sits at the top-left next to the title rather than floating
    // vertically centered against a multi-line description.
    className: "items-start!",
    description: <ReminderToastBody toastId={id} message={message} />,
    duration: Infinity,
    closeButton: false,
  });
};
