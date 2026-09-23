import { useCallback, useEffect, useMemo, useState } from "react";
import ManagementPage from "@/pages/MentorshipAdminPrototype/ManagementPage";
import ParticipantDetailPage from "@/pages/MentorshipAdminPrototype/ParticipantDetailPage";
import PairDetailPage from "@/pages/MentorshipAdminPrototype/PairDetailPage";
import NoteDialog from "@/pages/MentorshipAdminPrototype/NoteDialog";
import RaiseRequestDialog from "@/pages/MentorshipAdminPrototype/RaiseRequestDialog";
import ComposeDialog from "@/pages/MentorshipAdminPrototype/ComposeDialog";
import RoundModal from "@/pages/MentorshipAdminPrototype/RoundModal";
import {
  ACTOR_NAMES,
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
const CURRENT_ROUND_ID = 7;
const HASH_ROOT = "mentorship";

let nextId = 1;
const newId = (prefix) => `${prefix}-${nextId++}`;

/**
 * Where the reader is, read from the URL hash.
 *
 * The Pages bundle has no router, so the hash stands in for the real routes:
 * `#mentorship/participants/:id`, `#mentorship/pairs/:id`, and
 * `#mentorship?tab=…&q=…` for the list. The list's tab, round and filters live
 * in the query so that opening a detail page and coming back lands on the same
 * filtered list — the one cost of making details full pages instead of drawers.
 */
const parseLocation = () => {
  const [path, search = ""] = window.location.hash.replace(/^#/, "").split("?");
  const [root, kind, id] = path.split("/");
  const query = Object.fromEntries(new URLSearchParams(search));
  if (root === HASH_ROOT && kind === "participants" && id) {
    return {
      view: { kind: "participant", participantId: decodeURIComponent(id) },
      query,
    };
  }
  if (root === HASH_ROOT && kind === "pairs" && id) {
    return { view: { kind: "pair", pairId: Number(id) }, query };
  }
  return { view: { kind: "management" }, query };
};

const toHash = (view, query) => {
  if (view.kind === "participant") {
    return `#${HASH_ROOT}/participants/${encodeURIComponent(view.participantId)}`;
  }
  if (view.kind === "pair") return `#${HASH_ROOT}/pairs/${view.pairId}`;
  const search = new URLSearchParams(query).toString();
  return `#${HASH_ROOT}${search ? `?${search}` : ""}`;
};

/** Drops empty and default values so a shared link carries only real choices. */
const cleanQuery = (query) =>
  Object.fromEntries(
    Object.entries(query).filter(([, v]) => v !== "" && v !== "all" && v),
  );

/**
 * MentorshipAdminPrototype
 *
 * Self-contained, mock-data prototype of the redesigned mentorship admin
 * console. No backend, no auth, no environment variables; refreshing resets
 * the data (the URL, and so the current list filter, survives).
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
  const [location, setLocation] = useState(parseLocation);
  const [listQuery, setListQuery] = useState(() =>
    location.view.kind === "management" ? location.query : {},
  );

  const [rounds, setRounds] = useState(INITIAL_ROUNDS);
  const [participants, setParticipants] = useState(INITIAL_PARTICIPANTS);
  const [pairs, setPairs] = useState(INITIAL_PAIRS);
  const [meetings] = useState(INITIAL_MEETINGS);
  const [notes, setNotes] = useState(INITIAL_NOTES);
  const [requests, setRequests] = useState(INITIAL_REQUESTS);

  const [noteTarget, setNoteTarget] = useState(null);
  const [requestTarget, setRequestTarget] = useState(null);
  const [composeTarget, setComposeTarget] = useState(null);
  const [roundModal, setRoundModal] = useState(null);

  const view = location.view;
  const roundId = Number(listQuery.round ?? CURRENT_ROUND_ID);

  useEffect(() => {
    const sync = () => {
      const next = parseLocation();
      setLocation(next);
      if (next.view.kind === "management") setListQuery(next.query);
    };
    window.addEventListener("hashchange", sync);
    return () => window.removeEventListener("hashchange", sync);
  }, []);

  /** Moving between pages pushes a history entry, so the browser's back works too. */
  const navigate = useCallback((nextView, query = {}) => {
    setLocation({ view: nextView, query });
    if (nextView.kind === "management") setListQuery(query);
    const hash = toHash(nextView, query);
    if (window.location.hash !== hash) window.location.hash = hash;
  }, []);

  /** Filter changes replace the entry instead: typing a search is not a page. */
  const updateListQuery = useCallback(
    (patch) => {
      const query = cleanQuery({ ...listQuery, ...patch });
      setListQuery(query);
      setLocation({ view: { kind: "management" }, query });
      window.history.replaceState(
        null,
        "",
        toHash({ kind: "management" }, query),
      );
    },
    [listQuery],
  );

  const backToList = useCallback(
    () => navigate({ kind: "management" }, listQuery),
    [navigate, listQuery],
  );

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
    ({
      action,
      roundId: targetRoundId,
      participantId,
      participantIds,
      pairId,
      targetLabel,
      reason,
    }) => {
      setRequests((all) => [
        {
          requestId: Number(`9${nextId++}`.padEnd(4, "0")),
          action,
          roundId: targetRoundId,
          targetLabel,
          participantId: participantId ?? null,
          participantIds: participantIds ?? null,
          pairId: pairId ?? null,
          reason,
          raisedBy: CURRENT_USER.userId,
          createdAt: TODAY,
          status: "pending",
        },
        ...all,
      ]);
    },
    [],
  );

  /** Pending requests already aimed at any of the same people, or the same pair. */
  const pendingFor = useCallback(
    ({ participantId, participantIds, pairId }) => {
      const ids = participantIds ?? (participantId ? [participantId] : []);
      return requests.filter(
        (r) =>
          r.status === "pending" &&
          ((pairId && r.pairId === pairId) ||
            ids.some(
              (id) => r.participantId === id || r.participantIds?.includes(id),
            )),
      );
    },
    [requests],
  );

  /**
   * Deciding is where the approval becomes real: the state change, the note
   * and the decision are one step. Splitting them would leave a window where
   * a request reads "approved" and nothing has happened.
   */
  const decideRequest = useCallback(
    (requestId, approved, decisionNote) => {
      const request = requests.find((r) => r.requestId === requestId);
      if (!request) return;

      // Withdrawing takes the person's pairs with them, whichever pair the
      // request was raised from.
      const withdrawing =
        approved && request.action === "withdraw"
          ? participants.find((p) => p.participantId === request.participantId)
          : null;
      const affectedPairIds = withdrawing
        ? pairs
            .filter(
              (p) =>
                p.roundId === withdrawing.roundId &&
                p.status === "active" &&
                (p.mentorId === withdrawing.userId ||
                  p.menteeId === withdrawing.userId),
            )
            .map((p) => p.pairId)
        : [];

      setRequests((all) =>
        all.map((r) =>
          r.requestId === requestId
            ? {
                ...r,
                status: approved ? "approved" : "rejected",
                decidedBy: CURRENT_USER.userId,
                decidedAt: TODAY,
                decisionNote,
                affectedPairIds,
              }
            : r,
        ),
      );

      if (!approved) return;

      const tagOf = {
        mark_no_show: "no_show",
        mark_red_flag: "red_flag",
        change_partner: "partner_change_request",
        withdraw: "status_change",
        confirm_unmatched: "status_change",
      };
      const body = `${request.reason} — raised by ${
        ACTOR_NAMES[request.raisedBy]
      }, approved by ${CURRENT_USER.name}.${
        decisionNote ? ` ${decisionNote}` : ""
      }`;

      if (request.action === "confirm_unmatched") {
        request.participantIds.forEach((participantId) =>
          addNote({
            participantId,
            tag: tagOf.confirm_unmatched,
            body: `signed_up → un_matched. ${body}`,
          }),
        );
        setParticipants((all) =>
          all.map((p) =>
            request.participantIds.includes(p.participantId)
              ? { ...p, approvalStatus: "un_matched" }
              : p,
          ),
        );
        return;
      }

      addNote({
        participantId: request.participantId,
        pairId:
          request.pairId ??
          (affectedPairIds.length === 1 ? affectedPairIds[0] : null),
        tag: tagOf[request.action],
        body,
      });

      if (withdrawing) {
        setParticipants((all) =>
          all.map((p) =>
            p.participantId === withdrawing.participantId
              ? { ...p, approvalStatus: "withdrawn" }
              : p,
          ),
        );
        setPairs((all) =>
          all.map((p) =>
            affectedPairIds.includes(p.pairId)
              ? { ...p, status: "inactive" }
              : p,
          ),
        );
      }
    },
    [addNote, requests, participants, pairs],
  );

  const menteeParticipantOf = useCallback(
    (pair) =>
      participants.find(
        (p) => p.userId === pair.menteeId && p.roundId === pair.roundId,
      ),
    [participants],
  );

  /**
   * Setting a mark on the pair axis.
   *
   * Setting one opens the note box first, so a reply summary can go in with
   * it; clearing one is a correction and happens straight away. The pair is
   * looked up from current state before any setter runs: calling one updater
   * from inside another runs it twice under StrictMode, which would toggle the
   * mark straight back off again.
   */
  const applyMark = useCallback(
    (pairId, field, on) => {
      const pair = pairs.find((p) => p.pairId === pairId);
      if (!pair) return;
      if (field === "firstContact") {
        setPairs((all) =>
          all.map((p) =>
            p.pairId === pairId
              ? { ...p, firstContactConfirmedAt: on ? TODAY : null }
              : p,
          ),
        );
        return;
      }
      setParticipants((people) =>
        people.map((person) =>
          person.userId === pair.menteeId && person.roundId === pair.roundId
            ? { ...person, midtermReminderAt: on ? TODAY : null }
            : person,
        ),
      );
    },
    [pairs],
  );

  const markCell = useCallback(
    (pairId, field) => {
      const pair = pairs.find((p) => p.pairId === pairId);
      if (!pair) return;
      const mentee = menteeParticipantOf(pair);
      const isOn =
        field === "firstContact"
          ? Boolean(pair.firstContactConfirmedAt)
          : Boolean(mentee?.midtermReminderAt);
      if (isOn) {
        applyMark(pairId, field, false);
        return;
      }
      setNoteTarget({
        participantId: mentee?.participantId,
        pairId,
        mark: field,
        title:
          field === "firstContact"
            ? `First contact confirmed — ${pair.mentorName} ↔ ${pair.menteeName}`
            : `Mid-term reminder sent — ${pair.menteeName}`,
        fixedTag:
          field === "firstContact" ? "status_change" : "midterm_reminder",
      });
    },
    [pairs, menteeParticipantOf, applyMark],
  );

  /**
   * Marking many people at once, after sending on Teams.
   *
   * The mid-term reminder is a real column, not only a note, so marking it in
   * bulk has to light the same cell a single click does.
   */
  const bulkMark = useCallback(
    (participantIds, tag) => {
      participantIds.forEach((participantId) =>
        addNote({ participantId, tag, body: "" }),
      );
      if (tag !== "midterm_reminder") return;
      setParticipants((all) =>
        all.map((p) =>
          participantIds.includes(p.participantId) && p.role === "mentee"
            ? { ...p, midtermReminderAt: TODAY }
            : p,
        ),
      );
    },
    [addNote],
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

  const pairLabel = (p) => `${p.mentorName} ↔ ${p.menteeName}`;
  const backLabel = listQuery.tab === "pairs" ? "← Pairs" : "← Participants";

  const body = () => {
    if (view.kind === "participant") {
      const person = participants.find(
        (p) => p.participantId === view.participantId,
      );
      if (!person) return null;
      const personPairs = pairs.filter(
        (p) =>
          p.roundId === person.roundId &&
          (p.mentorId === person.userId || p.menteeId === person.userId),
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
          backLabel={backLabel}
          onBack={backToList}
          onOpenPair={(pairId) => navigate({ kind: "pair", pairId })}
          onAddNote={() =>
            setNoteTarget({ participantId: person.participantId })
          }
          onRaise={() =>
            setRequestTarget({
              roundId: person.roundId,
              participantId: person.participantId,
              targetLabel: person.name,
              actions: ["withdraw", "mark_no_show", "mark_red_flag"].concat(
                personPairs.length ? ["change_partner"] : [],
              ),
              pairChoices: personPairs.map((p) => ({
                pairId: p.pairId,
                label: pairLabel(p),
              })),
            })
          }
          onCompose={() => setComposeTarget({ recipients: [person.name] })}
        />
      );
    }

    if (view.kind === "pair") {
      const pair = pairs.find((p) => p.pairId === view.pairId);
      if (!pair) return null;
      return (
        <PairDetailPage
          pair={pair}
          round={rounds.find((r) => r.id === pair.roundId)}
          meetings={meetings.filter((m) => m.pairId === pair.pairId)}
          notes={notes.filter((n) => n.pairId === pair.pairId)}
          requests={requests.filter(
            (r) =>
              r.pairId === pair.pairId ||
              r.affectedPairIds?.includes(pair.pairId),
          )}
          can={can}
          backLabel={backLabel}
          onBack={backToList}
          onAddNote={() =>
            setNoteTarget({
              participantId: menteeParticipantOf(pair)?.participantId,
              pairId: pair.pairId,
            })
          }
          onRaise={() =>
            setRequestTarget({
              roundId: pair.roundId,
              participantId: menteeParticipantOf(pair)?.participantId,
              pairId: pair.pairId,
              targetLabel: pairLabel(pair),
              actions: ["change_partner"],
            })
          }
        />
      );
    }

    return (
      <ManagementPage
        round={round}
        rounds={rounds}
        query={listQuery}
        onQueryChange={updateListQuery}
        participants={participants}
        nonParticipants={NON_PARTICIPANTS}
        pairs={pairs}
        requests={requests}
        can={can}
        onDecide={decideRequest}
        onOpenParticipant={(participantId) =>
          navigate({ kind: "participant", participantId })
        }
        onOpenPair={(pairId) => navigate({ kind: "pair", pairId })}
        onMarkCell={markCell}
        onCompose={(recipients) => setComposeTarget({ recipients })}
        onBulkMark={bulkMark}
        onConfirmUnmatched={(people) =>
          setRequestTarget({
            roundId: round.id,
            participantIds: people.map((p) => p.participantId),
            targetLabel: `${people.length} ${
              people.length === 1 ? "person" : "people"
            } — ${people.map((p) => p.name).join("; ")}`,
            actions: ["confirm_unmatched"],
          })
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
        onSave={({ tag, body: text }) => {
          const { mark, participantId, pairId } = noteTarget;
          if (mark) applyMark(pairId, mark, true);
          addNote({
            participantId,
            pairId,
            tag,
            body:
              mark === "firstContact"
                ? `First contact confirmed.${text ? ` ${text}` : ""}`
                : text,
          });
          setNoteTarget(null);
        }}
      />
      <RaiseRequestDialog
        target={requestTarget}
        pending={requestTarget ? pendingFor(requestTarget) : []}
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
