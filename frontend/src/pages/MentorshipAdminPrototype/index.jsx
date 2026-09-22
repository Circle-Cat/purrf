import { useCallback, useMemo, useState } from "react";
import ManagementPage from "@/pages/MentorshipAdminPrototype/ManagementPage";
import ParticipantDetailPage from "@/pages/MentorshipAdminPrototype/ParticipantDetailPage";
import PairDetailPage from "@/pages/MentorshipAdminPrototype/PairDetailPage";
import NoteDialog from "@/pages/MentorshipAdminPrototype/NoteDialog";
import RaiseRequestDialog from "@/pages/MentorshipAdminPrototype/RaiseRequestDialog";
import ComposeDialog from "@/pages/MentorshipAdminPrototype/ComposeDialog";
import RoundModal from "@/pages/MentorshipAdminPrototype/RoundModal";
import {
  ALL_PERMISSIONS,
  CURRENT_USER,
  DEFAULT_PERMISSIONS,
  INITIAL_FEEDBACK,
  INITIAL_MEETINGS,
  INITIAL_NOTES,
  INITIAL_PAIRS,
  INITIAL_PARTICIPANTS,
  INITIAL_REQUESTS,
  INITIAL_ROUNDS,
  NON_PARTICIPANTS,
} from "@/pages/MentorshipAdminPrototype/mockData";

const TODAY = "2026-09-22";

let nextId = 1;
const newId = (prefix) => `${prefix}-${nextId++}`;

/**
 * MentorshipAdminPrototype
 *
 * Self-contained, mock-data prototype of the redesigned mentorship admin
 * console. No backend, no auth, no environment variables; refreshing resets
 * everything.
 *
 * Three things here are the design rather than decoration, and each is hard to
 * convey in a document:
 *
 *   1. A mentor with two mentees is one row on the person axis and two on the
 *      pair axis. That is the whole reason the search is split in two.
 *   2. Marking someone "no show" is not writing a note — it raises a request,
 *      and the note only appears once somebody with the approve permission
 *      decides it. Toggle the permissions in the header to watch the same
 *      action change shape.
 *   3. Feedback a participant wrote about their partner is readable here and
 *      never by the partner. The label always says whose opinion it is.
 *
 * @returns {JSX.Element}
 */
