/** Display metadata for the three Inbox services. */
export const SERVICES = [
  {
    key: "mentorship",
    label: "Mentorship",
    badgeClass: "border-teal-200 bg-teal-50 text-teal-800",
  },
  {
    key: "recruiting",
    label: "Recruiting",
    badgeClass: "border-indigo-200 bg-indigo-50 text-indigo-800",
  },
  {
    key: "inquiries",
    label: "Inquiries",
    badgeClass: "border-stone-300 bg-stone-100 text-stone-700",
  },
];

/**
 * Look up a service's display metadata.
 *
 * @param {string} key - Service key.
 * @returns {{key: string, label: string, badgeClass: string}}
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
 * Chip text for where an assigned thread sits.
 *
 * @param {object|null} assignment - Assignment DTO from the API.
 * @returns {string|null}
 */
export const assignmentLabel = (assignment) => {
  if (!assignment) return null;
  if (assignment.kind === "round") return `${assignment.roundName} round`;
  return `${assignment.jobTitle} · application #${assignment.applicationId}`;
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
