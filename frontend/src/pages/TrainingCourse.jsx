import { useParams } from "react-router-dom";
import { useAuth } from "@/context/auth";
import useTrainingRuntime from "@/hooks/useTrainingRuntime";

/**
 * The page a learner takes a course on.
 *
 * The course itself runs two frames down, on an origin of its own. This page
 * owns the only two things that origin cannot do: reading progress out of the
 * API, and writing it back -- both handled by useTrainingRuntime.
 */
export default function TrainingCourse() {
  const { trainingId } = useParams();
  // No Provider wraps this page in isolation (e.g. in tests), so guard
  // against the context's null default rather than assume a user is present.
  const { user } = useAuth() ?? {};
  const { session, loadError, saveFailed, sessionStale, frameRef, playerSrc } =
    useTrainingRuntime(trainingId, user);

  if (loadError) {
    return <p className="p-6 text-muted-foreground">{loadError}</p>;
  }
  if (!session) {
    return <p className="p-6 text-muted-foreground">Opening the course...</p>;
  }

  return (
    <div className="flex h-full flex-col">
      {saveFailed && (
        <div className="border-b bg-destructive/10 px-4 py-2 text-sm">
          {sessionStale
            ? "This course was updated while this page was open. Reload the page to continue; this page cannot save any more."
            : "Your progress could not be saved. Keep this tab open; the course saves again automatically."}
        </div>
      )}
      <iframe
        ref={frameRef}
        title="Course"
        src={playerSrc}
        className="flex-1"
      />
    </div>
  );
}
