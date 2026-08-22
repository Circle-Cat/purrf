/**
 * The leave request states and types the server sends.
 *
 * Mirrors `backend/common/leave_enums.py`. There is deliberately no state for
 * cancelling an approved request: approval is the end of the line, and hours
 * are put back by an admin adjustment with a note on it.
 */
export const LEAVE_REQUEST_STATUS = {
  PENDING: "pending",
  APPROVED: "approved",
  REJECTED: "rejected",
  WITHDRAWN: "withdrawn",
};

export const LEAVE_REQUEST_TYPE = {
  PAID: "paid",
  SICK: "sick",
  EXCHANGE: "exchange",
};

/** How each type is named on screen. */
export const LEAVE_TYPE_LABELS = {
  [LEAVE_REQUEST_TYPE.PAID]: "Paid leave",
  [LEAVE_REQUEST_TYPE.SICK]: "Sick leave",
  [LEAVE_REQUEST_TYPE.EXCHANGE]: "Holiday exchange",
};

/**
 * What each type does to the balance, and how the badge for it looks.
 *
 * Three cases, not two. Paid leave deducts, an exchange credits, and sick
 * leave does not touch the balance at all -- `leave_request_service._ledger_entry`
 * writes no row for it, not even a zero one. Colour alone would leave the
 * reader to learn a convention, and the surprising case is the one with no
 * sign, so the effect is spelled out rather than implied: visual weight
 * follows whether the balance moves, and the sign says which way.
 */
export const LEAVE_TYPE_EFFECT = {
  [LEAVE_REQUEST_TYPE.EXCHANGE]: { sign: "+", variant: "default" },
  [LEAVE_REQUEST_TYPE.PAID]: { sign: "\u2212", variant: "secondary" },
  [LEAVE_REQUEST_TYPE.SICK]: { sign: null, variant: "outline" },
};

/** How each state is named on screen. */
export const LEAVE_STATUS_LABELS = {
  [LEAVE_REQUEST_STATUS.PENDING]: "Awaiting your decision",
  [LEAVE_REQUEST_STATUS.APPROVED]: "Approved",
  [LEAVE_REQUEST_STATUS.REJECTED]: "Rejected",
  [LEAVE_REQUEST_STATUS.WITHDRAWN]: "Withdrawn",
};
