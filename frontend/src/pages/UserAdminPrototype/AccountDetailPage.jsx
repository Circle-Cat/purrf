import { useState } from "react";
import { ArrowLeft, ExternalLink, KeyRound, Mail } from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Textarea } from "@/components/ui/textarea";
import StateChips from "@/pages/UserAdminPrototype/StateChips";
import {
  actorName,
  fullName,
  statesOf,
} from "@/pages/UserAdminPrototype/accountState";
import { CURRENT_USER_ID } from "@/pages/UserAdminPrototype/mockData";

const Row = ({ label, children }) => (
  <div className="grid grid-cols-[7rem_1fr] gap-2 text-sm">
    <span className="text-slate-500">{label}</span>
    <span className="text-slate-900">{children}</span>
  </div>
);

const Section = ({ title, children }) => (
  <section className="space-y-2 border-t border-slate-200 pt-4">
    <h3 className="text-xs font-semibold uppercase tracking-wide text-slate-500">
      {title}
    </h3>
    {children}
  </section>
);

/**
 * AccountDetailPage
 *
 * Everything the console knows about one person, and every action it can take
 * on them.
 *
 * A page rather than a drawer, matching the recruiting detail pages: the way
 * out is a single link at the top left that names where it goes, and it
 * carries the caller's list state back so filters survive and the row you
 * came from is highlighted (`BackToBoardLink` does exactly this with `jobId`
 * and `focus`). In the shipped version this is a real route, so the back link
 * is a URL rather than a callback.
 *
 * The whole page sits behind user.admin, so there is no second permission gate
 * inside it. Permissions are a link out to the permission-management page
 * rather than a section here: that page keeps its own gate, and repeating the
 * check would put one rule in two places.
 *
 * @param {{user: object, request: object|null, onBack: Function,
 *   onDeactivate: Function, onReactivate: Function, onUnblock: Function,
 *   onBlock: Function, onDecide: Function}} props
 * @returns {JSX.Element}
 */
