/**
 * How a person's latest earlier round went, for "Meetings last round".
 *
 * "Earlier" is by the rounds' end dates, not their ids — ids do not run in
 * time order. The answer is one of:
 *
 *   first-time  — no registration in any earlier round
 *   unmatched   — registered, never paired
 *   withdrawn   — with no pairs: they left before being matched
 *   withdrawn   — they left part way; each pair's count where they stopped
 *   played      — each pair's count; a pair that ended early is flagged,
 *                 which is how a partner leaving shows up on this side
 *
 * A mentor who carried two mentees has two counts. They are kept apart:
 * meetings are counted per pair, and adding them would invent a number.
 *
 * @returns {object}
 */
export const lastRoundOf = (person, participants, pairs, rounds) => {
  const endOf = (roundId) =>
    rounds.find((r) => r.id === roundId)?.timeline
      .meetingsCompletionDeadlineAt ?? "";
  const now = endOf(person.roundId);
  const earlier = participants
    .filter(
      (p) =>
        p.userId === person.userId &&
        endOf(p.roundId) &&
        endOf(p.roundId) < now,
    )
    .sort((a, b) => endOf(b.roundId).localeCompare(endOf(a.roundId)));
  const last = earlier[0];
  if (!last) return { kind: "first-time" };

  const roundName = rounds.find((r) => r.id === last.roundId)?.name ?? "";
  const theirs = pairs.filter(
    (p) =>
      p.roundId === last.roundId &&
      (p.mentorId === person.userId || p.menteeId === person.userId),
  );
  if (theirs.length === 0) {
    return last.approvalStatus === "withdrawn"
      ? { kind: "withdrawn", roundName, pairs: [] }
      : { kind: "unmatched", roundName };
  }

  return {
    kind: last.approvalStatus === "withdrawn" ? "withdrawn" : "played",
    roundName,
    pairs: theirs.map((p) => ({
      completed: p.completed,
      required: p.required,
      unknown: p.completed == null,
      ended: p.status === "inactive" && p.completed < p.required,
    })),
  };
};

/** The cell's text for one of the answers above. */
export const describeLastRound = (value) => {
  if (value.kind === "first-time") return "First time";
  if (value.kind === "unmatched") return `${value.roundName} · Not matched`;
  if (value.kind === "withdrawn" && value.pairs.length === 0) {
    return `${value.roundName} · Withdrawn before matching`;
  }
  const counts = value.pairs
    .map((p) => {
      if (p.unknown) return "Unknown";
      const n = `${p.completed}/${p.required}`;
      if (value.kind === "withdrawn") return `Withdrawn at ${n}`;
      return p.ended ? `Pair ended at ${n}` : n;
    })
    .join(" · ");
  return `${value.roundName} · ${counts}`;
};

/**
 * What in someone's past has to be exempted before they can be matched.
 *
 * Their most recent earlier round — not the round just before this one —
 * decides two things: for a mentee, whether they reached the meetings it
 * required (withdrawing counts as not, before being matched too; a pair ended
 * by the partner does not count against them; no meeting data is not held
 * against anyone), and for anyone, a no show recorded in it. Revoked flags
 * never count. Someone who never took part has nothing to exempt.
 *
 * A red flag counts from any round — until an exemption has been proved out:
 * exempted for a round, took part in it, and came through it with none of
 * the problems above. From then on flags from before that round stay on the
 * record but no longer need exempting again. A new problem after it needs a
 * new exemption.
 *
 * @returns {string[]} One reason per problem, empty when there is none.
 */
export const historyIssuesOf = (
  person,
  participants,
  pairs,
  rounds,
  notes,
  revokedNoteIds,
) => {
  const nameOf = (roundId) => rounds.find((r) => r.id === roundId)?.name ?? "";
  const endOf = (roundId) =>
    rounds.find((r) => r.id === roundId)?.timeline
      .meetingsCompletionDeadlineAt ?? "";
  const standing = (n) => !revokedNoteIds.has(n.noteId);
  const hasNote = (roundId, tag) =>
    notes.some(
      (n) =>
        n.userId === person.userId &&
        n.roundId === roundId &&
        n.tag === tag &&
        standing(n),
    );
  const now = endOf(person.roundId);
  const earlier = participants
    .filter(
      (p) =>
        p.userId === person.userId &&
        endOf(p.roundId) &&
        endOf(p.roundId) < now,
    )
    .sort((a, b) => endOf(b.roundId).localeCompare(endOf(a.roundId)));

  /** What went wrong in one earlier round, apart from a red flag. */
  const problemsIn = (row, role) => {
    const where = nameOf(row.roundId);
    const found = [];
    if (hasNote(row.roundId, "no_show")) found.push(`No show in ${where}`);
    if (role !== "mentee") return found;
    const theirs = pairs.filter(
      (p) => p.roundId === row.roundId && p.menteeId === person.userId,
    );
    if (theirs.length === 0 && row.approvalStatus === "withdrawn") {
      found.push(`Withdrew before matching in ${where}`);
    }
    theirs.forEach((p) => {
      if (p.completed == null) return;
      const n = `${p.completed}/${p.required}`;
      if (row.approvalStatus === "withdrawn") {
        found.push(`Withdrew at ${n} in ${where}`);
      } else if (p.completed < p.required && p.status === "active") {
        found.push(`Met ${n} in ${where}`);
      }
    });
    return found;
  };

  // The latest round an exemption was proved out in, if any.
  const provedOut = earlier.find(
    (row) =>
      hasNote(row.roundId, "matching_exemption") &&
      pairs.some(
        (p) =>
          p.roundId === row.roundId &&
          (p.mentorId === person.userId || p.menteeId === person.userId),
      ) &&
      !hasNote(row.roundId, "red_flag") &&
      problemsIn(row, row.role).length === 0,
  );
  const clearedUpTo = provedOut ? endOf(provedOut.roundId) : "";

  const issues = notes
    .filter(
      (n) =>
        n.userId === person.userId &&
        n.tag === "red_flag" &&
        standing(n) &&
        (!clearedUpTo || endOf(n.roundId) > clearedUpTo),
    )
    .map((n) => `Red flag in ${nameOf(n.roundId)}`);

  const last = earlier[0];
  if (!last) return issues;
  return [...issues, ...problemsIn(last, person.role)];
};
