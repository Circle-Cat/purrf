import { useState } from "react";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Textarea } from "@/components/ui/textarea";
import { PROFILES } from "@/pages/MentorshipAdminPrototype/mockData";
import { REASON_LIMIT } from "@/pages/MentorshipAdminPrototype/matching";

const TYPE_LABELS = {
  hungarian: "Scored",
  mutual_yes: "Both asked",
  unmatched: "No match",
};

/**
 * One side of a proposed pair: their résumé and their application answers.
 *
 * @returns {JSX.Element}
 */
const ProfileCard = ({ title, name, userId }) => {
  const profile = PROFILES[userId];
  return (
    <section className="flex-1 rounded-md border border-slate-200 p-3">
      <p className="text-xs uppercase tracking-wide text-slate-400">{title}</p>
      <p className="text-sm font-semibold">{name}</p>
      {profile ? (
        <>
          <p className="text-xs text-slate-500">{profile.headline}</p>
          <p className="mt-3 text-xs font-medium text-slate-600">Experience</p>
          <ul className="text-sm">
            {profile.workHistory.map((w) => (
              <li key={`${w.company}-${w.title}`}>
                {w.title} · {w.company}{" "}
                <span className="text-slate-500">({w.years})</span>
              </li>
            ))}
          </ul>
          <p className="mt-2 text-xs font-medium text-slate-600">Education</p>
          <ul className="text-sm">
            {profile.education.map((e) => (
              <li key={e.school}>
                {e.degree} · {e.school}
              </li>
            ))}
          </ul>
          <p className="mt-2 text-xs font-medium text-slate-600">Application</p>
          <dl className="text-sm">
            {profile.answers.map((a) => (
              <div key={a.q} className="mt-1">
                <dt className="text-slate-500">{a.q}</dt>
                <dd>{a.a}</dd>
              </div>
            ))}
          </dl>
        </>
      ) : (
        <p className="mt-2 text-sm text-slate-500">No profile on file.</p>
      )}
    </section>
  );
};

/** Quotes a CSV cell. */
const cell = (value) => `"${String(value ?? "").replaceAll('"', '""')}"`;

/**
 * MatchingPage
 *
 * `/mentorship-management/matching/:roundId`: the run for a round, and the
 * review of its result.
 *
 * While a run is going nothing else can start in the round — the lock is per
 * round. Once it finishes, every mentee has a row, the unmatched ones too.
 * Opening a row puts both people's résumés and applications side by side
 * with the reason. The admin can rewrite the reason and move the mentee to a
 * different mentor; those edits sit in a draft over the matcher's result
 * until publishing, and the matcher's own reason is kept beside the edit so
 * the difference can be handed back to the algorithm side.
 *
 * Publishing writes the pairs, once. It does not mark anyone unmatched:
 * that list is confirmed through an approval, from here.
 *
 * @returns {JSX.Element}
 */
