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

/** Rows per page on the administrator's Ledger tab, as the real endpoint pages. */
export const LEDGER_PAGE_SIZE = 50;

/**
 * Who the Ledger tab can name. Everyone on the Balances tab, plus two who are
 * not: somebody who has left (their rows stay in the ledger forever, but the
 * person filter only lists who is paid now) and an account that no longer
 * resolves, whose rows must still be shown.
 */
export const LEDGER_PEOPLE = {
  1: { name: "Dana Whitfield", ldap: "dana.whitfield" },
  2: { name: "Marcus Bell", ldap: "marcus.bell" },
  3: { name: "Ines Okonkwo", ldap: "ines.okonkwo" },
  4: { name: "Tobias Lund", ldap: "tobias.lund" },
  5: { name: "Wei Zhang", ldap: "wei.zhang" },
  9: { name: "Priya Raghavan", ldap: "priya.raghavan" },
  10: { name: "Ravi Menon", ldap: "ravi.menon" },
  11: { name: "Sofia Almeida", ldap: "sofia.almeida" },
  12: { name: "Hannah Kim", ldap: "hannah.kim" },
  14: { name: null, ldap: null },
};

/** `2026-06-01` plus n days, computed in UTC so no local zone can shift it. */
const addDays = (iso, days) => {
  const [y, m, d] = iso.split("-").map(Number);
  return new Date(Date.UTC(y, m - 1, d + days)).toISOString().slice(0, 10);
};

/**
 * Every ledger row in the company, as the administrator's Ledger tab reads it.
 *
 * Weekly accruals run on Mondays at the placeholder 96h a year (1.85h a
 * week); L1 and the unparsable title accrue nothing. Hannah Kim's accruals stop
 * when she leaves in July. Ids are handed out in the order the rows would
 * have been written, which is what breaks a tie between two rows on one day.
 */
const buildOrgLedger = () => {
  const rows = [];
  const add = (userId, entryType, hours, effectiveDate, note = null) =>
    rows.push({ userId, entryType, hours, effectiveDate, note });

  for (const [userId, hours] of [
    [1, 46.5],
    [2, 20],
    [3, 72.5],
    [4, 38],
    [5, 12],
    [9, 80],
    [10, 0.5],
    [12, 16],
  ]) {
    add(
      userId,
      "manual_adjustment",
      hours,
      "2026-05-31",
      "Carried over from the previous system at go-live.",
    );
  }
  add(
    3,
    "carryover_forfeit",
    -8.5,
    "2026-05-31",
    "Above the carry-over cap at go-live.",
  );

  for (let week = 0; week < 17; week += 1) {
    const monday = addDays("2026-06-01", week * 7);
    for (const userId of [1, 2, 3, 4, 9]) {
      add(userId, "weekly_accrual", 1.85, monday);
    }
    if (monday >= "2026-07-06") add(5, "weekly_accrual", 1.85, monday);
    if (monday <= "2026-07-13") add(12, "weekly_accrual", 1.85, monday);
  }
  // Promoted from L1 on the same Monday as an accrual: two rows on one day.
  add(5, "level_change", 0, "2026-07-06", "L1 -> L2");

  add(
    2,
    "leave_deduction",
    -24,
    "2026-06-16",
    "Paid leave 2026-06-16 → 2026-06-18",
  );
  add(4, "leave_deduction", -8, "2026-07-02", "Paid leave 2026-07-02");
  add(1, "exchange_credit", 8, "2026-06-20", "Worked Midsummer Day");
  add(
    3,
    "leave_deduction",
    -40,
    "2026-08-03",
    "Paid leave 2026-08-03 → 2026-08-09",
  );
  add(
    12,
    "leave_deduction",
    -16,
    "2026-07-08",
    "Paid leave 2026-07-08 → 2026-07-09",
  );
  // An L1 has no entitlement and may still take paid leave: negative by design.
  add(11, "leave_deduction", -8, "2026-08-21", "Paid leave 2026-08-21");
  add(
    9,
    "leave_deduction",
    -16,
    "2026-09-01",
    "Paid leave 2026-09-01 → 2026-09-02",
  );
  add(
    1,
    "leave_deduction",
    -16,
    "2026-09-17",
    "Paid leave 2026-09-17 → 2026-09-18",
  );
  add(
    2,
    "manual_adjustment",
    4,
    "2026-09-08",
    "Half day booked twice in July; one returned.",
  );
  add(
    14,
    "manual_adjustment",
    10,
    "2026-05-31",
    "Carried over from the previous system at go-live.",
  );
  add(14, "leave_deduction", -8, "2026-06-10", "Paid leave 2026-06-10");

  return rows
    .sort((a, b) => a.effectiveDate.localeCompare(b.effectiveDate))
    .map((row, index) => ({ leaveLedgerId: 1000 + index, ...row }));
};

export const ORG_LEDGER = buildOrgLedger();
