/**
 * Mock data for the Leave & PTO prototype.
 *
 * ⚠️ EVERY POLICY FIGURE HERE IS A PLACEHOLDER, NOT THE REAL POLICY.
 * This prototype is published to a public GitHub Pages URL, so the real
 * entitlements, weekend arrangement, and company holiday calendar are
 * deliberately replaced with invented values. What the prototype demonstrates
 * is the *mechanism* — accrual, deduction, approval, advance notice — not the
 * numbers. Real figures live in the internal engineering spec.
 *
 * Placeholder substitutions:
 *   level entitlement   real → replaced with L1 0h / L2-L4 96h
 *   weekend days        real → replaced with Friday + Saturday
 *   holiday calendar    real → replaced with invented holidays
 */

/** Weekend days as JS getDay() indices. Placeholder: Friday(5) + Saturday(6). */
export const WEEKEND_DAYS = [5, 6];

/** Hours in one working day. */
export const HOURS_PER_DAY = 8;

/** Sick leave at or below this many hours is approved automatically. */
export const SICK_AUTO_APPROVE_HOURS = 24;

/**
 * Placeholder entitlements, in hours per year.
 *
 * The level entitlement is the whole yearly allowance — there is no second
 * pool on top of it. Anything beyond it reaches a balance one of three ways:
 * exchanging a company holiday, an administrator's correction, or the opening
 * balance carried over at go-live.
 */
export const LEVEL_POLICY = { L1: 0, L2: 96, L3: 96, L4: 96 };

/**
 * Placeholder company holidays, stored one row per date — the same shape as the
 * real table, where a multi-day break is several rows sharing a name rather
 * than a start/end pair.
 *
 * One property of the real calendar is reproduced here because it is what
 * breaks naive display code: a named holiday can be split across
 * non-consecutive dates (Founders Week below covers Oct 1-3 and Oct 5,
 * skipping Oct 4).
 *
 * Exchangeability belongs to the whole holiday, so every row of one break
 * carries the same value. Year End Break is exchangeable across all three of
 * its days, which is what lets the request form demonstrate working two of
 * them and keeping the third.
 */
export const COMPANY_HOLIDAYS = [
  { date: "2026-08-21", name: "Charter Day", exchangeable: false },

  { date: "2026-09-03", name: "Harvest Break", exchangeable: true },
  { date: "2026-09-04", name: "Harvest Break", exchangeable: true },
  { date: "2026-09-05", name: "Harvest Break", exchangeable: true },

  { date: "2026-09-25", name: "Autumn Festival", exchangeable: true },

  { date: "2026-10-01", name: "Founders Week", exchangeable: false },
  { date: "2026-10-02", name: "Founders Week", exchangeable: false },
  { date: "2026-10-03", name: "Founders Week", exchangeable: false },
  { date: "2026-10-05", name: "Founders Week", exchangeable: false },

  { date: "2026-11-13", name: "Founders Day", exchangeable: false },

  { date: "2026-12-23", name: "Year End Break", exchangeable: true },
  { date: "2026-12-24", name: "Year End Break", exchangeable: true },
  { date: "2026-12-25", name: "Year End Break", exchangeable: true },
];

/**
 * How the weekend reads on screen. One arrangement for everyone: the system
 * covers a single country, so there is no dimension to vary it along.
 *
 * Placeholder wording, like every other figure here.
 */
export const WEEKEND_LABEL = "Friday + Saturday (Local date)";

/** The signed-in employee for the Employee view. */
export const CURRENT_USER = {
  id: 1,
  name: "Dana Whitfield",
  level: "L3",
  managerId: 9,
  managerName: "Priya Raghavan",
  hireDate: "2024-03-11",
};

/** Direct reports shown in the Manager view (viewer = Priya, id 9). */
export const DEMO_MANAGER_ID = 9;

/**
 * Ledger rows for the current user. Balance is the sum of this list — there is
 * no second source of truth. The go-live balance carried over from the old
 * system is just an adjustment with a note saying so — it needs no type of
 * its own, and the engine ignores hand-written rows either way.
 */
export const INITIAL_LEDGER = [
  {
    id: 1,
    entryType: "manual_adjustment",
    hours: 46.5,
    effectiveDate: "2026-08-31",
    note: "Migrated from the previous system at go-live.",
  },
  {
    id: 2,
    entryType: "weekly_accrual",
    hours: 1.85,
    effectiveDate: "2026-09-07",
    note: "",
  },
  {
    id: 3,
    entryType: "weekly_accrual",
    hours: 1.85,
    effectiveDate: "2026-09-14",
    note: "",
  },
  {
    id: 5,
    entryType: "leave_deduction",
    hours: -16,
    effectiveDate: "2026-09-17",
    note: "Paid leave 2026-09-17 → 2026-09-18",
  },
  {
    id: 6,
    entryType: "exchange_credit",
    hours: 8,
    effectiveDate: "2026-09-04",
    note: "Worked Harvest Break",
  },
];

