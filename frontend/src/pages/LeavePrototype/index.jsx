import { useState } from "react";
import { CalendarClock, ShieldCheck, UserCheck, User } from "lucide-react";
import { Badge } from "@/components/ui/badge";
import EmployeeView from "@/pages/LeavePrototype/EmployeeView";
import ManagerView from "@/pages/LeavePrototype/ManagerView";
import AdminView from "@/pages/LeavePrototype/AdminView";
import {
  CURRENT_USER,
  INITIAL_LEDGER,
  INITIAL_REQUESTS,
  INITIAL_TEAM_REQUESTS,
} from "@/pages/LeavePrototype/mockData";
import {
  advanceNotice,
  isAutoApproved,
  ledgerBalance,
  pendingReserved,
  today,
} from "@/pages/LeavePrototype/leaveCalc";

/** The three vantage points the design is built around. */
const NAV = [
  { key: "employee", label: "Employee", icon: User },
  { key: "manager", label: "Manager", icon: UserCheck },
  { key: "admin", label: "Administrator", icon: ShieldCheck },
];

/** Everyone in this prototype reports to the same person. */
const DEMO_MANAGER_NAME = "Priya Raghavan";

/**
 * The ledger row an approved request produces. Sick leave produces none — it
 * is recorded and approved but never touches the balance.
 *
 * @param {object} request
 * @returns {object|null}
 */
const ledgerRowFor = (request) => {
  if (request.type === "sick") return null;
  const isExchange = request.type === "exchange";
  return {
    id: Date.now() + request.id,
    entryType: isExchange ? "exchange_credit" : "leave_deduction",
    hours: isExchange ? request.hours : -request.hours,
    effectiveDate: request.startDate,
    note: isExchange
      ? `Worked ${request.startDate}`
      : `Paid leave ${request.startDate}${
          request.endDate !== request.startDate ? ` → ${request.endDate}` : ""
        }`,
  };
};

/**
 * LeavePrototype
 *
 * Self-contained, mock-data prototype of the leave and annual-leave design.
 * Three role views share one set of state, so a request submitted on the
 * Employee page appears in the Manager queue and the decision made there flows
 * back — the point being to show that the balance, the approval, and the
 * ledger are one system rather than three screens.
 *
 * No backend, no auth, no environment variables. Refreshing resets everything.
 *
 * @returns {JSX.Element}
 */
