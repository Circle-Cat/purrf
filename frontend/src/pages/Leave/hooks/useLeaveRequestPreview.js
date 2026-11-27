import { useEffect, useState } from "react";

import { previewLeaveRequest } from "@/api/leaveApi";
import { refusalMessage } from "@/pages/Leave/hooks/useMyLeaveRequests";

/** How long typing has to pause before the server is asked. */
export const PREVIEW_DELAY_MS = 400;

/**
 * What a request would come to, asked of the server while the form is filled
 * in.
 *
 * The server works the figures out with the same rules filing uses, so the
 * form never quotes a number the list then contradicts. Each answer is kept
 * with the request it answers, so a slow reply for dates since changed is
 * never shown against the new ones.
 *
 * @param {object|null} payload The request as it would be filed, or null
 *   while the form cannot be sent yet.
 * @returns {{preview: object|null, previewError: string|null}}
 */
export function useLeaveRequestPreview(payload) {
  const key = payload ? JSON.stringify(payload) : null;
  const [answer, setAnswer] = useState({
    key: null,
    preview: null,
    error: null,
  });

  useEffect(() => {
    if (!key) return undefined;
    let isCurrent = true;
    const timer = setTimeout(async () => {
      try {
        const response = await previewLeaveRequest(JSON.parse(key));
        if (isCurrent) {
          setAnswer({ key, preview: response?.data ?? null, error: null });
        }
      } catch (error) {
        if (isCurrent) {
          setAnswer({ key, preview: null, error: refusalMessage(error) });
        }
      }
    }, PREVIEW_DELAY_MS);
    return () => {
      isCurrent = false;
      clearTimeout(timer);
    };
  }, [key]);

  const isAnswered = key !== null && answer.key === key;
  return {
    preview: isAnswered ? answer.preview : null,
    previewError: isAnswered ? answer.error : null,
  };
}
