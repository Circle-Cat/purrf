import { useCallback, useMemo, useState } from "react";
import { GraduationCap, Briefcase, ShieldCheck } from "lucide-react";
import AccountsPage from "@/pages/UserAdminPrototype/AccountsPage";
import AccountDetailPage from "@/pages/UserAdminPrototype/AccountDetailPage";
import BlockDialog from "@/pages/UserAdminPrototype/BlockDialog";
import DeactivateDialog from "@/pages/UserAdminPrototype/DeactivateDialog";
import DomainView from "@/pages/UserAdminPrototype/DomainView";
import {
  CURRENT_USER_ID,
  INITIAL_REQUESTS,
  INITIAL_USERS,
  MENTORSHIP_ROWS,
  RECRUITING_ROWS,
} from "@/pages/UserAdminPrototype/mockData";

/**
 * The three vantage points. Each one is a permission the design hands out
 * separately, and what you can do changes completely between them — which is
 * the single hardest thing to convey in writing.
 */
const NAV = [
  {
    key: "ops",
    label: "Operations",
    permission: "user.admin",
    icon: ShieldCheck,
  },
  {
    key: "recruiting",
    label: "Recruiting",
    permission: "recruiting.application.advance",
    icon: Briefcase,
  },
  {
    key: "mentorship",
    label: "Mentorship",
    permission: "mentorship.admin.write",
    icon: GraduationCap,
  },
];

const TODAY = "2026-09-03";

/**
 * UserAdminPrototype
 *
 * Self-contained, mock-data prototype of the user account console and the
 * block request-and-approve flow around it.
 *
 * The three views share one set of state on purpose: a request raised on the
 * Recruiting or Mentorship view appears in the Operations banner, and the
 * decision made there flows back to the row that raised it. That coupling is
 * the design — a block is one process crossing three surfaces, not three
 * screens that happen to mention the same person.
 *
 * No backend, no auth, no environment variables. Refreshing resets everything.
 *
 * @returns {JSX.Element}
 */
