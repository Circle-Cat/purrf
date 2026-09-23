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
import { stepsFor } from "@/pages/MentorshipAdminPrototype/emailStatus";
import {
  BLOCKER_TEXT,
  POOL_STATUSES,
  activePairsOf,
  freeSlotsOf,
  matchingBlocker,
} from "@/pages/MentorshipAdminPrototype/eligibility";
import {
  ACCOUNT_STATES,
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
// Request ids are numbers of their own, carried on from the mock ones.
let nextRequestId = Math.max(...INITIAL_REQUESTS.map((r) => r.requestId)) + 1;

/**
 * Where the reader is, read from the URL hash.
 *
 * The Pages bundle has no router, so the hash stands in for the real routes:
 * `#mentorship/participants/:userId?round=…&pair=…` for a person in a round —
 * registered or not, the same page — with one of their pairs open;
 * `#mentorship/matching/:roundId` for a round's matching run; and
 * `#mentorship?q=…` for the list. The list's round and filters live in the
 * query so that opening a detail page and coming back lands on the same
 * filtered list — the one cost of making details full pages instead of
 * drawers.
 *
 * Older links still open: `participants/:participantId`, `people/:userId/:roundId`
 * and `pairs/:pairId` (the mentee's page, on that pair).
 */
const parseLocation = () => {
  const [path, search = ""] = window.location.hash.replace(/^#/, "").split("?");
  const [root, kind, id, extra] = path.split("/");
  const query = Object.fromEntries(new URLSearchParams(search));
  const timeline = query.timeline ?? null;
  const pair = query.pair ? Number(query.pair) : null;
  if (root === HASH_ROOT && kind === "participants" && id) {
    if (/^\d+$/.test(id)) {
      return {
        view: {
          kind: "person",
          userId: Number(id),
          roundId: Number(query.round ?? CURRENT_ROUND_ID),
          timeline,
          pair,
        },
        query,
      };
    }
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
        pair,
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
  if (view.kind === "person") {
    const params = new URLSearchParams(
      Object.fromEntries(
        [
          ["round", view.roundId],
          ["pair", view.pair],
          ["timeline", view.timeline],
        ].filter(([, v]) => v),
      ),
    ).toString();
    return `#${HASH_ROOT}/participants/${view.userId}?${params}`;
  }
  if (view.kind === "matching") return `#${HASH_ROOT}/matching/${view.roundId}`;
  const search = new URLSearchParams(query).toString();
  return `#${HASH_ROOT}${search ? `?${search}` : ""}`;
};

/**
 * The list's filters, remembered for this tab so that Back from a detail page
 * opened by a refresh or a shared link still lands on the list it came from.
 */
const LIST_KEY = "mentorship-prototype-list";
const rememberList = (query) => {
  try {
    window.sessionStorage.setItem(LIST_KEY, JSON.stringify(query));
  } catch {
    // Storage can be unavailable; Back then opens the plain list.
  }
};
const rememberedList = () => {
  try {
    return JSON.parse(window.sessionStorage.getItem(LIST_KEY) ?? "{}");
  } catch {
    return {};
  }
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
 *   1. A mentor with two mentees is one row, with one line per pair inside
 *      it, and one page with a section per pair.
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
    location.view.kind === "management" ? location.query : rememberedList(),
  );
  useEffect(() => rememberList(listQuery), [listQuery]);

  const [rounds, setRounds] = useState(INITIAL_ROUNDS);
  const [participants, setParticipants] = useState(INITIAL_PARTICIPANTS);
  const [pairs, setPairs] = useState(INITIAL_PAIRS);
  const [meetings, setMeetings] = useState(INITIAL_MEETINGS);
  const [notes, setNotes] = useState(INITIAL_NOTES);
  const [requests, setRequests] = useState(INITIAL_REQUESTS);
  const [emails, setEmails] = useState(INITIAL_EMAILS);
  const [matchRuns, setMatchRuns] = useState({});
  // Every run that was published, kept after a later run replaces it.
  const [publishedRuns, setPublishedRuns] = useState([]);
  const [mailbox, setMailbox] = useState(MAILBOX_REPLIES);
  const [accountStates, setAccountStates] = useState(ACCOUNT_STATES);
  const accountOf = useCallback(
    (userId) => accountStates[userId] ?? { isActive: true, isBlocked: false },
    [accountStates],
  );

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
      userId,
      pairId,
      noteId,
      runId,
      targetLabel,
      reason,
      reviewerId,
    }) => {
      setRequests((all) => [
        {
          requestId: nextRequestId++,
          action,
          roundId: targetRoundId,
          targetLabel,
          participantId: participantId ?? null,
          participantIds: participantIds ?? null,
          userId: userId ?? null,
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
   * Registrations with a standing exemption from the history check for their
   * round's matching. Kept apart from the flags: an exemption lets someone
   * in, a flag is a judgement against them. Revoking one takes them back out.
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

  const updateRun = (forRound, change) =>
    setMatchRuns((all) => ({ ...all, [forRound]: change(all[forRound]) }));

  const nameOfUser = (userId) =>
    participants.find((p) => p.userId === userId)?.name ??
    ACTOR_NAMES[userId] ??
    `User ${userId}`;

  const issuesOf = (person) =>
    historyIssuesOf(person, participants, pairs, rounds, notes, revokedNoteIds);

  /** The same eligibility rule the list uses, read against the world as it is now. */
  const blockerOf = (person) =>
    matchingBlocker(person, {
      pairs,
      account: accountOf(person.userId),
      exempt: exemptParticipantIds.has(person.participantId),
      historyIssues: issuesOf(person),
    });

  /**
   * Why a run's result cannot be published as it stands today, beyond what the
   * review page already checks. Days can pass between running and publishing:
   * someone given a partner may have withdrawn, been blocked, or filled their
   * slots in the meantime.
   */
  const peopleProblemsOf = (run, draft) => {
    const forRound = run.roundId;
    const rows = effectiveRows(run, draft).filter((r) => r.mentorId);
    const given = {};
    rows.forEach((r) => {
      given[r.mentorId] = (given[r.mentorId] ?? 0) + 1;
      given[r.menteeId] = 1;
    });
    return Object.entries(given).flatMap(([id, count]) => {
      const userId = Number(id);
      const person = participants.find(
        (p) => p.userId === userId && p.roundId === forRound,
      );
      if (!person) return [`${nameOfUser(userId)} is no longer registered.`];
      const blocker = blockerOf(person);
      if (blocker && blocker !== "full") {
        return [`${person.name} ${BLOCKER_TEXT[blocker]}.`];
      }
      const free = freeSlotsOf(person, pairs);
      return free < count
        ? [
            `${person.name} is given ${count} but has ${free} slot${free === 1 ? "" : "s"} left now.`,
          ]
        : [];
    });
  };

  /**
   * Publishing writes the pairs and marks both sides matched. Everyone else
   * who went into the run and still has no active pair is marked unmatched;
   * someone who already had a pair this round keeps their status, and someone
   * who has withdrawn since is left alone.
   *
   * The first publish of a round stamps its matching as completed.
   */
  const publishRun = (forRound) => {
    const run = matchRuns[forRound];
    const target = rounds.find((r) => r.id === forRound);
    const finalRows = effectiveRows(run, run.draft).filter((r) => r.mentorId);
    const firstPairId = Math.max(...pairs.map((p) => p.pairId)) + 1;
    const created = finalRows.map((r, i) => ({
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
    }));
    const pairsAfter = [...pairs, ...created];
    setPairs(pairsAfter);
    const matchedIds = new Set(
      finalRows.flatMap((r) => [r.mentorId, r.menteeId]),
    );
    const inRun = new Set([
      ...run.mentors.map((m) => m.userId),
      ...run.mentees.map((m) => m.userId),
    ]);
    setParticipants((all) =>
      all.map((p) => {
        if (p.roundId !== forRound || !inRun.has(p.userId)) return p;
        if (matchedIds.has(p.userId))
          return { ...p, approvalStatus: "matched" };
        if (
          POOL_STATUSES.includes(p.approvalStatus) &&
          activePairsOf(p, pairsAfter).length === 0
        ) {
          return { ...p, approvalStatus: "un_matched" };
        }
        return p;
      }),
    );
    updateRun(forRound, (r) => ({
      ...r,
      status: "published",
      publishedAt: TODAY,
    }));
    setPublishedRuns((all) => [
      { ...run, status: "published", publishedAt: TODAY },
      ...all,
    ]);
    if (!target.matchingCompletedAt) {
      setRounds((all) =>
        all.map((r) =>
          r.id === forRound ? { ...r, matchingCompletedAt: TODAY } : r,
        ),
      );
    }
  };

  /**
   * Why an approval can no longer be applied, or null when it still can.
   *
   * Every action is re-read against the world as it is now. A request that
   * no longer makes sense is marked invalidated with this reason, which is
   * shown wherever the request is — never dropped in silence.
   */
  const staleReasonOf = (request) => {
    const person = request.participantId
      ? participants.find((p) => p.participantId === request.participantId)
      : null;
    const pair = request.pairId
      ? pairs.find((p) => p.pairId === request.pairId)
      : null;
    switch (request.action) {
      case "publish_matching": {
        const run = matchRuns[request.roundId];
        if (!run || run.runId !== request.runId) {
          return "A newer matching run has replaced this one.";
        }
        if (run.status !== "succeeded") return `The run is ${run.status}.`;
        const problems = [
          ...problemsOf(run, run.draft, nameOfUser),
          ...peopleProblemsOf(run, run.draft),
        ];
        return problems.length ? problems.join(" ") : null;
      }
      case "revoke_flag":
        return revokedNoteIds.has(request.noteId)
          ? "This flag has already been revoked."
          : null;
      case "withdraw":
      case "mark_no_show":
      case "mark_red_flag":
        return person?.approvalStatus === "withdrawn"
          ? `${person.name} has already withdrawn.`
          : null;
      case "change_partner":
        return pair && pair.status !== "active"
          ? "This pair has already ended."
          : null;
      case "exempt_matching": {
        const round = rounds.find((r) => r.id === person?.roundId);
        if (!person) return null;
        if (exemptParticipantIds.has(person.participantId)) {
          return `${person.name} is already exempted for this round.`;
        }
        if (issuesOf(person).length === 0) {
          return `${person.name}'s history no longer needs an exemption.`;
        }
        return TODAY > (round?.timeline.matchNotificationAt ?? "")
          ? "This round's matching has closed."
          : null;
      }
      case "block_account":
        return accountOf(request.userId).isBlocked
          ? `${request.targetLabel} is already blocked.`
          : null;
      default:
        return null;
    }
  };

  /**
   * Deciding is where the approval becomes real: the state change, the note
   * and the decision are one step. Splitting them would leave a window where
   * a request reads "approved" and nothing has happened.
   *
   * Anyone holding the approve permission may decide, whoever the request
   * was sent to — but not the person who raised it. Approving re-checks the
   * world first: a request that no longer makes sense is invalidated, with
   * its reason, not applied.
   */
  const decideRequest = (requestId, approved, decisionNote) => {
    const request = requests.find((r) => r.requestId === requestId);
    if (!request || request.raisedBy === viewerId) return;

    const staleReason = approved ? staleReasonOf(request) : null;
    if (staleReason) {
      setRequests((all) =>
        all.map((r) =>
          r.requestId === requestId
            ? {
                ...r,
                status: "invalidated",
                invalidReason: staleReason,
                decidedBy: viewerId,
                decidedAt: TODAY,
              }
            : r,
        ),
      );
      return;
    }

    // Withdrawing takes the person's pairs with them, whichever pair the
    // request was raised from; a partner change ends the one pair it names.
    const withdrawing =
      approved && request.action === "withdraw"
        ? participants.find((p) => p.participantId === request.participantId)
        : null;
    const affectedPairIds = withdrawing
      ? activePairsOf(withdrawing, pairs).map((p) => p.pairId)
      : approved && request.action === "change_partner"
        ? [request.pairId]
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

    if (request.action === "block_account") {
      blockAccount(request, body);
      return;
    }

    addNote({
      participantId: request.participantId,
      pairId:
        request.pairId ??
        (affectedPairIds.length === 1 ? affectedPairIds[0] : null),
      tag: tagOf[request.action],
      body:
        request.action === "change_partner"
          ? `Pair ended for a partner change. ${body}`
          : body,
    });

    if (withdrawing) {
      setParticipants((all) =>
        all.map((p) =>
          p.participantId === withdrawing.participantId
            ? { ...p, approvalStatus: "withdrawn" }
            : p,
        ),
      );
    }
    if (affectedPairIds.length) {
      setPairs((all) =>
        all.map((p) =>
          affectedPairIds.includes(p.pairId) ? { ...p, status: "inactive" } : p,
        ),
      );
    }
  };

  /**
   * An approved block, as the blacklist linkage (⑩) has it reach mentorship:
   * the account is locked out and every active pair the person is in ends,
   * with a note on each side saying why. Their registrations are left as
   * they are — lifting the block later does not bring any of it back.
   */
  const blockAccount = (request, body) => {
    const userId = request.userId;
    setAccountStates((all) => ({
      ...all,
      [userId]: { ...accountOf(userId), isBlocked: true },
    }));
    const ending = pairs.filter(
      (p) =>
        p.status === "active" &&
        (p.mentorId === userId || p.menteeId === userId),
    );
    setPairs((all) =>
      all.map((p) =>
        ending.some((e) => e.pairId === p.pairId)
          ? { ...p, status: "inactive" }
          : p,
      ),
    );
    setNotes((all) => [
      ...ending.flatMap((p) =>
        [p.mentorId, p.menteeId].map((who) => ({
          noteId: newId("n"),
          userId: who,
          roundId: p.roundId,
          pairId: p.pairId,
          tag: "status_change",
          body: `Pair ended: ${request.targetLabel} was blocked. ${body}`,
          authorId: viewerId,
          createdAt: TODAY,
          revokesNoteId: null,
        })),
      ),
      ...(ending.length
        ? []
        : [
            {
              noteId: newId("n"),
              userId,
              roundId: request.roundId,
              pairId: null,
              tag: "status_change",
              body: `Blocked from Purrf. ${body}`,
              authorId: viewerId,
              createdAt: TODAY,
              revokesNoteId: null,
            },
          ]),
      ...all,
    ]);
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
      if (pair.status !== "active") return;
      const mentee = menteeParticipantOf(pair);
      if (pair.firstContactConfirmedAt) {
        // Taking a mark back is a correction, and it is kept on the record.
        applyMark(pairId, field, false);
        addNote({
          participantId: mentee?.participantId,
          pairId,
          tag: null,
          body: `First contact mark of ${pair.firstContactConfirmedAt} cleared.`,
        });
        return;
      }
      setNoteTarget({
        participantId: mentee?.participantId,
        pairId,
        mark: field,
        title: `First contact confirmed — ${pair.mentorName} ↔ ${pair.menteeName}`,
        fixedTag: "first_contact",
      });
    },
    [pairs, menteeParticipantOf, applyMark, addNote],
  );

  /**
   * Sending writes one message per recipient onto their own timeline — there
   * is no separate "an email went out" note to keep in step with it, and
   * every "has this gone out" answer is read from these messages.
   */
  const sendEmails = useCallback(
    ({ templateKey, messages }) => {
      setEmails((all) => [
        ...messages.map(
          ({ participantId, userId, roundId: onRound, body }) => ({
            messageId: newId("e"),
            threadId: newId("t"),
            userId:
              userId ??
              participants.find((p) => p.participantId === participantId)
                ?.userId,
            roundId:
              onRound ??
              participants.find((p) => p.participantId === participantId)
                ?.roundId ??
              roundId,
            direction: "out",
            templateKey,
            body,
            sentBy: viewerId,
            at: TODAY,
          }),
        ),
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
          roundId,
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
   * A round's first publish is an approval like any other decision with
   * consequences. The request names the run, so approving an older run after
   * a new one has replaced it invalidates rather than publishes. A later,
   * supplemental run publishes straight from its page.
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
              ["pending", "invalidated"].includes(r.status) &&
              ((person.participantId != null &&
                (r.participantId === person.participantId ||
                  r.participantIds?.includes(person.participantId))) ||
                (r.pairId != null &&
                  personPairs.some((p) => p.pairId === r.pairId)) ||
                (r.action === "block_account" && r.userId === person.userId)),
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
          onOpenPair={(participantId, pairId) => {
            const other = participants.find(
              (p) => p.participantId === participantId,
            );
            navigate({
              kind: "person",
              userId: other.userId,
              roundId: other.roundId,
              pair: pairId,
            });
          }}
          onAddNote={() =>
            setNoteTarget(
              person.participantId
                ? { participantId: person.participantId }
                : { userId: person.userId, roundId: person.roundId },
            )
          }
          onMarkNotified={() =>
            setNoteTarget({
              ...(person.participantId
                ? { participantId: person.participantId }
                : { userId: person.userId, roundId: person.roundId }),
              title: `Mark as notified — ${person.name}`,
              notifySteps: stepsFor(person.participantId != null),
            })
          }
          onRaise={() =>
            setRequestTarget({
              roundId: person.roundId,
              participantId: person.participantId,
              targetLabel: person.name,
              // A partner change is about one pair, so it is raised from that
              // pair's section rather than here.
              actions: ["withdraw", "mark_no_show", "mark_red_flag"].concat(
                issuesOf(person).length ? ["exempt_matching"] : [],
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
                  roundId: person.roundId,
                  name: person.name,
                },
              ],
            })
          }
          blocked={accountOf(person.userId).isBlocked}
          onRequestBlock={() =>
            setRequestTarget({
              roundId: person.roundId,
              participantId: person.participantId,
              userId: person.userId,
              targetLabel: person.name,
              actions: ["block_account"],
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
          nameOf={nameOfUser}
          checkPeople={(draft) =>
            matchRuns[forRound]
              ? peopleProblemsOf(matchRuns[forRound], draft)
              : []
          }
          earlierRuns={publishedRuns.filter(
            (r) =>
              r.roundId === forRound && r.runId !== matchRuns[forRound]?.runId,
          )}
          supplemental={publishedRuns.some(
            (r) =>
              r.roundId === forRound && r.runId !== matchRuns[forRound]?.runId,
          )}
          can={can}
          onBack={backToList}
          onFinish={() => finishRun(forRound)}
          onSaveDraft={(draft) => saveDraft(forRound, draft)}
          onRequestPublish={() => requestPublish(forRound)}
          onPublish={() => publishRun(forRound)}
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
        accountOf={accountOf}
        can={can}
        onDecide={decideRequest}
        onOpenParticipant={(participantId, timeline) => {
          const who = participants.find(
            (p) => p.participantId === participantId,
          );
          navigate({
            kind: "person",
            userId: who.userId,
            roundId: who.roundId,
            timeline,
          });
        }}
        onMarkCell={markCell}
        onCompose={(recipients, defaultTemplate) =>
          setComposeTarget({ recipients, defaultTemplate })
        }
        onOpenPerson={(userId, timeline) =>
          navigate({ kind: "person", userId, roundId: round.id, timeline })
        }
        onEditRound={(r) => setRoundModal(r ?? { timeline: {} })}
        matchRun={matchRuns[round.id] ?? null}
        matchingOpen={TODAY <= (round.timeline.matchNotificationAt ?? "")}
        roundRunning={
          (round.timeline.promotionStartAt ?? "") <= TODAY &&
          TODAY <= (round.timeline.feedbackDeadlineAt ?? "")
        }
        onRunMatching={(people) => {
          startRun(people);
          navigate({ kind: "matching", roundId: round.id });
        }}
        onOpenMatching={() => navigate({ kind: "matching", roundId: round.id })}
        feedback={INITIAL_FEEDBACK}
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
        {can("mentorship.admin.read") ||
        can("mentorship.admin.write") ||
        can("mentorship.approve") ? (
          body()
        ) : (
          <p className="rounded-md border border-slate-200 bg-white p-6 text-sm text-slate-600">
            You need the read, write or approve permission to see this page.
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
