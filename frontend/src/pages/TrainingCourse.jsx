import { useCallback, useEffect, useRef, useState } from "react";
import { useParams } from "react-router-dom";
import { openSession, saveProgress } from "@/api/trainingApi";
import { useAuth } from "@/context/auth";
import { MESSAGE_TYPES, isTrustedMessage } from "@/training/scormBridge";

/**
 * The page a learner takes a course on.
 *
 * The course itself runs two frames down, on an origin of its own. This page
 * owns the only two things that origin cannot do: reading progress out of the
 * API, and writing it back.
 */
export default function TrainingCourse() {
  const { trainingId } = useParams();
  // No Provider wraps this page in isolation (e.g. in tests), so guard
  // against the context's null default rather than assume a user is present.
  const { user } = useAuth() ?? {};
  const [session, setSession] = useState(null);
  const [loadError, setLoadError] = useState(null);
  const [saveFailed, setSaveFailed] = useState(false);
  const frameRef = useRef(null);

  useEffect(() => {
    let cancelled = false;
    openSession(trainingId)
      .then((response) => {
        if (!cancelled) setSession(response.data);
      })
      .catch(() => {
        if (!cancelled) setLoadError("This course is not available.");
      });
    return () => {
      cancelled = true;
    };
  }, [trainingId]);

  const post = useCallback(
    (message, origin) =>
      frameRef.current?.contentWindow?.postMessage(message, origin),
    [],
  );

  useEffect(() => {
    if (!session) return undefined;
    const contentOrigin = new URL(session.contentBaseUrl).origin;

    const onMessage = async (event) => {
      // The whole security of the bridge. Without it any page could post a
      // finished course through.
      if (!isTrustedMessage(event, contentOrigin)) return;

      if (event.data.type === MESSAGE_TYPES.READY) {
        post(
          {
            type: MESSAGE_TYPES.INIT,
            progress: session.progress || {},
            learner: {
              userId: user?.userId,
              displayName: user?.email ?? "",
            },
            entryPath: session.entryPath,
          },
          contentOrigin,
        );
        return;
      }

      if (
        event.data.type === MESSAGE_TYPES.COMMIT ||
        event.data.type === MESSAGE_TYPES.FINISH
      ) {
        try {
          await saveProgress(trainingId, { cmi: event.data.cmi });
          setSaveFailed(false);
          post({ type: MESSAGE_TYPES.SAVED, ok: true }, contentOrigin);
        } catch {
          // LMSCommit already answered "true" to the course the moment it
          // posted; only this page can tell the learner the save did not land.
          setSaveFailed(true);
          post({ type: MESSAGE_TYPES.SAVED, ok: false }, contentOrigin);
        }
      }
    };

    window.addEventListener("message", onMessage);
    return () => window.removeEventListener("message", onMessage);
  }, [session, trainingId, user, post]);

  if (loadError) {
    return <p className="p-6 text-muted-foreground">{loadError}</p>;
  }
  if (!session) {
    return <p className="p-6 text-muted-foreground">Opening the course...</p>;
  }

  const playerSrc = `${session.contentBaseUrl}${session.playerPath}?appOrigin=${encodeURIComponent(
    window.location.origin,
  )}`;

  return (
    <div className="flex h-full flex-col">
      {saveFailed && (
        <div className="border-b bg-destructive/10 px-4 py-2 text-sm">
          Your progress could not be saved. Keep this tab open; the course saves
          again automatically.
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
