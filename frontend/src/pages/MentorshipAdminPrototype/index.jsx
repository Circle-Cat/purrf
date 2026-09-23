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
  APPROVE_HOLDERS,
  CURRENT_USER,
  DEFAULT_PERMISSIONS,
  INITIAL_EMAILS,
  INITIAL_FEEDBACK,
  INITIAL_MEETINGS,
  INITIAL_NOTES,
  INITIAL_PAIRS,
  INITIAL_PARTICIPANTS,
  INITIAL_REQUESTS,
  INITIAL_ROUNDS,
  MAILBOX_REPLIES,
  HIRED_APPLICATIONS,
  NEVER_REGISTERED,
  ONBOARDING_TRAININGS,
  NOTE_KIND,
  NOTE_LABELS,
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
 * `#mentorship/participants/:id`, `#mentorship/pairs/:id`,
 * `#mentorship/people/:userId/:roundId` for someone not registered, and
 * `#mentorship?tab=…&q=…` for the list. The list's tab, round and filters live
 * in the query so that opening a detail page and coming back lands on the same
 * filtered list — the one cost of making details full pages instead of drawers.
 */
const parseLocation = () => {
  const [path, search = ""] = window.location.hash.replace(/^#/, "").split("?");
  const [root, kind, id, extra] = path.split("/");
  const query = Object.fromEntries(new URLSearchParams(search));
  if (root === HASH_ROOT && kind === "participants" && id) {
    return {
      view: { kind: "participant", participantId: decodeURIComponent(id) },
      query,
    };
  }
  if (root === HASH_ROOT && kind === "people" && id && extra) {
    return {
      view: { kind: "person", userId: Number(id), roundId: Number(extra) },
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
  if (view.kind === "person") {
    return `#${HASH_ROOT}/people/${view.userId}/${view.roundId}`;
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
  const [viewerId, setViewerId] = useState(CURRENT_USER.userId);
  const viewerName = ACTOR_NAMES[viewerId];
  const [location, setLocation] = useState(parseLocation);
  const [listQuery, setListQuery] = useState(() =>
    location.view.kind === "management" ? location.query : {},
  );

  const [rounds, setRounds] = useState(INITIAL_ROUNDS);
  const [participants, setParticipants] = useState(INITIAL_PARTICIPANTS);
  const [pairs, setPairs] = useState(INITIAL_PAIRS);
  const [meetings, setMeetings] = useState(INITIAL_MEETINGS);
  const [notes, setNotes] = useState(INITIAL_NOTES);
  const [requests, setRequests] = useState(INITIAL_REQUESTS);
  const [emails, setEmails] = useState(INITIAL_EMAILS);
  const [mailbox, setMailbox] = useState(MAILBOX_REPLIES);

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

  /**
   * A note is written against a person and a round. Callers holding a
   * registration pass its participant id and it is resolved here; callers
   * holding someone who has not registered pass the user and round directly.
   */
  const addNote = useCallback(
    ({ participantId, userId, roundId, pairId, tag, body, revokesNoteId }) => {
      const registration = participantId
        ? participants.find((p) => p.participantId === participantId)
        : null;
      setNotes((all) => [
        {
          noteId: newId("n"),
          userId: registration?.userId ?? userId,
          roundId: registration?.roundId ?? roundId,
          pairId: pairId ?? null,
          tag: tag || null,
          body,
          authorId: viewerId,
          createdAt: TODAY,
          revokesNoteId: revokesNoteId ?? null,
        },
        ...all,
      ]);
    },
    [viewerId, participants],
  );

  /**
   * A flag stays on record when revoked; the revocation is a second note
   * pointing at it. Whether a flag still counts is read from that, not stored
   * on the flag.
   */
  const revokedNoteIds = useMemo(
    () => new Set(notes.map((n) => n.revokesNoteId).filter(Boolean)),
    [notes],
  );

  const raiseRequest = useCallback(
    ({
      action,
      roundId: targetRoundId,
      participantId,
      participantIds,
      pairId,
      noteId,
      targetLabel,
      reason,
      reviewerId,
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
          noteId: noteId ?? null,
          reason,
          raisedBy: viewerId,
          reviewerId,
          createdAt: TODAY,
          status: "pending",
        },
        ...all,
      ]);
    },
    [viewerId],
  );

  /**
   * The judgement flags on each person that still stand, as `{tag: count}`.
   * Shown next to their status because a flag coexists with it: someone can
   * be matched and have a no show on record.
   */
  const flagsByParticipant = useMemo(() => {
    const out = {};
    notes.forEach((n) => {
      if (NOTE_KIND[n.tag] !== "decided" || revokedNoteIds.has(n.noteId)) {
        return;
      }
      const registration = participants.find(
        (p) => p.userId === n.userId && p.roundId === n.roundId,
      );
      if (!registration) return;
      const key = registration.participantId;
      out[key] = out[key] ?? {};
      out[key][n.tag] = (out[key][n.tag] ?? 0) + 1;
    });
    return out;
  }, [notes, revokedNoteIds, participants]);

  /** Only the person who raised a request can withdraw it, and only while it waits. */
  const cancelRequest = useCallback(
    (requestId) =>
      setRequests((all) =>
        all.map((r) =>
          r.requestId === requestId &&
          r.status === "pending" &&
          r.raisedBy === viewerId
            ? { ...r, status: "cancelled", decidedAt: TODAY }
            : r,
        ),
      ),
    [viewerId],
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
   *
   * Anyone holding the approve permission may decide, whoever the request
   * was sent to — but not the person who raised it. Approving re-checks the
   * world first: a request that no longer makes sense is invalidated, not
   * applied.
   */
  const decideRequest = useCallback(
    (requestId, approved, decisionNote) => {
      const request = requests.find((r) => r.requestId === requestId);
      if (!request || request.raisedBy === viewerId) return;

      const stale =
        approved &&
        ((request.action === "revoke_flag" &&
          revokedNoteIds.has(request.noteId)) ||
          (request.action === "withdraw" &&
            participants.find((p) => p.participantId === request.participantId)
              ?.approvalStatus === "withdrawn"));
      if (stale) {
        setRequests((all) =>
          all.map((r) =>
            r.requestId === requestId
              ? {
                  ...r,
                  status: "invalidated",
                  decidedBy: viewerId,
                  decidedAt: TODAY,
                }
              : r,
          ),
        );
        return;
      }

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
                decidedBy: viewerId,
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
      }, approved by ${viewerName}.${decisionNote ? ` ${decisionNote}` : ""}`;

      if (request.action === "revoke_flag") {
        const flag = notes.find((n) => n.noteId === request.noteId);
        addNote({
          participantId: request.participantId,
          pairId: flag?.pairId,
          tag: "status_change",
          body: `Revoked the ${NOTE_LABELS[flag?.tag] ?? "flag"} of ${
            flag?.createdAt
          }. ${body}`,
          revokesNoteId: request.noteId,
        });
        return;
      }

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
    [
      addNote,
      requests,
      participants,
      pairs,
      notes,
      revokedNoteIds,
      viewerId,
      viewerName,
    ],
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

  /** The same, for people not registered for the round: notes still land. */
  const bulkMarkUnregistered = useCallback(
    (userIds, tag) =>
      userIds.forEach((userId) => addNote({ userId, roundId, tag, body: "" })),
    [addNote, roundId],
  );

  /**
   * Sending writes one message per recipient onto their own timeline — there
   * is no separate "an email went out" note to keep in step with it.
   *
   * A mid-term reminder sent from here stamps the mentee's cell by itself;
   * the manual mark stays for the Teams half and for anything sent elsewhere.
   */
  const sendEmails = useCallback(
    ({ templateKey, messages }) => {
      setEmails((all) => [
        ...messages.map(({ participantId, userId, body }) => ({
          messageId: newId("e"),
          threadId: newId("t"),
          userId:
            userId ??
            participants.find((p) => p.participantId === participantId)?.userId,
          roundId:
            participants.find((p) => p.participantId === participantId)
              ?.roundId ?? roundId,
          direction: "out",
          templateKey,
          body,
          sentBy: viewerId,
          at: TODAY,
        })),
        ...all,
      ]);
      if (templateKey !== "mentorship_midterm_reminder") return;
      const ids = messages.map((m) => m.participantId);
      setParticipants((all) =>
        all.map((p) =>
          ids.includes(p.participantId) && p.role === "mentee"
            ? { ...p, midtermReminderAt: TODAY }
            : p,
        ),
      );
    },
    [viewerId, roundId, participants],
  );

  /** Pulls this person's waiting replies in; returns how many arrived. */
  const refreshEmails = useCallback(
    (userId, forRound) => {
      const mine = (m) => m.userId === userId && m.roundId === forRound;
      const arrived = mailbox.filter(mine);
      setMailbox((all) => all.filter((m) => !mine(m)));
      setEmails((all) => [...arrived, ...all]);
      return arrived.length;
    },
    [mailbox],
  );

  /**
   * The meeting log's batch save. The pair's completed count moves with it,
   * as the backend recomputes it from the same rows.
   */
  const saveMeetings = useCallback(
    async (pairId, { updates, deletes }) => {
      const before = meetings.filter((m) => m.pairId === pairId);
      const after = before
        .filter((m) => !deletes.includes(m.meetingId))
        .map((m) => {
          const patch = updates.find((u) => u.meetingId === m.meetingId);
          return patch ? { ...m, ...patch, meetingId: m.meetingId } : m;
        });
      const delta =
        after.filter((m) => m.isCompleted).length -
        before.filter((m) => m.isCompleted).length;
      setMeetings((all) => [
        ...all.filter((m) => m.pairId !== pairId),
        ...after,
      ]);
      if (delta !== 0) {
        setPairs((all) =>
          all.map((p) =>
            p.pairId === pairId ? { ...p, completed: p.completed + delta } : p,
          ),
        );
      }
    },
    [meetings],
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

  /**
   * Everyone in the programme with no registration for the selected round.
   *
   * "In the programme" is having been admitted to a mentor or mentee posting,
   * or having registered for any round (which is how the historical backfill
   * arrived). An onboarding course on its own does not count — courses can be
   * handed out separately — but the course rows say how far onboarding has
   * got, which is what a reminder chases. "Not registered" is the programme
   * minus the selected round's participants: pick last year's round and it
   * answers for last year.
   */
  const unregistered = useMemo(() => {
    const endOf = (id) =>
      rounds.find((r) => r.id === id)?.timeline.meetingsCompletionDeadlineAt ??
      "";
    const registered = new Set(
      participants.filter((p) => p.roundId === round.id).map((p) => p.userId),
    );
    const courseOf = (userId, role) =>
      ONBOARDING_TRAININGS.find((t) => t.userId === userId && t.role === role)
        ?.status ?? null;
    const lastRowOf = (userId) =>
      participants
        .filter((p) => p.userId === userId)
        .sort((a, b) => endOf(b.roundId).localeCompare(endOf(a.roundId)))[0];
    const inProgramme = [
      ...new Set([
        ...HIRED_APPLICATIONS.map((a) => a.userId),
        ...participants.map((p) => p.userId),
      ]),
    ];
    return inProgramme
      .filter((userId) => !registered.has(userId))
      .map((userId) => {
        const last = lastRowOf(userId);
        const who = last ?? NEVER_REGISTERED.find((p) => p.userId === userId);
        return {
          userId,
          name: who?.name,
          email: who?.email,
          identity: who?.identity,
          mentorOnboarding: courseOf(userId, "mentor"),
          menteeOnboarding: courseOf(userId, "mentee"),
          lastTookPart: last
            ? (rounds.find((r) => r.id === last.roundId)?.name ?? null)
            : null,
        };
      })
      .filter((p) => p.name);
  }, [participants, rounds, round]);

  /**
   * A person as seen from one round. Registered, it is their participant row;
   * not registered, it is who they are with no status — the same page, so a
   * note written before they sign up is where they will find it after.
   */
  const personInRound = (userId, forRound) => {
    const registration = participants.find(
      (p) => p.userId === userId && p.roundId === forRound,
    );
    if (registration) return registration;
    const known =
      participants.find((p) => p.userId === userId) ??
      NEVER_REGISTERED.find((p) => p.userId === userId);
    if (!known) return null;
    return {
      participantId: null,
      userId,
      roundId: forRound,
      name: known.name,
      email: known.email,
      identity: known.identity,
      role: null,
      approvalStatus: null,
      onboardingDone: false,
    };
  };

  const pairLabel = (p) => `${p.mentorName} ↔ ${p.menteeName}`;
  const backLabel = listQuery.tab === "pairs" ? "← Pairs" : "← Participants";

  const body = () => {
    if (view.kind === "participant" || view.kind === "person") {
      const person =
        view.kind === "participant"
          ? participants.find((p) => p.participantId === view.participantId)
          : personInRound(view.userId, view.roundId);
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
          emails={emails.filter(
            (e) => e.userId === person.userId && e.roundId === person.roundId,
          )}
          onRefreshEmails={() => refreshEmails(person.userId, person.roundId)}
          feedback={INITIAL_FEEDBACK}
          flags={flagsByParticipant[person.participantId] ?? {}}
          revokedNoteIds={revokedNoteIds}
          requests={requests.filter(
            (r) =>
              r.status === "pending" &&
              (r.participantId === person.participantId ||
                r.participantIds?.includes(person.participantId)),
          )}
          viewerId={viewerId}
          onCancelRequest={cancelRequest}
          onRevoke={(note) =>
            setRequestTarget({
              roundId: person.roundId,
              participantId: person.participantId,
              pairId: note.pairId,
              noteId: note.noteId,
              targetLabel: `${person.name} — ${NOTE_LABELS[note.tag]} of ${
                note.createdAt
              }`,
              actions: ["revoke_flag"],
            })
          }
          can={can}
          backLabel={backLabel}
          onBack={backToList}
          onOpenPair={(pairId) => navigate({ kind: "pair", pairId })}
          onAddNote={() =>
            setNoteTarget(
              person.participantId
                ? { participantId: person.participantId }
                : { userId: person.userId, roundId: person.roundId },
            )
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
          onCompose={() =>
            setComposeTarget({
              recipients: [
                {
                  participantId: person.participantId,
                  userId: person.userId,
                  name: person.name,
                },
              ],
            })
          }
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
          meetings={meetings
            .filter((m) => m.pairId === pair.pairId)
            .sort((a, b) => a.startDatetime.localeCompare(b.startDatetime))}
          onSaveMeetings={(batch) => saveMeetings(pair.pairId, batch)}
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
        nonParticipants={unregistered}
        emails={emails}
        pairs={pairs}
        requests={requests}
        viewerId={viewerId}
        flagsByParticipant={flagsByParticipant}
        can={can}
        onDecide={decideRequest}
        onOpenParticipant={(participantId) =>
          navigate({ kind: "participant", participantId })
        }
        onOpenPair={(pairId) => navigate({ kind: "pair", pairId })}
        onMarkCell={markCell}
        onCompose={(recipients, defaultTemplate) =>
          setComposeTarget({ recipients, defaultTemplate })
        }
        onBulkMark={bulkMark}
        onBulkMarkUnregistered={bulkMarkUnregistered}
        onOpenPerson={(userId) =>
          navigate({ kind: "person", userId, roundId: round.id })
        }
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
          <label className="flex items-center gap-1 text-xs text-slate-500">
            signed in as
            <select
              aria-label="Signed in as"
              className="rounded border border-slate-300 px-1 py-0.5 text-xs text-slate-700"
              value={viewerId}
              onChange={(e) => setViewerId(Number(e.target.value))}
            >
              {APPROVE_HOLDERS.map((h) => (
                <option key={h.userId} value={h.userId}>
                  {h.name}
                </option>
              ))}
            </select>
          </label>
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
          const {
            mark,
            participantId,
            userId,
            roundId: forRound,
            pairId,
          } = noteTarget;
          if (mark) applyMark(pairId, mark, true);
          addNote({
            participantId,
            userId,
            roundId: forRound,
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
        viewerId={viewerId}
        onClose={() => setRequestTarget(null)}
        onSave={(payload) => {
          raiseRequest({ ...requestTarget, ...payload });
          setRequestTarget(null);
        }}
      />
      {composeTarget ? (
        <ComposeDialog
          target={composeTarget}
          onClose={() => setComposeTarget(null)}
          onSend={(payload) => {
            sendEmails(payload);
            setComposeTarget(null);
          }}
        />
      ) : null}
      <RoundModal
        round={roundModal}
        onClose={() => setRoundModal(null)}
        onSave={saveRound}
      />
    </div>
  );
};

export default MentorshipAdminPrototype;