const UserAdminPrototype = () => {
  const [view, setView] = useState("ops");
  const [users, setUsers] = useState(INITIAL_USERS);
  const [requests, setRequests] = useState(INITIAL_REQUESTS);
  const [openUserId, setOpenUserId] = useState(null);
  const [focusUserId, setFocusUserId] = useState(null);
  const [filters, setFilters] = useState({
    term: "",
    type: "all",
    status: "all",
  });
  const [page, setPage] = useState(0);
  const [deactivating, setDeactivating] = useState(null);
  const [blocking, setBlocking] = useState(null);
  const [blockMode, setBlockMode] = useState("apply");

  const userById = useCallback(
    (userId) => users.find((u) => u.userId === userId),
    [users],
  );

  const pendingFor = useCallback(
    (userId) =>
      requests.find(
        (r) => r.targetUserId === userId && r.status === "pending",
      ) ?? null,
    [requests],
  );

  const latestFor = useCallback(
    (userId) =>
      [...requests].reverse().find((r) => r.targetUserId === userId) ?? null,
    [requests],
  );

  const patchUser = (userId, patch) =>
    setUsers((prev) =>
      prev.map((u) => (u.userId === userId ? { ...u, ...patch } : u)),
    );

  const applyBlock = (userId, reason) =>
    patchUser(userId, {
      isBlocked: true,
      blockedAt: TODAY,
      blockedBy: CURRENT_USER_ID,
      blockedReason: reason,
    });

  const confirmBlockDialog = (reason, reviewer) => {
    const target = blocking;
    setBlocking(null);
    if (blockMode === "apply") {
      applyBlock(target.userId, reason);
      return;
    }
    setRequests((prev) => [
      ...prev,
      {
        id: Date.now(),
        targetUserId: target.userId,
        raisedBy: view === "recruiting" ? "Silva, Marco" : "Okonkwo, Ada",
        raisedFrom:
          view === "recruiting" ? "Screening board" : "Mentorship management",
        raisedOn: TODAY,
        reason,
        reviewerId: reviewer.userId,
        reviewerName: reviewer.name,
        status: "pending",
        decidedBy: null,
        decidedOn: null,
        decisionNote: null,
      },
    ]);
  };

  const decideRequest = (requestId, approved, note) => {
    const request = requests.find((r) => r.id === requestId);
    setRequests((prev) =>
      prev.map((r) =>
        r.id === requestId
          ? {
              ...r,
              status: approved ? "approved" : "rejected",
              decidedBy: "Wang, Yanpei",
              decidedOn: TODAY,
              decisionNote: note || null,
            }
          : r,
      ),
    );
    if (approved) applyBlock(request.targetUserId, request.reason);
  };

  const openUser = userById(openUserId) ?? null;
  const openRequest = openUserId ? pendingFor(openUserId) : null;

  /** Opening a person remembers the row, so the trip back can highlight it. */
  const openAccount = (userId) => {
    setFocusUserId(userId);
    setOpenUserId(userId);
  };

  const domainProps = useMemo(
    () => ({
      userById,
      requestFor: latestFor,
      onRequest: (user) => {
        setBlockMode("request");
        setBlocking(user);
      },
    }),
    [userById, latestFor],
  );

  return (
    <div className="min-h-full bg-slate-50">
      <nav className="flex flex-wrap items-center gap-2 border-b border-slate-200 bg-white px-4 py-2">
        <span className="mr-2 text-xs uppercase tracking-wide text-slate-400">
          Signed in as
        </span>
        {NAV.map((item) => {
          const Icon = item.icon;
          const active = item.key === view;
          return (
            <button
              key={item.key}
              type="button"
              onClick={() => setView(item.key)}
              className={`flex items-center gap-1.5 rounded-md border px-3 py-1.5 text-sm transition-colors ${
                active
                  ? "border-slate-900 bg-slate-900 text-white"
                  : "border-slate-300 bg-white text-slate-700 hover:bg-slate-100"
              }`}
            >
              <Icon size={14} />
              {item.label}
              <code
                className={`ml-1 rounded px-1 text-[11px] ${
                  active
                    ? "bg-slate-700 text-slate-200"
                    : "bg-slate-100 text-slate-500"
                }`}
              >
                {item.permission}
              </code>
            </button>
          );
        })}
      </nav>

      <main className="mx-auto max-w-5xl p-6">
        {view === "ops" &&
          (openUser ? (
            <AccountDetailPage
              user={openUser}
              request={openRequest}
              onBack={() => setOpenUserId(null)}
              onDeactivate={setDeactivating}
              onReactivate={(user) =>
                patchUser(user.userId, {
                  isActive: true,
                  deactivatedAt: null,
                  deactivatedBy: null,
                  deactivatedReason: null,
                })
              }
              onUnblock={(user) =>
                patchUser(user.userId, {
                  isBlocked: false,
                  blockedAt: null,
                  blockedBy: null,
                  blockedReason: null,
                })
              }
              onBlock={(user) => {
                setBlockMode("apply");
                setBlocking(user);
              }}
              onDecide={decideRequest}
            />
          ) : (
            <AccountsPage
              users={users}
              requests={requests}
              filters={filters}
              onFilters={setFilters}
              page={page}
              onPage={setPage}
              focusUserId={focusUserId}
              onOpen={openAccount}
            />
          ))}

        {view === "recruiting" && (
          <DomainView
            title="Screening board"
            subtitle="Candidates on postings you own. Blocking is judged from the interview record, which is here."
            columns={[
              { key: "posting", label: "Posting" },
              { key: "stage", label: "Stage" },
            ]}
            rows={RECRUITING_ROWS}
            {...domainProps}
          />
        )}

        {view === "mentorship" && (
          <DomainView
            title="Mentorship management"
            subtitle="Participants in the current round. No-show counts and red flags are on this table, so the action belongs here too."
            columns={[
              { key: "role", label: "Role" },
              { key: "partner", label: "Partner" },
              { key: "noShows", label: "No-shows" },
            ]}
            rows={MENTORSHIP_ROWS}
            {...domainProps}
          />
        )}
      </main>

      <DeactivateDialog
        user={deactivating}
        onCancel={() => setDeactivating(null)}
        onConfirm={(note) => {
          patchUser(deactivating.userId, {
            isActive: false,
            deactivatedAt: TODAY,
            deactivatedBy: CURRENT_USER_ID,
            deactivatedReason: note || null,
          });
          setDeactivating(null);
        }}
      />

      <BlockDialog
        user={blocking}
        mode={blockMode}
        onCancel={() => setBlocking(null)}
        onConfirm={confirmBlockDialog}
      />
    </div>
  );
};

export default UserAdminPrototype;
