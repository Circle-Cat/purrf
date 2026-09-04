import { useEffect, useMemo, useState } from "react";
import { useParams } from "react-router-dom";
import { useAuth } from "@/context/auth";
import { readCompletionConfig, startTrial } from "@/api/trainingApi";
import useTrainingRuntime from "@/hooks/useTrainingRuntime";
import { Card } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { formatInTz, resolveViewerTimezone } from "@/utils/dateTime";
import PackageHealthBox from "@/pages/AdminTraining/components/PackageHealthBox";

const timeOf = (ms, tz) =>
  formatInTz(new Date(ms).toISOString(), tz, "HH:mm:ss");

// suspend_data has no cap on this column, so its row and its writes-log entry
// show a size only -- never a "used / limit" pair implying a ceiling we do
// not impose.
const formatCmiValue = (field, value) =>
  field === "cmi.suspend_data"
    ? `${(value ?? "").length} chars`
    : String(value);

const formatDuration = (ms) => {
  const totalSeconds = Math.max(0, Math.round(ms / 1000));
  const minutes = Math.floor(totalSeconds / 60);
  const seconds = totalSeconds % 60;
  return minutes > 0 ? `${minutes}m ${seconds}s` : `${seconds}s`;
};

/**
 * The page an administrator uses to prove a course package can be finished.
 *
 * It opens a trial assignment on the course under the admin's own identity,
 * then runs the ordinary learner flow against it via useTrainingRuntime --
 * the same iframe, the same message bridge, the same origin check. The
 * diagnostics below it are a second consumer of that same traffic, not
 * a second listener: it reads whatever the hook already received.
 *
 * Reaching a finishing lesson_status stamps the course server-side on the
 * commit that carries it, so this page does not call anything extra to
 * unlock the course -- it only reflects what it observed.
 *
 * @component
 */
