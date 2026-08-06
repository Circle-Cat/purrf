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
 *   extra paid leave    real → replaced with 40h weekly + 40h granted
 *   weekend days        real → replaced with Friday + Saturday
 *   holiday calendar    real → replaced with invented holidays
 */

/** Weekend days as JS getDay() indices. Placeholder: Friday(5) + Saturday(6). */
export const WEEKEND_DAYS = [5, 6];

/** Hours in one working day. */
export const HOURS_PER_DAY = 8;

/** Sick leave at or below this many hours is approved automatically. */
export const SICK_AUTO_APPROVE_HOURS = 24;

/** Placeholder entitlements, in hours per year. */
export const LEVEL_POLICY = { L1: 0, L2: 96, L3: 96, L4: 96 };

/**
 * The two halves of the extra paid leave, which are granted quite differently.
 *
 *   weekly    accrues week by week alongside the level entitlement, so it is
 *             just another number in the same sum
 *   holiday   granted in a lump by an administrator ahead of each public
 *             holiday, because that is when it is needed and no calendar in
 *             this system knows when those fall
 *
 * Placeholder figures.
 */
export const WEEKLY_EXTRA_HOURS = 40;
export const HOLIDAY_GRANT_ALLOWANCE = 40;

/**
 * Placeholder company holidays, stored one row per date — the same shape as the
 * real table, where a multi-day break is several rows sharing a name rather
 * than a start/end pair.
 *
 * Two properties of the real calendar are reproduced here because they are what
 * break naive display code:
 *
 *   - A named holiday can be split across non-consecutive dates (Founders Week
 *     below covers Oct 1-3 and Oct 5, skipping Oct 4).
 *   - Exchangeability is per date, not per holiday, so one break can be partly
 *     exchangeable (Founders Week again).
 */
export const COMPANY_HOLIDAYS = [
  { date: "2026-08-21", name: "Charter Day", exchangeable: false },

  { date: "2026-09-03", name: "Harvest Break", exchangeable: true },
  { date: "2026-09-04", name: "Harvest Break", exchangeable: true },
  { date: "2026-09-05", name: "Harvest Break", exchangeable: true },

  { date: "2026-09-25", name: "Autumn Festival", exchangeable: true },

  { date: "2026-10-01", name: "Founders Week", exchangeable: false },
  { date: "2026-10-02", name: "Founders Week", exchangeable: false },
  { date: "2026-10-03", name: "Founders Week", exchangeable: true },
  { date: "2026-10-05", name: "Founders Week", exchangeable: true },

  { date: "2026-11-13", name: "Cat Day", exchangeable: false },

  { date: "2026-12-23", name: "Year End Break", exchangeable: true },
  { date: "2026-12-24", name: "Year End Break", exchangeable: true },
  { date: "2026-12-25", name: "Year End Break", exchangeable: false },
];

/**
 * A second region, so the administrator screen has something to switch to.
 *
 * Regions differ in more than their holidays — how much extra paid leave they
 * get, whether any of it is granted around public holidays at all, and which
 * days count as the weekend are all regional. That is why these live in
 * the database with a screen to edit them: a region is created the day someone
 * is hired into it, which is not a date anyone can plan a yearly migration
 * around.
 *
 * Placeholder figures, like everything else here.
 */
export const REGIONS = {
  CN: {
    label: "China",
    weeklyExtraHours: WEEKLY_EXTRA_HOURS,
    holidayGrantAllowance: HOLIDAY_GRANT_ALLOWANCE,
    weekendDays: WEEKEND_DAYS,
    weekendLabel: "Friday + Saturday (Local date)",
  },
  INTL: {
    label: "International",
    weeklyExtraHours: 40,
    holidayGrantAllowance: 0,
    weekendDays: [0, 6],
    weekendLabel: "Saturday + Sunday (Local date)",
  },
};

/** Placeholder company holidays for the second region. */
export const INTL_COMPANY_HOLIDAYS = [
  { date: "2026-09-07", name: "Labour Day", exchangeable: false },
  { date: "2026-11-26", name: "Thanksgiving", exchangeable: false },
  { date: "2026-11-27", name: "Thanksgiving", exchangeable: true },
  { date: "2026-12-24", name: "Winter Break", exchangeable: false },
  { date: "2026-12-25", name: "Winter Break", exchangeable: false },
];

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
 * no second source of truth. `openingBalance` is the one-off migration row
 * written when the system went live; it is deliberately excluded from the
 * accrual engine's "already granted" total.
 */
export const INITIAL_LEDGER = [
  {
    id: 1,
    entryType: "opening_balance",
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
    id: 4,
    entryType: "holiday_grant",
    hours: 5.33,
    effectiveDate: "2026-09-25",
    note: "Autumn Festival",
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
 * Org-wide balances for the Admin overview. `region` decides the weekend, the
 * entitlement, and who a grant reaches, so it is not decoration. `dataIssue` marks people the
 * Azure sync could not fully resolve; `no_manager` is called out separately
 * because those people cannot submit any request at all.
 */
export const ORG_BALANCES = [
  {
    id: 1,
    name: "Dana Whitfield",
    region: "CN",
    level: "L3",
    manager: "Priya Raghavan",
    balance: 47.53,
    pending: 0,
    dataIssue: null,
  },
  {
    id: 2,
    name: "Marcus Bell",
    region: "CN",
    level: "L2",
    manager: "Priya Raghavan",
    balance: 12,
    pending: 24,
    dataIssue: null,
  },
  {
    id: 3,
    name: "Ines Okonkwo",
    region: "CN",
    level: "L4",
    manager: "Priya Raghavan",
    balance: 88.25,
    pending: 8,
    dataIssue: null,
  },
  {
    id: 4,
    name: "Tobias Lund",
    region: "CN",
    level: "L3",
    manager: "Priya Raghavan",
    balance: 51,
    pending: 0,
    dataIssue: null,
  },
  {
    id: 5,
    name: "Wei Zhang",
    region: "CN",
    level: "L2",
    manager: "Priya Raghavan",
    balance: 33.75,
    pending: 0,
    dataIssue: null,
  },
  {
    id: 9,
    name: "Priya Raghavan",
    region: "CN",
    level: "L4",
    manager: "—",
    balance: 104,
    pending: 0,
    dataIssue: "no_manager",
  },
  {
    id: 10,
    name: "Ravi Menon",
    region: "INTL",
    level: null,
    manager: "Priya Raghavan",
    balance: 0,
    pending: 0,
    dataIssue: "unparsable_title",
  },
  {
    id: 11,
    name: "Sofia Almeida",
    region: "INTL",
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
