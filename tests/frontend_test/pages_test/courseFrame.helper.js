import { expect, vi } from "vitest";
import { screen, waitFor } from "@testing-library/react";

/**
 * Lets a test wait for the course bridge to be listening, not just rendered.
 *
 * useTrainingRuntime adds its window "message" listener from an effect, and
 * React can run that effect a scheduler task after the frame is already in
 * the DOM. A message dispatched in between reaches nobody: a save is never
 * made, and an assertion that nothing was saved passes without testing
 * anything. On a loaded machine that gap is wide enough to hit.
 *
 * Call after vi.clearAllMocks(), which would otherwise wipe the calls this
 * counts, and restore in afterEach.
 */
export const watchCourseBridge = () => {
  const add = vi.spyOn(window, "addEventListener");
  const remove = vi.spyOn(window, "removeEventListener");
  const messageCalls = (spy) =>
    spy.mock.calls.filter(([type]) => type === "message").length;

  return {
    findCourseFrame: async () => {
      const frame = await screen.findByTitle(/course/i);
      await waitFor(() =>
        expect(messageCalls(add)).toBeGreaterThan(messageCalls(remove)),
      );
      return frame;
    },
    restore: () => {
      add.mockRestore();
      remove.mockRestore();
    },
  };
};