const LeavePrototype = () => {
  const [active, setActive] = useState("employee");
  const [ledger, setLedger] = useState(INITIAL_LEDGER);
  const [requests, setRequests] = useState([
    ...INITIAL_REQUESTS,
    ...INITIAL_TEAM_REQUESTS,
  ]);
  const [adjustments, setAdjustments] = useState([]);
  const [nextId, setNextId] = useState(300);

  const myRequests = requests.filter((r) => r.userId === CURRENT_USER.id);
  const managerQueue = requests.filter((r) =>
    ["pending", "cancel_pending"].includes(r.status),
  );

  /** Accept a new request, auto-approving it when the rules say so. */
  const handleSubmit = (draft) => {
    const balance = ledgerBalance(ledger);
    const available = balance - pendingReserved(myRequests);
    const notice = advanceNotice(draft.hours, draft.startDate, today());
    const auto = isAutoApproved(draft);

    const request = {
      id: nextId,
      userId: CURRENT_USER.id,
      userName: CURRENT_USER.name,
      userLevel: CURRENT_USER.level,
      balanceBefore: balance,
      type: draft.type,
      startDate: draft.startDate,
      endDate: draft.endDate,
      hours: draft.hours,
      status: auto ? "approved" : "pending",
      approverName: DEMO_MANAGER_NAME,
      reason: draft.reason,
      isOverdraft: draft.type === "paid" && draft.hours > available,
      isLateNotice: draft.type === "paid" && !notice.ok,
      requiredNoticeDays: notice.required,
      actualNoticeDays: notice.actual,
      decidedBy: auto ? "system" : null,
    };

    setNextId((n) => n + 1);
    setRequests((prev) => [request, ...prev]);
    // Auto-approved sick leave writes nothing, but keep the path uniform.
    const row = auto ? ledgerRowFor(request) : null;
    if (row) setLedger((prev) => [...prev, row]);
  };

  /** Pull back a request that nobody has decided yet. */
  const handleWithdraw = (id) =>
    setRequests((prev) =>
      prev.map((r) => (r.id === id ? { ...r, status: "withdrawn" } : r)),
    );

  /**
   * Ask to undo an approved request. Anything a manager approved goes back to
   * them; anything the system approved on its own is cancelled outright, since
   * there was never a person in the loop to consult.
   */
  const handleRequestCancel = (id) =>
    setRequests((prev) =>
      prev.map((r) => {
        if (r.id !== id) return r;
        if (r.decidedBy === "system") {
          const row = ledgerRowFor(r);
          if (row) {
            setLedger((rows) => [
              ...rows,
              { ...row, id: Date.now(), hours: -row.hours, note: "Cancelled" },
            ]);
          }
          return { ...r, status: "cancelled" };
        }
        return { ...r, status: "cancel_pending" };
      }),
    );

  /** Approve a request, or allow a cancellation and reverse its ledger row. */
  const handleApprove = (id) =>
    setRequests((prev) =>
      prev.map((r) => {
        if (r.id !== id) return r;
        if (r.status === "cancel_pending") {
          if (r.userId === CURRENT_USER.id) {
            const row = ledgerRowFor(r);
            if (row) {
              setLedger((rows) => [
                ...rows,
                {
                  ...row,
                  id: Date.now(),
                  entryType: "reversal",
                  hours: -row.hours,
                  note: `Reversal — cancelled request #${r.id}`,
                },
              ]);
            }
          }
          return { ...r, status: "cancelled", decidedBy: DEMO_MANAGER_NAME };
        }
        if (r.userId === CURRENT_USER.id) {
          const row = ledgerRowFor(r);
          if (row) setLedger((rows) => [...rows, row]);
        }
        return { ...r, status: "approved", decidedBy: DEMO_MANAGER_NAME };
      }),
    );

  /** Reject a request, or decline a cancellation and leave it approved. */
  const handleReject = (id, comment) =>
    setRequests((prev) =>
      prev.map((r) =>
        r.id === id
          ? {
              ...r,
              status: r.status === "cancel_pending" ? "approved" : "rejected",
              rejectComment: comment,
              decidedBy: DEMO_MANAGER_NAME,
            }
          : r,
      ),
    );

  /** Write an admin ledger row against the current user where applicable. */
  const handleAdjust = (row) => {
    setAdjustments((prev) => [row, ...prev]);
    if (row.personId === CURRENT_USER.id) {
      setLedger((prev) => [
        ...prev,
        {
          id: row.id,
          entryType: row.entryType,
          hours: row.hours,
          effectiveDate: row.effectiveDate,
          note: row.note,
        },
      ]);
    }
  };

  const pendingCount = managerQueue.length;

  return (
    <div className="flex min-h-screen bg-slate-50">
      <aside className="w-56 shrink-0 border-r border-slate-200 bg-white flex flex-col">
        <div className="px-4 py-4 border-b border-slate-100">
          <div className="flex items-center gap-2">
            <CalendarClock size={17} className="text-slate-700" />
            <span className="text-lg font-semibold text-slate-900">Leave</span>
            <Badge variant="outline" className="text-xs">
              v1
            </Badge>
          </div>
          <p className="text-xs text-slate-400 mt-0.5">Prototype · mock data</p>
        </div>

        <nav className="p-2 space-y-1">
          {NAV.map((item) => {
            const Icon = item.icon;
            const isActive = active === item.key;
            return (
              <button
                key={item.key}
                type="button"
                onClick={() => setActive(item.key)}
                className={`w-full flex items-center gap-2.5 px-3 py-2 rounded-lg text-sm transition-colors ${
                  isActive
                    ? "bg-slate-800 text-white"
                    : "text-slate-600 hover:bg-slate-100"
                }`}
              >
                <Icon size={16} />
                <span className="flex-1 text-left">{item.label}</span>
                {item.key === "manager" && pendingCount > 0 && (
                  <span
                    className={`text-xs rounded-full px-1.5 tabular-nums ${
                      isActive
                        ? "bg-white/20 text-white"
                        : "bg-slate-200 text-slate-700"
                    }`}
                  >
                    {pendingCount}
                  </span>
                )}
              </button>
            );
          })}
        </nav>

        <div className="mt-auto p-3">
          <p className="text-xs leading-relaxed text-slate-400">
            Every policy figure here is a placeholder, not the real policy.
            Entitlements, the weekend arrangement, and the holiday calendar are
            invented so this can be shown publicly.
          </p>
        </div>
      </aside>

      <main className="flex-1 min-w-0">
        {active === "employee" && (
          <EmployeeView
            ledger={ledger}
            requests={myRequests}
            onSubmit={handleSubmit}
            onWithdraw={handleWithdraw}
            onRequestCancel={handleRequestCancel}
          />
        )}
        {active === "manager" && (
          <ManagerView
            queue={managerQueue}
            onApprove={handleApprove}
            onReject={handleReject}
          />
        )}
        {active === "admin" && (
          <AdminView adjustments={adjustments} onAdjust={handleAdjust} />
        )}
      </main>
    </div>
  );
};

export default LeavePrototype;
