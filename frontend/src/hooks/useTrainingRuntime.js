import { useCallback, useEffect, useRef, useState } from "react";
import { openSession, saveProgress } from "@/api/trainingApi";
import request from "@/utils/request";
import { API_ENDPOINTS } from "@/constants/ApiEndpoints";
import { MESSAGE_TYPES, isTrustedMessage } from "@/training/scormBridge";

/**
 * Opens a training session and bridges postMessage traffic with the course
 * frame it points at: replies to the frame's READY handshake, saves every
 * commit and finish, and falls back to a save on unload.
 *
 * Shared by the learner's course page and the admin trial page so the
 * origin check -- the whole security of the bridge -- exists in one place.
 *
 * @param {string|number|undefined|null} trainingId Absent until known.
 * @param {{userId?: number, email?: string}} [user]
 * @returns {{
 *   session: object|null,
 *   loadError: string|null,
 *   saveFailed: boolean,
 *   frameRef: import("react").RefObject<HTMLIFrameElement>,
 *   playerSrc: string|null,
 *   writes: Array<{type: "commit"|"finish", cmi: Object<string, string>, receivedAt: number}>,
 * }}
 */
export default function useTrainingRuntime(trainingId, user) {
  const [session, setSession] = useState(null);
  const [loadError, setLoadError] = useState(null);
  const [saveFailed, setSaveFailed] = useState(false);
  const [writes, setWrites] = useState([]);
  const frameRef = useRef(null);
  // The last cmi a commit or finish carried, and whether it has been flushed
  // by the unload safety net below. The tab can close before the ordinary
  // save even resolves, so unload resends the same cmi unconditionally.
  const lastCmiRef = useRef(null);
  const unsavedRef = useRef(false);
  // One save per assignment on the wire at a time. A course reports
  // `incomplete` and then `completed` within the same second, and two such
  // requests in flight together each decide the assignment's next status from
  // a server-side read the other has not written to yet.
  const saveChainRef = useRef(Promise.resolve());

  useEffect(() => {
    if (!trainingId) return undefined;
    let cancelled = false;
    setSession(null);
    setLoadError(null);
    setWrites([]);
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

    const queueSave = (cmi, extra) => {
      const queued = saveChainRef.current.then(() =>
        saveProgress(trainingId, { cmi, ...extra }),
      );
      // The chain has to survive a rejected save, or one failure strands
      // every save after it.
      saveChainRef.current = queued.catch(() => {});
      return queued;
    };

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
              // The auth context carries no name field, so email stands in
              // as the learner-visible name the course displays and reports.
              displayName: user?.email ?? "",
            },
            entryPath: session.entryPath,
          },
          contentOrigin,
        );
        return;
      }

      if (event.data.type === MESSAGE_TYPES.ERROR) {
        // The player already surfaced this to the course; without a
        // consumer here, a learner's "blank iframe" report leaves nothing
        // behind it to investigate.
        console.error(
          `[useTrainingRuntime] scorm:error from training ${trainingId}`,
          { code: event.data.code, message: event.data.message },
        );
        return;
      }

      if (
        event.data.type === MESSAGE_TYPES.COMMIT ||
        event.data.type === MESSAGE_TYPES.FINISH
      ) {
        setWrites((prev) => [
          ...prev,
          {
            type:
              event.data.type === MESSAGE_TYPES.FINISH ? "finish" : "commit",
            cmi: event.data.cmi,
            receivedAt: Date.now(),
          },
        ]);
        lastCmiRef.current = event.data.cmi;
        unsavedRef.current = true;
        try {
          await queueSave(event.data.cmi);
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

    // An XHR in flight when the tab closes is dropped; fetch with keepalive
    // survives it, so this one save goes around axios.
    const onBeforeUnload = () => {
      if (!unsavedRef.current) return;
      unsavedRef.current = false;
      fetch(
        `${request.defaults.baseURL}${API_ENDPOINTS.TRAINING_PROGRESS(trainingId)}`,
        {
          method: "POST",
          credentials: "include",
          keepalive: true,
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ cmi: lastCmiRef.current }),
        },
      );
    };

    window.addEventListener("message", onMessage);
    window.addEventListener("beforeunload", onBeforeUnload);
    return () => {
      window.removeEventListener("message", onMessage);
      window.removeEventListener("beforeunload", onBeforeUnload);
    };
  }, [session, trainingId, user, post]);

  const playerSrc = session
    ? `${session.contentBaseUrl}${session.playerPath}?appOrigin=${encodeURIComponent(
        window.location.origin,
      )}`
    : null;

  return { session, loadError, saveFailed, frameRef, playerSrc, writes };
}