/** Requests already on file for the current user. */
export const INITIAL_REQUESTS = [
  {
    id: 101,
    userId: 1,
    userName: "Dana Whitfield",
    type: "paid",
    startDate: "2026-09-17",
    endDate: "2026-09-18",
    hours: 16,
    status: "approved",
    approverName: "Priya Raghavan",
    reason: "Family visit.",
    isOverdraft: false,
    isLateNotice: false,
    decidedBy: "Priya Raghavan",
  },
  {
    id: 102,
    userId: 1,
    userName: "Dana Whitfield",
    type: "sick",
    startDate: "2026-09-29",
    endDate: "2026-09-29",
    hours: 8,
    status: "approved",
    approverName: "Priya Raghavan",
    reason: "Migraine.",
    isOverdraft: false,
    isLateNotice: false,
    decidedBy: "system",
  },
  {
    id: 103,
    userId: 1,
    userName: "Dana Whitfield",
    type: "exchange",
    startDate: "2026-09-04",
    endDate: "2026-09-04",
    hours: 8,
    status: "approved",
    approverName: "Priya Raghavan",
    reason: "Covering the release window.",
    isOverdraft: false,
    isLateNotice: false,
    decidedBy: "Priya Raghavan",
  },
];

/**
 * Requests from other people, waiting on the demo manager. Seeded so the
 * Manager view opens with something to act on, including one overdraft and one
 * late-notice request so both warning treatments are visible.
 */
export const INITIAL_TEAM_REQUESTS = [
  {
    id: 201,
    userId: 2,
    userName: "Marcus Bell",
    userLevel: "L2",
    balanceBefore: 12,
    type: "paid",
    startDate: "2026-11-02",
    endDate: "2026-11-06",
    hours: 24,
    status: "pending",
    approverName: "Priya Raghavan",
    reason: "Pre-booked trip.",
    isOverdraft: true,
    isLateNotice: false,
    decidedBy: null,
  },
  {
    id: 202,
    userId: 3,
    userName: "Ines Okonkwo",
    userLevel: "L4",
    balanceBefore: 88.25,
    type: "paid",
    startDate: "2026-10-15",
    endDate: "2026-10-15",
    hours: 8,
    status: "pending",
    approverName: "Priya Raghavan",
    reason: "Moving apartments.",
    isOverdraft: false,
    isLateNotice: true,
    requiredNoticeDays: 2,
    actualNoticeDays: 1,
    decidedBy: null,
  },
  {
    id: 203,
    userId: 4,
    userName: "Tobias Lund",
    userLevel: "L3",
    balanceBefore: 51,
    type: "sick",
    startDate: "2026-10-19",
    endDate: "2026-10-22",
    hours: 32,
    status: "pending",
    approverName: "Priya Raghavan",
    reason: "Surgery recovery, doctor's note to follow.",
    isOverdraft: false,
    isLateNotice: false,
    decidedBy: null,
  },
];

/**
 * Org-wide balances for the Admin overview. `dataIssue` marks people the
 * Azure sync could not fully resolve; `no_manager` is called out separately
 * because those people cannot submit any request at all.
 */
export const ORG_BALANCES = [
  {
    id: 1,
    name: "Dana Whitfield",
    level: "L3",
    manager: "Priya Raghavan",
    balance: 42.2,
    pending: 0,
    dataIssue: null,
  },
  {
    id: 2,
    name: "Marcus Bell",
    level: "L2",
    manager: "Priya Raghavan",
    balance: 12,
    pending: 24,
    dataIssue: null,
  },
  {
    id: 3,
    name: "Ines Okonkwo",
    level: "L4",
    manager: "Priya Raghavan",
    balance: 88.25,
    pending: 8,
    dataIssue: null,
  },
  {
    id: 4,
    name: "Tobias Lund",
    level: "L3",
    manager: "Priya Raghavan",
    balance: 51,
    pending: 0,
    dataIssue: null,
  },
  {
    id: 5,
    name: "Wei Zhang",
    level: "L2",
    manager: "Priya Raghavan",
    balance: 33.75,
    pending: 0,
    dataIssue: null,
  },
  {
    id: 9,
    name: "Priya Raghavan",
    level: "L4",
    manager: "—",
    balance: 104,
    pending: 0,
    dataIssue: "no_manager",
  },
  {
    id: 10,
    name: "Ravi Menon",
    level: null,
    manager: "Priya Raghavan",
    balance: 0,
    pending: 0,
    dataIssue: "unparsable_title",
  },
  {
    id: 11,
    name: "Sofia Almeida",
    level: "L1",
    manager: "Priya Raghavan",
    balance: 0,
    pending: 0,
    dataIssue: "missing_hire_date",
  },
];

/** Human-readable labels for the data-health issues above. */
export const DATA_ISSUE_LABELS = {
  no_manager: {
    title: "No manager in Azure",
    blurb: "Cannot submit any request, including sick leave.",
    severity: "critical",
  },
  unparsable_title: {
    title: "Job title does not parse",
    blurb: 'Expected the form "Software Engineer (L3)". Accrues 0 level leave.',
    severity: "warning",
  },
  missing_hire_date: {
    title: "No hire date in Azure",
    blurb: "Accrual cannot start. Nothing is granted until this is filled in.",
    severity: "warning",
  },
};