const MentorshipAdminPrototype = () => {
  const [permissions, setPermissions] = useState(DEFAULT_PERMISSIONS);
  const [view, setView] = useState({ kind: "management" });

  const [rounds, setRounds] = useState(INITIAL_ROUNDS);
  const [participants, setParticipants] = useState(INITIAL_PARTICIPANTS);
  const [pairs, setPairs] = useState(INITIAL_PAIRS);
  const [meetings] = useState(INITIAL_MEETINGS);
  const [notes, setNotes] = useState(INITIAL_NOTES);
  const [requests, setRequests] = useState(INITIAL_REQUESTS);

  const [roundId, setRoundId] = useState(7);
  const [noteTarget, setNoteTarget] = useState(null);
  const [requestTarget, setRequestTarget] = useState(null);
  const [composeTarget, setComposeTarget] = useState(null);
  const [roundModal, setRoundModal] = useState(null);

  const can = useCallback(
    (permission) => permissions.includes(permission),
    [permissions],
  );

  const togglePermission = (key) =>
    setPermissions((held) =>
      held.includes(key) ? held.filter((p) => p !== key) : [...held, key],
    );

  const addNote = useCallback(({ participantId, pairId, tag, body }) => {
    setNotes((all) => [
      {
        noteId: newId("n"),
        participantId,
        pairId: pairId ?? null,
        tag: tag || null,
        body,
        authorId: CURRENT_USER.userId,
        createdAt: TODAY,
      },
      ...all,
    ]);
  }, []);

  const raiseRequest = useCallback(
    ({ action, participantId, pairId, targetLabel, reason }) => {
      setRequests((all) => [
        {
          requestId: Number(`9${nextId++}`.padEnd(4, "0")),
          action,
          roundId,
          targetLabel,
          participantId,
          pairId: pairId ?? null,
          reason,
          raisedBy: CURRENT_USER.userId,
          createdAt: TODAY,
          status: "pending",
        },
        ...all,
      ]);
    },
    [roundId],
  );

  /**
   * Deciding is where the approval becomes real: the state change, the note
   * and the decision are one step. Splitting them would leave a window where
   * a request reads "approved" and nothing has happened.
   */
  const decideRequest = useCallback(
    (requestId, approved, decisionNote) => {
      setRequests((all) =>
        all.map((r) =>
          r.requestId === requestId
            ? {
                ...r,
                status: approved ? "approved" : "rejected",
                decidedBy: CURRENT_USER.userId,
                decidedAt: TODAY,
                decisionNote,
              }
            : r,
        ),
      );

      const request = requests.find((r) => r.requestId === requestId);
      if (!request || !approved) return;

      const tagOf = {
        mark_no_show: "no_show",
        mark_red_flag: "red_flag",
        change_partner: "partner_change_request",
        withdraw: "status_change",
      };

      addNote({
        participantId: request.participantId,
        pairId: request.pairId,
        tag: tagOf[request.action],
        body: `${request.reason} — raised by ${
          CURRENT_USER.name
        }, approved by ${CURRENT_USER.name}.`,
      });

      if (request.action === "withdraw") {
        setParticipants((all) =>
          all.map((p) =>
            p.participantId === request.participantId
              ? { ...p, approvalStatus: "withdrawn" }
              : p,
          ),
        );
        setPairs((all) =>
          all.map((p) =>
            p.pairId === request.pairId ? { ...p, status: "inactive" } : p,
          ),
        );
      }
    },
    [addNote, requests],
  );

  /**
   * Toggling a cell on the pair axis.
   *
   * The pair is looked up from current state before any setter runs: calling
   * one updater from inside another runs it twice under StrictMode, which
   * would toggle the mark straight back off again.
   */
  const markCell = useCallback(
    (pairId, field) => {
      if (field === "firstContact") {
        setPairs((all) =>
          all.map((p) =>
            p.pairId === pairId
              ? {
                  ...p,
                  firstContactConfirmedAt: p.firstContactConfirmedAt
                    ? null
                    : TODAY,
                }
              : p,
          ),
        );
        return;
      }
      const pair = pairs.find((p) => p.pairId === pairId);
      if (!pair) return;
      setParticipants((people) =>
        people.map((person) =>
          person.userId === pair.menteeId && person.roundId === pair.roundId
            ? {
                ...person,
                midtermReminderAt: person.midtermReminderAt ? null : TODAY,
              }
            : person,
        ),
      );
    },
    [pairs],
  );

  const saveRound = useCallback((draft) => {
    setRounds((all) =>
      all.some((r) => r.id === draft.id)
        ? all.map((r) => (r.id === draft.id ? draft : r))
        : [{ ...draft, id: Math.max(...all.map((r) => r.id)) + 1 }, ...all],
    );
    setRoundModal(null);
  }, []);

  const round = useMemo(
    () => rounds.find((r) => r.id === roundId) ?? rounds[0],
    [rounds, roundId],
  );

  const body = () => {
    if (view.kind === "participant") {
      const person = participants.find(
        (p) => p.participantId === view.participantId,
      );
      return (
        <ParticipantDetailPage
          person={person}
          rounds={rounds}
          participants={participants}
          pairs={pairs}
          notes={notes}
          feedback={INITIAL_FEEDBACK}
          can={can}
          onBack={() => setView({ kind: "management" })}
          onOpenPair={(pairId) => setView({ kind: "pair", pairId })}
          onAddNote={() =>
            setNoteTarget({ participantId: person.participantId })
          }
          onRaise={() =>
            setRequestTarget({
              participantId: person.participantId,
              targetLabel: person.name,
            })
          }
          onCompose={() => setComposeTarget({ recipients: [person.name] })}
        />
      );
    }

    if (view.kind === "pair") {
      const pair = pairs.find((p) => p.pairId === view.pairId);
      return (
        <PairDetailPage
          pair={pair}
          round={rounds.find((r) => r.id === pair.roundId)}
          meetings={meetings.filter((m) => m.pairId === pair.pairId)}
          notes={notes.filter((n) => n.pairId === pair.pairId)}
          requests={requests.filter((r) => r.pairId === pair.pairId)}
          can={can}
          onBack={() => setView({ kind: "management" })}
          onAddNote={() =>
            setNoteTarget({
              participantId: participants.find(
                (p) => p.userId === pair.menteeId && p.roundId === pair.roundId,
              )?.participantId,
              pairId: pair.pairId,
            })
          }
        />
      );
    }

    return (
      <ManagementPage
        round={round}
        rounds={rounds}
        onSelectRound={setRoundId}
        participants={participants}
        nonParticipants={NON_PARTICIPANTS}
        pairs={pairs}
        requests={requests}
        can={can}
        onDecide={decideRequest}
        onOpenParticipant={(participantId) =>
          setView({ kind: "participant", participantId })
        }
        onOpenPair={(pairId) => setView({ kind: "pair", pairId })}
        onMarkCell={markCell}
        onCompose={(recipients) => setComposeTarget({ recipients })}
        onBulkMark={(participantIds, tag) =>
          participantIds.forEach((participantId) =>
            addNote({ participantId, tag, body: "" }),
          )
        }
        onEditRound={(r) => setRoundModal(r ?? { timeline: {} })}
      />
    );
  };

  return (
    <div className="min-h-screen bg-slate-50 text-slate-900">
      <header className="border-b border-slate-200 bg-white">
        <div className="mx-auto flex max-w-6xl flex-wrap items-center gap-3 px-6 py-3">
          <span className="text-sm font-semibold">Mentorship management</span>
          <span className="text-xs text-slate-500">
            signed in as {CURRENT_USER.name}
          </span>
          <div
            role="group"
            aria-label="Permissions"
            className="ml-auto flex items-center gap-2"
          >
            <span className="text-xs uppercase tracking-wide text-slate-400">
              Permissions
            </span>
            {ALL_PERMISSIONS.map((p) => (
              <button
                key={p.key}
                type="button"
                aria-pressed={can(p.key)}
                onClick={() => togglePermission(p.key)}
                className={`rounded-md border px-2 py-1 text-xs transition-colors ${
                  can(p.key)
                    ? "border-slate-900 bg-slate-900 text-white"
                    : "border-slate-300 text-slate-500 hover:bg-slate-100"
                }`}
              >
                {p.label}
              </button>
            ))}
          </div>
        </div>
      </header>

      <main className="mx-auto max-w-6xl px-6 py-6">
        {can("mentorship.admin.read") || can("mentorship.approve") ? (
          body()
        ) : (
          <p className="rounded-md border border-slate-200 bg-white p-6 text-sm text-slate-600">
            You need the read or approve permission to see this page.
          </p>
        )}
      </main>

      <NoteDialog
        target={noteTarget}
        onClose={() => setNoteTarget(null)}
        onSave={(payload) => {
          addNote({ ...noteTarget, ...payload });
          setNoteTarget(null);
        }}
      />
      <RaiseRequestDialog
        target={requestTarget}
        onClose={() => setRequestTarget(null)}
        onSave={(payload) => {
          raiseRequest({ ...requestTarget, ...payload });
          setRequestTarget(null);
        }}
      />
      <ComposeDialog
        target={composeTarget}
        onClose={() => setComposeTarget(null)}
      />
      <RoundModal
        round={roundModal}
        onClose={() => setRoundModal(null)}
        onSave={saveRound}
      />
    </div>
  );
};

export default MentorshipAdminPrototype;
