/** Display metadata for the three Inbox services. */
export const SERVICES = [
  {
    key: "mentorship",
    label: "Mentorship",
    badgeClass: "border-teal-200 bg-teal-50 text-teal-800",
    file: {
      action: "File to participant",
      title: "File to a participant",
      done: "Filed to the participant. Find it on their page from now on.",
    },
  },
  {
    key: "recruiting",
    label: "Recruiting",
    badgeClass: "border-indigo-200 bg-indigo-50 text-indigo-800",
    file: {
      action: "File to application",
      title: "File to an application",
      done: "Filed to the application. Find it on the application from now on.",
    },
  },
  {
    key: "inquiries",
    label: "Inquiries",
    badgeClass: "border-stone-300 bg-stone-100 text-stone-700",
  },
];

/**
 * Look up a service's display metadata. `file` holds the wording of filing a
 * thread out of the Inbox, for the services that can.
 *
 * @param {string} key - Service key.
 * @returns {{key: string, label: string, badgeClass: string,
 *   file?: {action: string, title: string, done: string}}}
 */
export const serviceOf = (key) =>
  SERVICES.find((s) => s.key === key) ?? {
    key,
    label: key,
    badgeClass: "border-slate-300 bg-slate-50 text-slate-700",
  };

/** Label of each machine-generated mail kind. */
export const MACHINE_TAG_LABELS = {
  auto_reply: "Auto-reply",
  bounce: "Delivery failed",
};

/**
 * Format an ISO timestamp as `Sep 29, 21:14` in the viewer's time zone.
 *
 * @param {string} iso - ISO timestamp.
 * @returns {string}
 */
export const formatTime = (iso) =>
  new Date(iso).toLocaleString("en-US", {
    month: "short",
    day: "numeric",
    hour: "2-digit",
    minute: "2-digit",
    hour12: false,
  });

/**
 * Format a byte count for an attachment chip.
 *
 * @param {number} bytes - Size in bytes.
 * @returns {string}
 */
export const formatSize = (bytes) => {
  if (typeof bytes !== "number") return "";
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${Math.round(bytes / 1024)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
};