const AccountDetailPage = ({
  user,
  request,
  onBack,
  onDeactivate,
  onReactivate,
  onUnblock,
  onBlock,
  onDecide,
}) => {
  const [decisionNote, setDecisionNote] = useState("");

  const isSelf = user.userId === CURRENT_USER_ID;
  const decide = (approved) => {
    onDecide(request.id, approved, decisionNote.trim());
    setDecisionNote("");
  };

  return (
    <div className="max-w-3xl space-y-5">
      <button
        type="button"
        onClick={onBack}
        className="inline-flex items-center gap-1 text-sm font-medium text-slate-600 transition-colors hover:text-slate-900"
      >
        <ArrowLeft className="h-4 w-4" aria-hidden />
        Accounts
      </button>

      <header className="flex flex-wrap items-center gap-2">
        <h1 className="text-xl font-semibold text-slate-900">
          {fullName(user)}
        </h1>
        <span className="text-sm text-slate-500">user {user.userId}</span>
        {user.isSuperAdmin && (
          <Badge
            variant="outline"
            className="border-violet-300 bg-violet-50 text-violet-800"
          >
            Super admin
          </Badge>
        )}
      </header>

      <section className="space-y-2">
        <Row label="Name">
          {fullName(user)}
          {user.preferredName ? ` ("${user.preferredName}")` : ""}
        </Row>
        <Row label="Type">
          {user.userType === "internal" ? "Internal" : "External"}
        </Row>
        <Row label="Contact">{user.contactEmail}</Row>
        <Row label="Created">{user.createdOn}</Row>
      </section>

      {request && request.status === "pending" && (
        <section className="space-y-3 rounded-md border border-amber-300 bg-amber-50 p-4">
          <h2 className="text-sm font-semibold text-amber-900">
            Block request awaiting your decision
          </h2>
          <div className="space-y-1 text-sm text-amber-900">
            <p>
              Raised by {request.raisedBy} from {request.raisedFrom} on{" "}
              {request.raisedOn}
            </p>
            <p className="rounded border border-amber-200 bg-white/70 p-2 text-slate-800">
              {request.reason}
            </p>
          </div>
          <Textarea
            value={decisionNote}
            onChange={(e) => setDecisionNote(e.target.value)}
            placeholder="Decision note — optional, sent back to the requester"
            rows={2}
          />
          <div className="flex gap-2">
            <Button variant="destructive" onClick={() => decide(true)}>
              Approve and block
            </Button>
            <Button variant="outline" onClick={() => decide(false)}>
              Reject request
            </Button>
          </div>
          <p className="text-xs text-amber-800">
            Approving applies the block immediately, with the same consequences
            shown when it was raised.
          </p>
        </section>
      )}

      <Section title="Account state">
        <StateChips
          states={statesOf(
            user,
            Boolean(request && request.status === "pending"),
          )}
        />
        {!user.isActive && (
          <p className="text-sm text-slate-700">
            Deactivated {user.deactivatedAt} by {actorName(user.deactivatedBy)}
            {user.deactivatedReason ? ` — "${user.deactivatedReason}"` : ""}
          </p>
        )}
        {user.isBlocked && (
          <p className="text-sm text-slate-700">
            Blocked {user.blockedAt} by {actorName(user.blockedBy)} —{" "}
            {user.blockedReason}
          </p>
        )}
      </Section>

      <Section title="Sign-in methods">
        {user.emails.map((entry) => (
          <div key={entry.address} className="flex items-center gap-2 text-sm">
            <Mail size={14} className="text-slate-400" />
            <span className="text-slate-900">{entry.address}</span>
            <span className="text-xs text-slate-500">
              {entry.confirmed ? "confirmed" : "unconfirmed"}
              {entry.primary ? " · primary" : ""}
            </span>
          </div>
        ))}
        {user.identities.map((entry) => (
          <div key={entry.claim} className="flex items-center gap-2 text-sm">
            <KeyRound size={14} className="text-slate-400" />
            <span className="text-slate-900">
              {entry.provider} · {entry.claim}
            </span>
          </div>
        ))}
        {user.identities.length === 0 && (
          <p className="text-xs text-slate-500">
            No linked identity. This account has only ever signed in with an
            emailed code, which leaves no identity row by design.
          </p>
        )}
        <p className="pt-1 text-xs text-slate-500">
          Read-only. Removing or relinking a sign-in method is not part of this
          console.
        </p>
      </Section>

      <Section title="Actions">
        <div className="flex flex-wrap gap-2">
          {user.isActive ? (
            <Button
              variant="outline"
              disabled={isSelf}
              onClick={() => onDeactivate(user)}
            >
              Deactivate
            </Button>
          ) : (
            <Button variant="outline" onClick={() => onReactivate(user)}>
              Reactivate
            </Button>
          )}
          {user.isBlocked ? (
            <Button variant="outline" onClick={() => onUnblock(user)}>
              Unblock
            </Button>
          ) : (
            <Button
              variant="destructive"
              disabled={isSelf}
              onClick={() => onBlock(user)}
            >
              Block
            </Button>
          )}
        </div>
        {isSelf && (
          <p className="text-xs text-slate-500">
            You cannot deactivate or block yourself — it would lock you out of
            the console needed to undo it.
          </p>
        )}
      </Section>

      <Section title="Permissions">
        <a
          className="inline-flex items-center gap-1.5 text-sm font-medium text-blue-700 hover:underline"
          href="#users"
          onClick={(e) => e.preventDefault()}
        >
          Manage permissions
          <ExternalLink size={13} />
        </a>
        <p className="text-xs text-slate-500">
          Opens the permission-management page with this person selected. That
          page enforces its own gate.
        </p>
      </Section>
    </div>
  );
};

export default AccountDetailPage;
