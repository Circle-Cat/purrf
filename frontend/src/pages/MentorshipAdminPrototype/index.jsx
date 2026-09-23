import { useCallback, useEffect, useMemo, useState } from "react";
import ManagementPage from "@/pages/MentorshipAdminPrototype/ManagementPage";
import ParticipantDetailPage from "@/pages/MentorshipAdminPrototype/ParticipantDetailPage";
import NoteDialog from "@/pages/MentorshipAdminPrototype/NoteDialog";
import RaiseRequestDialog from "@/pages/MentorshipAdminPrototype/RaiseRequestDialog";
import ComposeDialog from "@/pages/MentorshipAdminPrototype/ComposeDialog";
import RoundModal from "@/pages/MentorshipAdminPrototype/RoundModal";
import MatchingPage from "@/pages/MentorshipAdminPrototype/MatchingPage";
import {
  historyIssuesOf,
  lastRoundOf,
} from "@/pages/MentorshipAdminPrototype/lastRound";
import {
  effectiveRows,
  problemsOf,
  simulateRun,
} from "@/pages/MentorshipAdminPrototype/matching";
import {
  ACTOR_NAMES,
  ADMISSION_NOTIFICATIONS,
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
 * `#mentorship/participants/:id?pair=…` (a person, with one of their pairs
 * open), `#mentorship/pairs/:id` (an older pair link, which opens the
 * mentee's page on that pair),
 * `#mentorship/people/:userId/:roundId` for someone not registered,
 * `#mentorship/matching/:roundId` for a round's matching run, and
 * `#mentorship?tab=…&q=…` for the list. The list's tab, round and filters live
 * in the query so that opening a detail page and coming back lands on the same
 * filtered list — the one cost of making details full pages instead of drawers.
 */
const parseLocation = () => {
  const [path, search = ""] = window.location.hash.replace(/^#/, "").split("?");
  const [root, kind, id, extra] = path.split("/");
  const query = Object.fromEntries(new URLSearchParams(search));
  const timeline = query.timeline ?? null;
  const pair = query.pair ? Number(query.pair) : null;
  if (root === HASH_ROOT && kind === "participants" && id) {
    return {
      view: {
        kind: "participant",
        participantId: decodeURIComponent(id),
        timeline,
        pair,
      },
      query,
    };
  }
  if (root === HASH_ROOT && kind === "people" && id && extra) {
    return {
      view: {
        kind: "person",
        userId: Number(id),
        roundId: Number(extra),
        timeline,
      },
      query,
    };
  }
  if (root === HASH_ROOT && kind === "matching" && id) {
    return { view: { kind: "matching", roundId: Number(id) }, query };
  }
  if (root === HASH_ROOT && kind === "pairs" && id) {
    return { view: { kind: "pair", pairId: Number(id) }, query };
  }
  return { view: { kind: "management" }, query };
};

const toHash = (view, query) => {
  const params = new URLSearchParams(
    Object.fromEntries(
      [
        ["timeline", view.timeline],
        ["pair", view.pair],
      ].filter(([, v]) => v),
    ),
  ).toString();
  const timeline = params ? `?${params}` : "";
  if (view.kind === "participant") {
    return `#${HASH_ROOT}/participants/${encodeURIComponent(view.participantId)}${timeline}`;
  }
  if (view.kind === "person") {
    return `#${HASH_ROOT}/people/${view.userId}/${view.roundId}${timeline}`;
  }
  if (view.kind === "matching") return `#${HASH_ROOT}/matching/${view.roundId}`;
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
  const [matchRuns, setMatchRuns] = useState({});
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
      runId,
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
          runId: runId ?? null,
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
      if (
        NOTE_KIND[n.tag] !== "decided" ||
        n.tag === "matching_exemption" ||
        revokedNoteIds.has(n.noteId)
      ) {
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

  /**
   * Registrations with a standing exemption from the onboarding requirement.
   * Kept apart from the flags: an exemption lets someone in, a flag is a
   * judgement against them. Revoking one takes the person back out.
   */
  const exemptParticipantIds = useMemo(
    () =>
      new Set(
        notes
          .filter(
            (n) =>
              n.tag === "matching_exemption" && !revokedNoteIds.has(n.noteId),
          )
          .map(
            (n) =>
              participants.find(
                (p) => p.userId === n.userId && p.roundId === n.roundId,
              )?.participantId,
          )
          .filter(Boolean),
      ),
    [notes, revokedNoteIds, participants],
  );

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
  const updateRun = (forRound, change) =>
    setMatchRuns((all) => ({ ...all, [forRound]: change(all[forRound]) }));

  /**
   * Publishing writes the pairs, marks both sides matched, and marks everyone
   * else who went into the run unmatched — once. The approval that leads here
   * is where the unmatched list is seen and confirmed.
   */
  const publishRun = (forRound) => {
    const run = matchRuns[forRound];
    const target = rounds.find((r) => r.id === forRound);
    const finalRows = effectiveRows(run, run.draft).filter((r) => r.mentorId);
    const firstPairId = Math.max(...pairs.map((p) => p.pairId)) + 1;
    setPairs((all) => [
      ...all,
      ...finalRows.map((r, i) => ({
        pairId: firstPairId + i,
        roundId: forRound,
        mentorId: r.mentorId,
        menteeId: r.menteeId,
        mentorName: nameOfUser(r.mentorId),
        menteeName: nameOfUser(r.menteeId),
        status: "active",
        firstContactConfirmedAt: null,
        completed: 0,
        required: target.requiredMeetings,
      })),
    ]);
    const matchedIds = new Set(
      finalRows.flatMap((r) => [r.mentorId, r.menteeId]),
    );
    // Everyone who went into the run and came out without a partner.
    const inRun = new Set([
      ...run.mentors.map((m) => m.userId),
      ...run.mentees.map((m) => m.userId),
    ]);
    setParticipants((all) =>
      all.map((p) => {
        if (p.roundId !== forRound || !inRun.has(p.userId)) return p;
        return {
          ...p,
          approvalStatus: matchedIds.has(p.userId) ? "matched" : "un_matched",
        };
      }),
    );
    updateRun(forRound, (r) => ({ ...r, status: "published" }));
  };

  const nameOfUser = (userId) =>
    participants.find((p) => p.userId === userId)?.name ?? `User ${userId}`;

  const decideRequest = (requestId, approved, decisionNote) => {
    {
      const request = requests.find((r) => r.requestId === requestId);
      if (!request || request.raisedBy === viewerId) return;

      const run =
        request.action === "publish_matching"
          ? matchRuns[request.roundId]
          : null;
      const stale =
        approved &&
        ((request.action === "publish_matching" &&
          (!run ||
            run.runId !== request.runId ||
            run.status !== "succeeded" ||
            problemsOf(run, run.draft, nameOfUser).length > 0)) ||
          (request.action === "revoke_flag" &&
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
        exempt_matching: "matching_exemption",
      };
      const body = `${request.reason} — raised by ${
        ACTOR_NAMES[request.raisedBy]
      }, approved by ${viewerName}.${decisionNote ? ` ${decisionNote}` : ""}`;

      if (request.action === "publish_matching") {
        publishRun(request.roundId);
        return;
      }

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
    }
  };

  const menteeParticipantOf = useCallback(
    (pair) =>
      participants.find(
        (p) => p.userId === pair.menteeId && p.roundId === pair.roundId,
      ),
    [participants],
  );

  /**
   * Marking a mentee's first contact with their mentor.
   *
   * Setting it opens the note box first, so a reply summary can go in with
   * it; clearing it is a correction and happens straight away. The pair is
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
      }
    },
    [pairs],
  );

  const markCell = useCallback(
    (pairId, field) => {
      const pair = pairs.find((p) => p.pairId === pairId);
      if (!pair) return;
      const mentee = menteeParticipantOf(pair);
      if (pair.firstContactConfirmedAt) {
        applyMark(pairId, field, false);
        return;
      }
      setNoteTarget({
        participantId: mentee?.participantId,
        pairId,
        mark: field,
        title: `First contact confirmed — ${pair.mentorName} ↔ ${pair.menteeName}`,
        fixedTag: "status_change",
      });
    },
    [pairs, menteeParticipantOf, applyMark],
  );

  /**
   * Marking many people at once, after notifying them some other way. The
   * note is the mark: the Notifications column reads it.
   */
  const bulkMark = useCallback(
    (participantIds, tag) =>
      participantIds.forEach((participantId) =>
        addNote({ participantId, tag, body: "" }),
      ),
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
   * is no separate "an email went out" note to keep in step with it, and
   * every "has this gone out" answer is read from these messages.
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

  /**
   * Starting a run takes the round's lock: while it runs, nothing else can
   * start in that round. A finished, unpublished run can be replaced by a
   * new one; its draft goes with it.
   */
  const startRun = useCallback(
    (people) => {
      if (matchRuns[roundId]?.status === "running") return;
      const mentors = people
        .filter((p) => p.role === "mentor")
        .map(({ userId, freeSlots }) => ({ userId, freeSlots }));
      const mentees = people
        .filter((p) => p.role === "mentee")
        .map(({ userId }) => ({ userId }));
      setMatchRuns((all) => ({
        ...all,
        [roundId]: {
          runId: `r${roundId}-${TODAY.replaceAll("-", "")}-${nextId++}`,
          status: "running",
          startedAt: `${TODAY} 10:02`,
          triggeredBy: viewerId,
          mentors,
          mentees,
          rows: [],
          draft: {},
        },
      }));
    },
    [matchRuns, roundId, viewerId],
  );

  const finishRun = (forRound) =>
    updateRun(forRound, (run) => ({
      ...run,
      status: "succeeded",
      ...simulateRun(run),
    }));

  /** Saving the draft replaces what is stored with what the page holds. */
  const saveDraft = (forRound, draft) =>
    updateRun(forRound, (run) => ({ ...run, draft }));

  /**
   * Publishing is an approval like any other decision with consequences. The
   * request names the run, so approving an older run after a new one has
   * replaced it invalidates rather than publishes.
   */
  const requestPublish = (forRound) => {
    const run = matchRuns[forRound];
    const target = rounds.find((r) => r.id === forRound);
    const matched = effectiveRows(run, run.draft).filter((r) => r.mentorId);
    const paired = new Set(matched.flatMap((r) => [r.mentorId, r.menteeId]));
    const left = [...run.mentors, ...run.mentees]
      .map((x) => x.userId)
      .filter((id) => !paired.has(id));
    setRequestTarget({
      roundId: forRound,
      runId: run.runId,
      targetLabel: `${target?.name} — ${matched.length} pairs from run ${run.runId}; ${
        left.length
      } unmatched${left.length ? `: ${left.map(nameOfUser).join("; ")}` : ""}`,
      actions: ["publish_matching"],
    });
  };

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

  const issuesOf = (person) =>
    historyIssuesOf(person, participants, pairs, rounds, notes, revokedNoteIds);

  const pairLabel = (p) => `${p.mentorName} ↔ ${p.menteeName}`;
  const backLabel = "← Participants";

  const body = () => {
    if (
      view.kind === "participant" ||
      view.kind === "person" ||
      view.kind === "pair"
    ) {
      const linkedPair =
        view.kind === "pair"
          ? pairs.find((p) => p.pairId === view.pairId)
          : null;
      const person =
        view.kind === "participant"
          ? participants.find((p) => p.participantId === view.participantId)
          : view.kind === "pair"
            ? linkedPair && menteeParticipantOf(linkedPair)
            : personInRound(view.userId, view.roundId);
      const openPairId = view.kind === "pair" ? view.pairId : view.pair;
      if (!person) return null;
      const personPairs = pairs.filter(
        (p) =>
          p.roundId === person.roundId &&
          (p.mentorId === person.userId || p.menteeId === person.userId),
      );
      return (
        <ParticipantDetailPage
          key={`${person.participantId ?? person.userId}-${openPairId ?? ""}`}
          openPairId={openPairId}
          pairMeetings={(pairId) =>
            meetings
              .filter((m) => m.pairId === pairId)
              .sort((a, b) => a.startDatetime.localeCompare(b.startDatetime))
          }
          pairRequests={(pairId) =>
            requests.filter(
              (r) => r.pairId === pairId || r.affectedPairIds?.includes(pairId),
            )
          }
          onSaveMeetings={saveMeetings}
          onAddPairNote={(pair) =>
            setNoteTarget({
              participantId: menteeParticipantOf(pair)?.participantId,
              pairId: pair.pairId,
            })
          }
          onRaisePair={(pair) =>
            setRequestTarget({
              roundId: pair.roundId,
              participantId: menteeParticipantOf(pair)?.participantId,
              pairId: pair.pairId,
              targetLabel: pairLabel(pair),
              actions: ["change_partner"],
            })
          }
          onMarkFirstContact={(pairId) => markCell(pairId, "firstContact")}
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
          initialTimeline={view.timeline}
          flags={flagsByParticipant[person.participantId] ?? {}}
          exempt={exemptParticipantIds.has(person.participantId)}
          historyIssues={person.participantId ? issuesOf(person) : []}
          onRequestExemption={() =>
            setRequestTarget({
              roundId: person.roundId,
              participantId: person.participantId,
              targetLabel: person.name,
              actions: ["exempt_matching"],
            })
          }
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
          onOpenPair={(participantId, pairId) =>
            navigate({ kind: "participant", participantId, pair: pairId })
          }
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
              actions: ["withdraw", "mark_no_show", "mark_red_flag"]
                .concat(personPairs.length ? ["change_partner"] : [])
                .concat(issuesOf(person).length ? ["exempt_matching"] : []),
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

    if (view.kind === "matching") {
      const forRound = view.roundId;
      const target = rounds.find((r) => r.id === forRound) ?? round;
      return (
        <MatchingPage
          round={target}
          run={matchRuns[forRound] ?? null}
          nameOf={(userId) =>
            participants.find((p) => p.userId === userId)?.name ??
            `User ${userId}`
          }
          can={can}
          onBack={backToList}
          onFinish={() => finishRun(forRound)}
          onSaveDraft={(draft) => saveDraft(forRound, draft)}
          onRequestPublish={() => requestPublish(forRound)}
          publishRequest={
            requests.find(
              (r) =>
                r.action === "publish_matching" &&
                r.status === "pending" &&
                r.runId === matchRuns[forRound]?.runId,
            ) ?? null
          }
          viewerId={viewerId}
          onCancelRequest={cancelRequest}
        />
      );
    }

    return (
      <ManagementPage
        round={round}
        rounds={rounds}
        query={listQuery}
        onQueryChange={updateListQuery}
        participants={participants.map((p) => ({
          ...p,
          lastRound: lastRoundOf(p, participants, pairs, rounds),
          historyIssues: issuesOf(p),
        }))}
        nonParticipants={unregistered}
        emails={emails}
        notes={notes}
        notifications={ADMISSION_NOTIFICATIONS}
        pairs={pairs}
        requests={requests}
        viewerId={viewerId}
        flagsByParticipant={flagsByParticipant}
        exemptParticipantIds={exemptParticipantIds}
        can={can}
        onDecide={decideRequest}
        onOpenParticipant={(participantId, timeline) =>
          navigate({ kind: "participant", participantId, timeline })
        }
        onMarkCell={markCell}
        onCompose={(recipients, defaultTemplate) =>
          setComposeTarget({ recipients, defaultTemplate })
        }
        onBulkMark={bulkMark}
        onBulkMarkUnregistered={bulkMarkUnregistered}
        onOpenPerson={(userId, timeline) =>
          navigate({ kind: "person", userId, roundId: round.id, timeline })
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
        matchRun={matchRuns[round.id] ?? null}
        matchingOpen={TODAY <= (round.timeline.matchNotificationAt ?? "")}
        onRunMatching={(people) => {
          startRun(people);
          navigate({ kind: "matching", roundId: round.id });
        }}
        onOpenMatching={() => navigate({ kind: "matching", roundId: round.id })}
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
