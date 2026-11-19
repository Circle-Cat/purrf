/**
 * Display metadata for the Inbox services. Unsorted holds mail sent straight
 * to the shared mailbox: it cannot receive transfers, and its threads can be
 * deleted.
 */
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
    label: "Contact",
    badgeClass: "border-stone-300 bg-stone-100 text-stone-700",
  },
  {
    key: "unsorted",
    label: "Unsorted",
    badgeClass: "border-zinc-300 bg-zinc-50 text-zinc-600",
    transferTarget: false,
    deletable: true,
  },
];

/**
 * Look up a service's display metadata. `file` holds the wording of filing a
 * thread out of the Inbox, for the services that can.
 *
 * @param {string} key - Service key.
 * @returns {{key: string, label: string, badgeClass: string,
 *   file?: {action: string, title: string, done: string},
 *   transferTarget?: boolean, deletable?: boolean}}
 */
export const serviceOf = (key) =>
  SERVICES.find((s) => s.key === key) ?? {
    key,
    label: key,
    badgeClass: "border-slate-300 bg-slate-50 text-slate-700",
  };

/**
 * Which mail a service holds, for the line under the service chips: mail
 * sent to its address, or for Unsorted mail sent straight to the mailbox.
 *
 * @param {string} key - Service key.
 * @param {string | null | undefined} address - The service's address.
 * @returns {{before: string, address: string, after: string} | null} The
 *   sentence split around the address, or null when there is no address.
 */
export const addressNote = (key, address) => {
  if (!address) return null;
  if (key === "unsorted") {
    return {
      before: "Mail sent straight to ",
      address,
      after: ", not to any service address.",
    };
  }
  return { before: "Mail sent to ", address, after: "." };
};

/**
 * `1 conversation`, `3 conversations`.
 *
 * @param {number} n - Count.
 * @returns {string}
 */
export const conversations = (n) => `${n} conversation${n === 1 ? "" : "s"}`;

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