const MatchingPage = ({
  round,
  run,
  nameOf,
  can,
  onBack,
  onFinish,
  onEditDraft,
  onRevert,
  onPublish,
  onConfirmUnmatched,
}) => {
  // Several rows can be open at once: moving a mentee from one mentor to
  // another usually means looking at both of that mentor's mentees.
  const [open, setOpen] = useState([]);
  const toggle = (id) =>
    setOpen((all) =>
      all.includes(id) ? all.filter((x) => x !== id) : [...all, id],
    );
  const writable = can("mentorship.admin.write");

  if (!run) {
    return (
      <div className="rounded-lg border border-slate-200 bg-white p-5">
        <Button size="sm" variant="ghost" onClick={onBack}>
          ← Participants
        </Button>
        <p className="mt-3 text-sm text-slate-600">
          No matching run for {round.name} yet.
        </p>
      </div>
    );
  }

  const effective = run.rows.map((row) => {
    const edit = run.draft[row.menteeId];
    return edit ? { ...row, ...edit, edited: true } : { ...row, edited: false };
  });
  const slotsOf = Object.fromEntries(
    run.mentors.map((m) => [m.userId, m.freeSlots]),
  );
  const taken = effective.reduce((acc, r) => {
    if (r.mentorId) acc[r.mentorId] = (acc[r.mentorId] ?? 0) + 1;
    return acc;
  }, {});
  const overCap = run.mentors.filter(
    (m) => (taken[m.userId] ?? 0) > m.freeSlots,
  );
  const tooLong = effective.filter((r) => r.reason.length > REASON_LIMIT);
  const noReason = effective.filter((r) => r.mentorId && !r.reason.trim());
  const problems = [
    ...overCap.map(
      (m) =>
        `${nameOf(m.userId)} is given ${taken[m.userId]} mentees but has ${m.freeSlots} slot${m.freeSlots === 1 ? "" : "s"} left.`,
    ),
    ...tooLong.map(
      (r) =>
        `The reason for ${nameOf(r.menteeId)} is over ${REASON_LIMIT} characters.`,
    ),
    ...noReason.map((r) => `${nameOf(r.menteeId)} is matched with no reason.`),
  ];
  const unmatchedMentors = run.mentors
    .map((m) => m.userId)
    .filter((id) => !taken[id]);
  const published = run.status === "published";
  const editable = writable && run.status === "succeeded";

  const csv = [
    [
      "mentee",
      "matcher mentor",
      "matcher reason",
      "final mentor",
      "final reason",
    ]
      .map(cell)
      .join(","),
    ...run.rows.map((row) => {
      const final = effective.find((r) => r.menteeId === row.menteeId);
      return [
        nameOf(row.menteeId),
        row.mentorId ? nameOf(row.mentorId) : "",
        row.reason,
        final.mentorId ? nameOf(final.mentorId) : "",
        final.reason,
      ]
        .map(cell)
        .join(",");
    }),
  ].join("\n");

  return (
    <div className="rounded-lg border border-slate-200 bg-white">
      <header className="flex flex-wrap items-center gap-3 px-5 py-4">
        <Button size="sm" variant="ghost" onClick={onBack}>
          ← Participants
        </Button>
        <div>
          <h2 className="text-base font-semibold">Matching — {round.name}</h2>
          <p className="text-xs text-slate-500">
            Run {run.runId} · started by {nameOf(run.triggeredBy)} at{" "}
            {run.startedAt} · {run.mentors.length} mentors, {run.mentees.length}{" "}
            mentees
          </p>
        </div>
        <Badge variant="secondary" className="ml-auto">
          {run.status}
        </Badge>
      </header>

      {run.status === "running" ? (
        <div className="border-t border-slate-200 px-5 py-4 text-sm">
          <p>
            Running. No other run can start in this round until it finishes; you
            will get an email when it does.
          </p>
          <Button
            size="sm"
            variant="outline"
            className="mt-2"
            onClick={onFinish}
          >
            Simulate the run finishing (prototype only)
          </Button>
        </div>
      ) : (
        <>
          <div className="border-t border-slate-200 px-5 py-3 text-sm">
            {effective.filter((r) => r.mentorId).length} of {effective.length}{" "}
            mentees matched.{" "}
            {unmatchedMentors.length > 0 ? (
              <>
                Mentors without a mentee:{" "}
                {unmatchedMentors.map(nameOf).join(", ")}.{" "}
                {published && writable ? (
                  <Button
                    size="sm"
                    variant="outline"
                    onClick={() => onConfirmUnmatched(unmatchedMentors)}
                  >
                    Confirm as unmatched
                  </Button>
                ) : null}
              </>
            ) : null}
          </div>

          <ul className="divide-y divide-slate-100 border-t border-slate-200">
            {effective.map((r) => (
              <li key={r.menteeId} className="px-5 py-3">
                <button
                  type="button"
                  aria-expanded={open.includes(r.menteeId)}
                  onClick={() => toggle(r.menteeId)}
                  className="flex w-full flex-wrap items-center gap-3 text-left text-sm"
                >
                  <span className="w-40 font-medium">{nameOf(r.menteeId)}</span>
                  <span className="w-40">
                    {r.mentorId ? `→ ${nameOf(r.mentorId)}` : "No mentor"}
                  </span>
                  <Badge variant="outline">
                    {r.edited
                      ? "Edited"
                      : (TYPE_LABELS[r.matchType] ?? r.matchType)}
                  </Badge>
                  <span className="w-10 text-slate-500">
                    {r.edited ? "" : (r.score ?? "—")}
                  </span>
                  <span className="flex-1 truncate text-slate-600">
                    {r.reason}
                  </span>
                </button>

                {open.includes(r.menteeId) ? (
                  <div className="mt-3 space-y-3">
                    <div className="flex flex-col gap-3 md:flex-row">
                      <ProfileCard
                        title="Mentee"
                        name={nameOf(r.menteeId)}
                        userId={r.menteeId}
                      />
                      {r.mentorId ? (
                        <ProfileCard
                          title="Mentor"
                          name={nameOf(r.mentorId)}
                          userId={r.mentorId}
                        />
                      ) : null}
                    </div>

                    <label
                      className="block text-xs text-slate-500"
                      htmlFor={`mentor-${r.menteeId}`}
                    >
                      Mentor
                    </label>
                    <select
                      id={`mentor-${r.menteeId}`}
                      aria-label={`Mentor for ${nameOf(r.menteeId)}`}
                      disabled={!editable}
                      className="w-full rounded-md border border-slate-300 p-2 text-sm"
                      value={r.mentorId ?? ""}
                      onChange={(e) =>
                        onEditDraft(r.menteeId, {
                          mentorId: e.target.value
                            ? Number(e.target.value)
                            : null,
                        })
                      }
                    >
                      <option value="">No mentor this round</option>
                      {run.mentors.map((m) => {
                        const candidate = run.rows
                          .find((x) => x.menteeId === r.menteeId)
                          .candidates.find((c) => c.mentorId === m.userId);
                        const used =
                          (taken[m.userId] ?? 0) -
                          (r.mentorId === m.userId ? 1 : 0);
                        return (
                          <option key={m.userId} value={m.userId}>
                            {nameOf(m.userId)} — {slotsOf[m.userId] - used} of{" "}
                            {slotsOf[m.userId]} slots free
                            {candidate
                              ? ` · candidate, ${candidate.score}`
                              : ""}
                          </option>
                        );
                      })}
                    </select>

                    <label
                      className="block text-xs text-slate-500"
                      htmlFor={`reason-${r.menteeId}`}
                    >
                      Reason shown to the pair
                    </label>
                    <Textarea
                      id={`reason-${r.menteeId}`}
                      aria-label={`Reason for ${nameOf(r.menteeId)}`}
                      disabled={!editable}
                      rows={3}
                      value={r.reason}
                      onChange={(e) =>
                        onEditDraft(r.menteeId, { reason: e.target.value })
                      }
                    />
                    <p
                      className={`text-xs ${
                        r.reason.length > REASON_LIMIT
                          ? "text-red-600"
                          : "text-slate-500"
                      }`}
                    >
                      {r.reason.length}/{REASON_LIMIT}
                    </p>

                    {r.edited ? (
                      <div className="rounded-md bg-slate-50 p-3 text-sm">
                        <p className="text-xs text-slate-500">
                          The matcher proposed
                        </p>
                        <p>
                          {(() => {
                            const original = run.rows.find(
                              (x) => x.menteeId === r.menteeId,
                            );
                            return `${
                              original.mentorId
                                ? nameOf(original.mentorId)
                                : "No mentor"
                            } — ${original.reason || "no reason"}`;
                          })()}
                        </p>
                        {editable ? (
                          <Button
                            size="sm"
                            variant="ghost"
                            className="mt-1"
                            onClick={() => onRevert(r.menteeId)}
                          >
                            Revert to the matcher&apos;s result
                          </Button>
                        ) : null}
                      </div>
                    ) : null}
                  </div>
                ) : null}
              </li>
            ))}
          </ul>

          <footer className="space-y-2 border-t border-slate-200 px-5 py-4">
            {problems.length > 0 ? (
              <ul className="text-sm text-red-700">
                {problems.map((p) => (
                  <li key={p}>{p}</li>
                ))}
              </ul>
            ) : null}
            <div className="flex flex-wrap items-center gap-2">
              {published ? (
                <p className="text-sm text-slate-600">
                  Published. The pairs are live; this result can no longer be
                  changed.
                </p>
              ) : (
                <Button
                  size="sm"
                  disabled={!editable || problems.length > 0}
                  onClick={onPublish}
                >
                  Publish results
                </Button>
              )}
              <a
                className="text-sm text-slate-700 underline underline-offset-2"
                download={`${run.runId}-reasons.csv`}
                href={`data:text/csv;charset=utf-8,${encodeURIComponent(csv)}`}
              >
                Download matcher vs final reasons
              </a>
            </div>
          </footer>
        </>
      )}
    </div>
  );
};

export default MatchingPage;
