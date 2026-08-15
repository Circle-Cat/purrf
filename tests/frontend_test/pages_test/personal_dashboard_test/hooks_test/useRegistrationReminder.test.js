import { describe, it, expect, vi, beforeEach } from "vitest";
import { renderHook } from "@testing-library/react";

import { useRegistrationReminder } from "@/pages/PersonalDashboard/hooks/useRegistrationReminder";
import * as reminderToast from "@/components/common/showReminderToast";

const SESSION_KEY = "mentorship-registration-toast-shown";

const openRound = {
  enabled: true,
  isLoading: false,
  isRegistered: false,
  isRegistrationOpen: true,
  registrationDeadlineAt: "2026-09-30T15:59:00Z",
  roundName: "2026 Fall",
};

const noOpenRound = {
  enabled: true,
  isLoading: false,
  isRegistered: false,
  isRegistrationOpen: false,
  registrationDeadlineAt: null,
  roundName: "",
};

const lastToast = () => reminderToast.showReminderToast.mock.calls.at(-1)[0];

describe("useRegistrationReminder", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    sessionStorage.clear();
    vi.spyOn(reminderToast, "showReminderToast").mockImplementation(() => {});
  });

  it("stays silent for someone who is not an admitted participant", () => {
    renderHook(() => useRegistrationReminder({ ...openRound, enabled: false }));

    expect(reminderToast.showReminderToast).not.toHaveBeenCalled();
    expect(sessionStorage.getItem(SESSION_KEY)).toBeNull();
  });

  it("waits for the mentorship data before saying anything", () => {
    // Mid-load the round looks closed and the user looks unregistered,
    // which is the wrong thing to announce.
    renderHook(() =>
      useRegistrationReminder({ ...openRound, isLoading: true }),
    );

    expect(reminderToast.showReminderToast).not.toHaveBeenCalled();
    expect(sessionStorage.getItem(SESSION_KEY)).toBeNull();
  });

  it("stays silent once the user has registered for the round", () => {
    renderHook(() =>
      useRegistrationReminder({ ...openRound, isRegistered: true }),
    );

    expect(reminderToast.showReminderToast).not.toHaveBeenCalled();
  });

  it("names the round and the deadline in Pacific time", () => {
    renderHook(() => useRegistrationReminder(openRound));

    expect(lastToast().title).toBe("Register for 2026 Fall");
    expect(lastToast().message).toBe(
      "Please complete your registration by Sep 30, 8:59 AM (PT) to get " +
        "matched with a partner.",
    );
  });

  it("holds the zone steady across the winter change", () => {
    // Standard time, three hours behind the summer offset the case above
    // exercises. The label stays PT either way rather than flipping
    // between PDT and PST.
    renderHook(() =>
      useRegistrationReminder({
        ...openRound,
        registrationDeadlineAt: "2026-12-31T15:59:00Z",
      }),
    );

    expect(lastToast().message).toContain("Dec 31, 7:59 AM (PT)");
  });

  it("drops the round from the title when it has no name", () => {
    renderHook(() =>
      useRegistrationReminder({ ...openRound, roundName: "  " }),
    );

    expect(lastToast().title).toBe("Register for the mentorship round");
  });

  it("says registration has not opened when no round is taking sign-ups", () => {
    renderHook(() => useRegistrationReminder(noOpenRound));

    expect(lastToast().title).toBe("Mentorship registration");
    expect(lastToast().message).toBe(
      "Registration hasn't opened yet—we'll reach out soon with the next steps!",
    );
  });

  it("says registration has not opened once the deadline has passed", () => {
    renderHook(() =>
      useRegistrationReminder({ ...openRound, isRegistrationOpen: false }),
    );

    expect(lastToast().title).toBe("Mentorship registration");
  });

  it("fires at most once per session", () => {
    const first = renderHook(() => useRegistrationReminder(openRound));
    first.unmount();

    renderHook(() => useRegistrationReminder(openRound));

    expect(reminderToast.showReminderToast).toHaveBeenCalledTimes(1);
  });

  it("writes the session marker after firing", () => {
    renderHook(() => useRegistrationReminder(openRound));

    expect(sessionStorage.getItem(SESSION_KEY)).toBe("1");
  });
});
