const OUTCOMES = {
  approved: "Approved",
  rejected: "Rejected",
  withdrawn: "Withdrawn",
  superseded: "Closed by a direct block",
};

/**
 * The page a block request was raised from, readable: "recruiting_application"
 * reads "recruiting application".
 * @param {string|null|undefined} raisedFrom
 * @returns {string}
 */
export const humanizeSource = (raisedFrom) =>
  (raisedFrom ?? "").replace(/_/g, " ").trim();

/**
 * How a closed block request ended, as the account page lists it.
 * @param {string} status - The request's status.
 * @returns {string}
 */
export const blockRequestOutcome = (status) => OUTCOMES[status] ?? status;
