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
 * against anyone), and for
 * anyone, a no show recorded in it. A red flag counts from any round. Revoked
 * flags never count. Someone who never took part has nothing to exempt.
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
  const standing = (n) => !revokedNoteIds.has(n.noteId);
  const issues = notes
    .filter(
      (n) => n.userId === person.userId && n.tag === "red_flag" && standing(n),
    )
    .map((n) => `Red flag in ${nameOf(n.roundId)}`);

  const endOf = (roundId) =>
    rounds.find((r) => r.id === roundId)?.timeline
      .meetingsCompletionDeadlineAt ?? "";
  const now = endOf(person.roundId);
  const last = participants
    .filter(
      (p) =>
        p.userId === person.userId &&
        endOf(p.roundId) &&
        endOf(p.roundId) < now,
    )
    .sort((a, b) => endOf(b.roundId).localeCompare(endOf(a.roundId)))[0];
  if (!last) return issues;

  const where = nameOf(last.roundId);
  if (
    notes.some(
      (n) =>
        n.userId === person.userId &&
        n.roundId === last.roundId &&
        n.tag === "no_show" &&
        standing(n),
    )
  ) {
    issues.push(`No show in ${where}`);
  }

  if (person.role === "mentee") {
    const theirs = pairs.filter(
      (p) => p.roundId === last.roundId && p.menteeId === person.userId,
    );
    if (theirs.length === 0 && last.approvalStatus === "withdrawn") {
      issues.push(`Withdrew before matching in ${where}`);
    }
    pairs
      .filter((p) => p.roundId === last.roundId && p.menteeId === person.userId)
      .forEach((p) => {
        if (p.completed == null) return;
        const n = `${p.completed}/${p.required}`;
        if (last.approvalStatus === "withdrawn") {
          issues.push(`Withdrew at ${n} in ${where}`);
        } else if (p.completed < p.required && p.status === "active") {
          issues.push(`Met ${n} in ${where}`);
        }
      });
  }
  return issues;
};