export default function TrainingTrial() {
  const { courseId } = useParams();
  const { user } = useAuth() ?? {};
  const [trainingId, setTrainingId] = useState(null);
  const [trialError, setTrialError] = useState(null);
  // The same `TrainingCompletionConfigDto` shape `PackageHealthBox` renders
  // from the upload dialog -- one component, one set of copy, so this page
  // and that dialog never say two different things about the same package.
  const [completionConfig, setCompletionConfig] = useState(null);
  // Whether the course carries its stamp. The only answer to "can this be
  // assigned yet" -- the assignment's own status cannot stand in for it,
  // because a verifier re-running a replaced package is already DONE.
  const [verified, setVerified] = useState(false);

  // Router keeps this page mounted when only the param changes, so every
  // answer about the previous course has to go before the new one arrives.
  useEffect(() => {
    let cancelled = false;
    setTrialError(null);
    setTrainingId(null);
    startTrial(courseId)
      .then((response) => {
        if (!cancelled) setTrainingId(response.data.trainingId);
      })
      .catch(() => {
        if (!cancelled) {
          setTrialError("Could not start a trial run of this course.");
        }
      });
    return () => {
      cancelled = true;
    };
  }, [courseId]);

  // Read before the run, not after: whoever is about to click through a
  // course needs to know it can only be finished from inside a Storyline
  // block, or that we cannot tell. A failure to fetch is left silent -- it
  // says nothing about the package, and the run itself is the real answer.
  // What the fetch resolves with is never silent, even when it's the
  // ordinary, nothing-wrong case -- that silence is what let the 08-29
  // failure go undetected.
  useEffect(() => {
    let cancelled = false;
    setCompletionConfig(null);
    setVerified(false);
    readCompletionConfig(courseId)
      .then(({ data }) => {
        if (cancelled) return;
        setVerified(Boolean(data.verified));
        setCompletionConfig(data);
      })
      .catch(() => {});
    return () => {
      cancelled = true;
    };
  }, [courseId]);

  const {
    session,
    loadError,
    saveFailed,
    frameRef,
    playerSrc,
    writes,
    courseVerified,
  } = useTrainingRuntime(trainingId, user);

  const tz = resolveViewerTimezone();

  // The current value of every field is the last write that carried it --
  // each commit may report the whole model or only what changed.
  const latestCmi = useMemo(
    () => writes.reduce((acc, write) => ({ ...acc, ...write.cmi }), {}),
    [writes],
  );
  const lessonStatus = latestCmi["cmi.core.lesson_status"];
  // The stamp lands on the commit that reported completion, and that save's
  // own response says so. The assignment's status cannot stand in for it: a
  // verifier re-running a replaced package is already DONE, so their first
  // commit of the new run reads done and every one after it does too.
  const isComplete = verified || courseVerified;
  const hasSuspendData = "cmi.suspend_data" in latestCmi;

  const firstWrite = writes[0];
  // The write we were on when the server first said done. Held rather than
  // recomputed: the course keeps committing afterwards, and the moment it
  // finished must not drift with them.
  const [finishingWrite, setFinishingWrite] = useState(null);
  useEffect(() => {
    if (!isComplete) return;
    setFinishingWrite((held) => held ?? writes[writes.length - 1] ?? null);
  }, [isComplete, writes]);
  const lastFinishCall = [...writes].reverse().find((w) => w.type === "finish");
  const commitWrites = writes.filter((w) => w.type === "commit");
  const lastCommit = commitWrites[commitWrites.length - 1];

  if (trialError) {
    return <p className="p-6 text-muted-foreground">{trialError}</p>;
  }

  return (
    <div className="space-y-5 p-6">
      <div>
        <h1 className="text-xl font-semibold">Trial run</h1>
        <p className="mt-0.5 font-mono text-sm text-muted-foreground">
          Course #{courseId}
        </p>
      </div>

      {completionConfig && (
        <div data-testid="trial-package-notes">
          <PackageHealthBox config={completionConfig} />
        </div>
      )}

      <Card className="overflow-hidden py-0">
        {loadError ? (
          <p className="p-6 text-muted-foreground">{loadError}</p>
        ) : !session ? (
          <p className="p-6 text-muted-foreground">Opening the course...</p>
        ) : (
          <div className="flex aspect-video flex-col">
            {saveFailed && (
              <div className="border-b bg-destructive/10 px-4 py-2 text-sm">
                Your progress could not be saved. Keep this tab open; the course
                saves again automatically.
              </div>
            )}
            <iframe
              ref={frameRef}
              title="Course"
              src={playerSrc}
              className="flex-1"
            />
          </div>
        )}
      </Card>

      <div
        data-testid="trial-verdict"
        className={
          isComplete
            ? "rounded-xl border border-emerald-600/30 bg-emerald-600/10 p-4 text-sm"
            : "rounded-xl border bg-card p-4 text-sm"
        }
      >
        {isComplete ? (
          <>
            <p className="font-semibold text-emerald-700 dark:text-emerald-400">
              ✓ Completed — this course can now be assigned
            </p>
            <p className="mt-1 text-muted-foreground">
              This course is now verified and unlocked for assignment.
              {finishingWrite &&
                ` Verified by ${user?.email ?? "you"} on ${timeOf(
                  finishingWrite.receivedAt,
                  tz,
                )}.`}{" "}
              Reached <code>{lessonStatus}</code>
              {firstWrite &&
                finishingWrite &&
                ` after ${formatDuration(
                  finishingWrite.receivedAt - firstWrite.receivedAt,
                )}`}
              .
            </p>
          </>
        ) : (
          <>
            <p className="font-semibold">○ Not complete yet</p>
            <p className="mt-1 text-muted-foreground">
              This course unlocks for assignment the moment it reports{" "}
              <code>completed</code> or <code>passed</code>.
            </p>
          </>
        )}
      </div>

      <div className="grid grid-cols-1 items-start gap-5 lg:grid-cols-2">
        <Card className="p-5">
          <h4 className="mb-3 text-xs font-semibold uppercase tracking-wide text-muted-foreground">
            Runtime
          </h4>
          <dl className="grid grid-cols-[max-content_1fr] gap-x-4 gap-y-1.5 font-mono text-sm">
            <dt className="text-muted-foreground">lesson_status</dt>
            <dd>{lessonStatus ?? "—"}</dd>
            <dt className="text-muted-foreground">suspend_data</dt>
            <dd>
              {hasSuspendData
                ? formatCmiValue(
                    "cmi.suspend_data",
                    latestCmi["cmi.suspend_data"],
                  )
                : "—"}
            </dd>
            <dt className="text-muted-foreground">LMSFinish</dt>
            <dd>
              {lastFinishCall
                ? `✓ ${timeOf(lastFinishCall.receivedAt, tz)}`
                : "not called yet"}
            </dd>
            <dt className="text-muted-foreground">Commits</dt>
            <dd>
              {commitWrites.length}
              {lastCommit && ` · last ${timeOf(lastCommit.receivedAt, tz)}`}
            </dd>
          </dl>
        </Card>

        <Card className="p-5">
          <div className="mb-3 flex items-center gap-2">
            <h4 className="text-xs font-semibold uppercase tracking-wide text-muted-foreground">
              CMI writes
            </h4>
            <Badge variant="secondary">{writes.length}</Badge>
          </div>
          <div
            data-testid="trial-writes"
            className="max-h-56 space-y-1 overflow-y-auto rounded-md border bg-background p-2 font-mono text-xs text-muted-foreground"
          >
            {writes.length === 0 ? (
              <p>No CMI traffic received.</p>
            ) : (
              [...writes].reverse().flatMap((write, writeIdx) =>
                Object.entries(write.cmi).map(([field, value]) => (
                  <p key={`${writeIdx}-${field}`}>
                    <span>{timeOf(write.receivedAt, tz)}</span>{" "}
                    <span className="font-medium text-foreground">{field}</span>{" "}
                    <span>{formatCmiValue(field, value)}</span>
                  </p>
                )),
              )
            )}
          </div>
        </Card>
      </div>
    </div>
  );
}
