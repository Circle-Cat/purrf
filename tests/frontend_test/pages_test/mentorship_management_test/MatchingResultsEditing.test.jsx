import {
  act,
  fireEvent,
  render,
  screen,
  waitFor,
  within,
} from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { toast } from "sonner";
import MatchingResultsPage from "@/pages/MentorshipManagement/MatchingResultsPage";
import {
  getAllMentorshipRounds,
  getMatchingResults,
  getMatchingRun,
  getMatchingUnmatched,
  releaseMatchingEditLock,
  releaseMatchingEditLockOnLeave,
  saveMatchingDraft,
  takeMatchingEditLock,
} from "@/api/mentorshipApi";
import { useFeatureFlags } from "@/hooks/useFeatureFlags";
import { useAuth } from "@/context/auth";
import { FEATURE_FLAGS } from "@/constants/FeatureFlags";
import { formatInTz } from "@/utils/dateTime";

vi.mock("@/api/mentorshipApi", () => ({
  getAllMentorshipRounds: vi.fn(() => Promise.resolve({ data: [] })),
  getMatchingRun: vi.fn(() => Promise.resolve({ data: null })),
  getMatchingResults: vi.fn(() => Promise.resolve({ data: null })),
  getMatchingUnmatched: vi.fn(() => Promise.resolve({ data: null })),
  takeMatchingEditLock: vi.fn(() => Promise.resolve({ data: null })),
  releaseMatchingEditLock: vi.fn(() => Promise.resolve({ data: null })),
  releaseMatchingEditLockOnLeave: vi.fn(() => Promise.resolve()),
  saveMatchingDraft: vi.fn(() => Promise.resolve({ data: { draftCount: 0 } })),
}));

vi.mock("@/hooks/useFeatureFlags", () => ({ useFeatureFlags: vi.fn() }));

vi.mock("@/context/auth", () => ({ useAuth: vi.fn() }));

const READ = "mentorship.admin.read";
const WRITE = "mentorship.admin.write";
const ME = 5845;
const MINUTE = 60 * 1000;

const STARTED_AT = new Date(Date.now() - 60 * MINUTE).toISOString();

const lockOf = (minutesLeft, who = { userId: ME, name: "Dev Admin" }) => ({
  ...who,
  expiresAt: new Date(Date.now() + minutesLeft * MINUTE).toISOString(),
});

const overviewOf = (overrides = {}) => ({
  status: "succeeded",
  runId: 4,
  startedAt: STARTED_AT,
  finishedAt: STARTED_AT,
  triggeredByUserId: "5845",
  triggeredByName: "Dev Admin",
  matcherVersion: "1.2.0",
  runDate: STARTED_AT.slice(0, 10),
  inputWrittenAt: STARTED_AT,
  mentorCount: 4,
  menteeCount: 3,
  matchedCount: 2,
  unmatchedCount: 1,
  unmatchedMentors: [{ userId: 3102, name: "Bob Liu" }],
  editLock: null,
  draftCount: 1,
  mentorSlots: [
    { userId: 101, name: "Ann Lee", slots: 2, assigned: 1 },
    { userId: 102, name: "Dan Ma", slots: 2, assigned: 1 },
    { userId: 103, name: null, slots: 3, assigned: 0 },
    { userId: 104, name: "Fay Qi", slots: 1, assigned: 0 },
    { userId: 3102, name: "Bob Liu", slots: 2, assigned: 0 },
  ],
  problems: [],
  ...overrides,
});

// Saved as the matcher proposed it.
const cara = {
  mentee: { userId: 201, name: "Cara Wang" },
  mentor: { userId: 101, name: "Ann Lee" },
  score: 0.87342,
  matchType: "hungarian",
  recommendationReason: "Fintech overlap.",
  edited: false,
  matcherMentor: { userId: 101, name: "Ann Lee" },
  matcherReason: "Fintech overlap.",
  diagnosticReason: "",
  candidates: [
    { userId: 102, name: "Dan Ma", score: 0.91 },
    { userId: 103, name: null, score: 0.5 },
  ],
  menteeProfile: null,
  mentorProfile: null,
};

// Moved by hand in the saved draft, away from the matcher's Fay Qi.
const eve = {
  mentee: { userId: 202, name: "Eve Zhou" },
  mentor: { userId: 102, name: "Dan Ma" },
  score: 0.62,
  matchType: "mutual_yes",
  recommendationReason: "Moved by hand.",
  edited: true,
  matcherMentor: { userId: 104, name: "Fay Qi" },
  matcherReason: "You both asked for each other.",
  diagnosticReason: "",
  candidates: [{ userId: 102, name: "Dan Ma", score: 0.62 }],
  menteeProfile: null,
  mentorProfile: null,
};

const hal = {
  person: { userId: 203, name: "Hal Wu" },
  role: "mentee",
  profile: null,
  edited: false,
  matcherMentor: null,
  matcherReason: "",
  recommendationReason: "",
  diagnosticReason: "No mentor had a free slot.",
  candidates: [{ userId: 102, name: "Dan Ma", score: 0.4 }],
};

const bob = {
  person: { userId: 3102, name: "Bob Liu" },
  role: "mentor",
  profile: null,
  diagnosticReason: "",
  candidates: [],
};

const resultsPage = (items, overrides = {}) => ({
  data: {
    status: "succeeded",
    matchedCount: 2,
    unmatchedCount: 1,
    total: items.length,
    items,
    ...overrides,
  },
});

const unmatchedPage = (items) => ({
  data: { status: "succeeded", total: items.length, items },
});

const conflict = (message) =>
  Object.assign(new Error("Request failed with status code 409"), {
    response: { status: 409, data: { success: false, message, data: null } },
  });

const renderPage = (search = "") =>
  render(
    <MemoryRouter
      initialEntries={[
        { pathname: "/mentorship-management/matching/7", search },
      ]}
    >
      <Routes>
        <Route
          path="/mentorship-management/matching/:roundId"
          element={<MatchingResultsPage />}
        />
      </Routes>
    </MemoryRouter>,
  );

const rowOf = (text) => screen.getByText(text).closest("li");

const toggleRow = (text) =>
  fireEvent.click(within(rowOf(text)).getAllByRole("button")[0]);

const editButton = () => screen.queryByRole("button", { name: "Edit" });

const reasonBox = (text) =>
  within(rowOf(text)).getByRole("textbox", {
    name: "Reason shown to the pair",
  });

const typeReason = (text, value) =>
  fireEvent.change(reasonBox(text), { target: { value } });

const startEditing = async () => {
  fireEvent.click(await screen.findByRole("button", { name: "Edit" }));
  await screen.findByRole("button", { name: "Save draft" });
};

const pickMentor = async (user, rowText, optionName) => {
  await user.click(
    within(rowOf(rowText)).getByRole("combobox", { name: "Mentor" }),
  );
  await user.click(await screen.findByRole("option", { name: optionName }));
};

const optionNames = async (user, rowText) => {
  await user.click(
    within(rowOf(rowText)).getByRole("combobox", { name: "Mentor" }),
  );
  const names = (await screen.findAllByRole("option")).map(
    (o) => o.textContent,
  );
  await user.keyboard("{Escape}");
  return names;
};

describe("MatchingResultsPage editing", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    useFeatureFlags.mockReturnValue({ [FEATURE_FLAGS.MATCHING_RUN]: true });
    useAuth.mockReturnValue({
      permissions: [READ, WRITE],
      user: { userId: ME },
    });
    getAllMentorshipRounds.mockResolvedValue({
      data: [{ id: 7, name: "Fall 2026", isInProgress: true }],
    });
    getMatchingRun.mockResolvedValue({ data: overviewOf() });
    getMatchingResults.mockResolvedValue(resultsPage([cara, eve]));
    getMatchingUnmatched.mockResolvedValue(unmatchedPage([hal, bob]));
    takeMatchingEditLock.mockImplementation(() =>
      Promise.resolve({ data: lockOf(10) }),
    );
  });

  afterEach(() => {
    vi.useRealTimers();
  });

  describe("edit lock", () => {
    it("offers Edit to a writer on a succeeded run, in read-only until taken", async () => {
      renderPage();
      await screen.findByText("Cara Wang");

      expect(editButton()).toBeEnabled();
      expect(screen.queryByRole("textbox")).toBeNull();
      expect(screen.queryByRole("button", { name: "Save draft" })).toBeNull();
      expect(screen.queryByText(/Being edited by/)).toBeNull();
    });

    it("offers no Edit to a reader", async () => {
      useAuth.mockReturnValue({ permissions: [READ], user: { userId: ME } });
      renderPage();
      await screen.findByText("Cara Wang");

      expect(editButton()).toBeNull();
    });

    it("offers no Edit before the run has succeeded", async () => {
      getMatchingRun.mockResolvedValue({
        data: { status: "running", runId: 4, startedAt: STARTED_AT },
      });
      renderPage();
      await screen.findByText("Running");

      expect(editButton()).toBeNull();
    });

    it("says who else is editing and keeps Edit disabled", async () => {
      getMatchingRun.mockResolvedValue({
        data: overviewOf({
          editLock: lockOf(5, { userId: 3001, name: "Ann Lee" }),
        }),
      });
      renderPage();

      expect(
        await screen.findByText("Being edited by Ann Lee"),
      ).toBeInTheDocument();
      expect(editButton()).toBeDisabled();
    });

    it("tells a reader too who is editing", async () => {
      useAuth.mockReturnValue({ permissions: [READ], user: { userId: ME } });
      getMatchingRun.mockResolvedValue({
        data: overviewOf({
          editLock: lockOf(5, { userId: 3001, name: null }),
        }),
      });
      renderPage();

      expect(
        await screen.findByText("Being edited by ID 3001"),
      ).toBeInTheDocument();
    });

    it("lets me resume a lock I already hold", async () => {
      getMatchingRun.mockResolvedValue({
        data: overviewOf({ editLock: lockOf(5) }),
      });
      renderPage();
      await screen.findByText("Cara Wang");

      expect(screen.queryByText(/Being edited by/)).toBeNull();
      await startEditing();
      expect(takeMatchingEditLock).toHaveBeenCalledWith("7");
    });

    it("takes the lock and enters edit mode with nothing to save yet", async () => {
      renderPage();
      await screen.findByText("Cara Wang");

      await startEditing();

      expect(takeMatchingEditLock).toHaveBeenCalledWith("7");
      expect(editButton()).toBeNull();
      expect(screen.getByRole("button", { name: "Save draft" })).toBeDisabled();
      expect(
        screen.queryByRole("button", { name: "Discard changes" }),
      ).toBeNull();
      expect(screen.queryByText("Unsaved changes.")).toBeNull();
    });

    it("can stop editing with nothing changed, giving the lock back", async () => {
      renderPage();
      await screen.findByText("Cara Wang");
      await startEditing();

      fireEvent.click(screen.getByRole("button", { name: "Stop editing" }));

      await waitFor(() =>
        expect(releaseMatchingEditLock).toHaveBeenCalledWith("7"),
      );
      expect(editButton()).toBeInTheDocument();
      expect(saveMatchingDraft).not.toHaveBeenCalled();
    });

    it("stays read-only and says why when someone else took it first", async () => {
      const toastError = vi.spyOn(toast, "error");
      takeMatchingEditLock.mockRejectedValue(
        conflict("Being edited by Ann Lee."),
      );
      renderPage();
      await screen.findByText("Cara Wang");

      fireEvent.click(editButton());

      await waitFor(() =>
        expect(toastError).toHaveBeenCalledWith("Being edited by Ann Lee."),
      );
      expect(screen.queryByRole("button", { name: "Save draft" })).toBeNull();
      expect(editButton()).toBeInTheDocument();
      // Fetched again to show who holds it.
      await waitFor(() => expect(getMatchingRun).toHaveBeenCalledTimes(2));
    });
  });

  describe("keeping the lock", () => {
    beforeEach(() => {
      vi.useFakeTimers({ shouldAdvanceTime: true });
    });

    const editCara = async () => {
      renderPage();
      await screen.findByText("Cara Wang");
      await startEditing();
      toggleRow("Cara Wang");
    };

    const advance = (ms) =>
      act(async () => {
        await vi.advanceTimersByTimeAsync(ms);
      });

    it("renews on a change at most once a minute", async () => {
      await editCara();
      expect(takeMatchingEditLock).toHaveBeenCalledTimes(1);

      typeReason("Cara Wang", "One");
      expect(takeMatchingEditLock).toHaveBeenCalledTimes(1);

      await advance(61 * 1000);
      typeReason("Cara Wang", "Two");
      expect(takeMatchingEditLock).toHaveBeenCalledTimes(2);

      typeReason("Cara Wang", "Three");
      await advance(30 * 1000);
      typeReason("Cara Wang", "Four");
      expect(takeMatchingEditLock).toHaveBeenCalledTimes(2);
    });

    it("asks whether I am still editing two minutes before the lock ends", async () => {
      await editCara();
      const firstLock = (await takeMatchingEditLock.mock.results[0].value).data;

      await advance(7 * MINUTE);
      expect(screen.queryByText(/Still editing\?/)).toBeNull();

      await advance(MINUTE + 1000);
      const at = formatInTz(
        firstLock.expiresAt,
        "America/Los_Angeles",
        "HH:mm",
      );
      expect(
        screen.getByText(`Still editing? Your lock ends at ${at}.`),
      ).toBeInTheDocument();

      fireEvent.click(screen.getByRole("button", { name: "Keep editing" }));

      await waitFor(() =>
        expect(screen.queryByText(/Still editing\?/)).toBeNull(),
      );
      expect(takeMatchingEditLock).toHaveBeenCalledTimes(2);
    });

    it("leaves edit mode and drops the changes when the lock ends", async () => {
      await editCara();
      typeReason("Cara Wang", "Not kept.");
      expect(screen.getByText("Unsaved changes.")).toBeInTheDocument();

      await advance(10 * MINUTE + 1000);

      expect(
        screen.getByText(
          "Your editing lock ended; unsaved changes were not kept.",
        ),
      ).toBeInTheDocument();
      expect(screen.queryByRole("button", { name: "Save draft" })).toBeNull();
      expect(screen.queryByRole("textbox")).toBeNull();
      expect(editButton()).toBeEnabled();
      expect(
        within(rowOf("Cara Wang")).getAllByText("Fintech overlap.").length,
      ).toBeGreaterThan(0);
      expect(screen.queryByText("Not kept.")).toBeNull();
      expect(releaseMatchingEditLock).not.toHaveBeenCalled();
    });
  });

  describe("editing a matched row", () => {
    const editRow = async (text) => {
      renderPage();
      await screen.findByText("Cara Wang");
      await startEditing();
      toggleRow(text);
    };

    it("offers no mentor, the matcher's mentor and each candidate with slots and score", async () => {
      const user = userEvent.setup();
      await editRow("Cara Wang");

      expect(
        within(rowOf("Cara Wang")).getByRole("combobox", { name: "Mentor" }),
      ).toHaveTextContent("Ann Lee (ID 101) — 1 of 2 slots free");
      expect(await optionNames(user, "Cara Wang")).toEqual([
        "No mentor this round",
        "Ann Lee (ID 101) — 1 of 2 slots free",
        "Dan Ma (ID 102) — 1 of 2 slots free · 0.91",
        "ID 103 — 3 of 3 slots free · 0.5",
      ]);
    });

    it("changing the mentor clears the reason, asks for one and moves a slot", async () => {
      const user = userEvent.setup();
      await editRow("Cara Wang");

      await pickMentor(user, "Cara Wang", /^Dan Ma \(ID 102\)/);

      const row = within(rowOf("Cara Wang"));
      expect(reasonBox("Cara Wang")).toHaveValue("");
      expect(row.getByText("0/300")).toBeInTheDocument();
      expect(
        row.getByText("A matched mentee needs a reason."),
      ).toBeInTheDocument();
      expect(screen.getByText("Unsaved changes.")).toBeInTheDocument();
      // The summary line follows the unsaved choice.
      expect(row.getByText("Edited")).toBeInTheDocument();
      expect(row.queryByText("Scored")).toBeNull();
      expect(row.getByText("0.91")).toBeInTheDocument();
      expect(row.getByText("Dan Ma")).toBeInTheDocument();

      expect(await optionNames(user, "Cara Wang")).toEqual([
        "No mentor this round",
        "Ann Lee (ID 101) — 2 of 2 slots free",
        "Dan Ma (ID 102) — 0 of 2 slots free · 0.91",
        "ID 103 — 3 of 3 slots free · 0.5",
      ]);

      typeReason("Cara Wang", "Dan knows payments.");
      expect(row.queryByText("A matched mentee needs a reason.")).toBeNull();
    });

    it("needs no reason with no mentor", async () => {
      const user = userEvent.setup();
      await editRow("Cara Wang");

      await pickMentor(user, "Cara Wang", "No mentor this round");

      const row = within(rowOf("Cara Wang"));
      expect(row.queryByText("A matched mentee needs a reason.")).toBeNull();
      expect(row.getByText("Edited")).toBeInTheDocument();
      expect(row.getByText("No mentor")).toBeInTheDocument();
      expect(row.getByText("—")).toBeInTheDocument();
    });

    it("counts the reason and turns red past 300", async () => {
      await editRow("Cara Wang");
      const row = within(rowOf("Cara Wang"));
      expect(row.getByText("16/300")).not.toHaveClass("text-red-600");

      typeReason("Cara Wang", "x".repeat(300));
      expect(row.getByText("300/300")).not.toHaveClass("text-red-600");

      typeReason("Cara Wang", "x".repeat(301));
      expect(row.getByText("301/300")).toHaveClass("text-red-600");
    });

    it("shows what the matcher proposed once the row differs, and reverts to it", async () => {
      await editRow("Cara Wang");
      expect(
        within(rowOf("Cara Wang")).queryByText(/The matcher proposed/),
      ).toBeNull();

      typeReason("Cara Wang", "Rewritten.");
      expect(
        within(rowOf("Cara Wang")).getByText(
          "The matcher proposed: Ann Lee (ID 101) — Fintech overlap.",
        ),
      ).toBeInTheDocument();

      fireEvent.click(
        within(rowOf("Cara Wang")).getByRole("button", {
          name: "Revert to the matcher's result",
        }),
      );

      expect(reasonBox("Cara Wang")).toHaveValue("Fintech overlap.");
      expect(
        within(rowOf("Cara Wang")).queryByText(/The matcher proposed/),
      ).toBeNull();
      // Back to the saved row, so nothing is left to save.
      expect(screen.queryByText("Unsaved changes.")).toBeNull();
    });

    it("reverts a saved edit as an unsaved change", async () => {
      await editRow("Eve Zhou");
      const row = within(rowOf("Eve Zhou"));
      expect(
        row.getByText(
          "The matcher proposed: Fay Qi (ID 104) — You both asked for each other.",
        ),
      ).toBeInTheDocument();

      fireEvent.click(
        row.getByRole("button", { name: "Revert to the matcher's result" }),
      );

      expect(row.getByRole("combobox", { name: "Mentor" })).toHaveTextContent(
        "Fay Qi (ID 104) — 0 of 1 slots free",
      );
      expect(reasonBox("Eve Zhou")).toHaveValue(
        "You both asked for each other.",
      );
      expect(row.queryByText(/The matcher proposed/)).toBeNull();
      expect(screen.getByText("Unsaved changes.")).toBeInTheDocument();
      // Fay is not a candidate, so the unsaved choice has no score.
      expect(row.getByText("—")).toBeInTheDocument();
      expect(row.getByText("Edited")).toBeInTheDocument();
    });
  });

  describe("editing the Unmatched tab", () => {
    it("gives an unmatched mentee a candidate", async () => {
      const user = userEvent.setup();
      renderPage("?tab=unmatched");
      await screen.findByText("Hal Wu");
      await startEditing();
      toggleRow("Hal Wu");

      expect(await optionNames(user, "Hal Wu")).toEqual([
        "No mentor this round",
        "Dan Ma (ID 102) — 1 of 2 slots free · 0.4",
      ]);
      await pickMentor(user, "Hal Wu", /^Dan Ma/);
      typeReason("Hal Wu", "Dan has room.");

      const row = within(rowOf("Hal Wu"));
      expect(row.getByText("Dan Ma")).toBeInTheDocument();
      expect(row.getByText("Edited")).toBeInTheDocument();
      expect(
        row.getByText("The matcher proposed: No mentor — no reason"),
      ).toBeInTheDocument();
    });

    it("does not edit an unmatched mentor", async () => {
      renderPage("?tab=unmatched");
      await screen.findByText("Bob Liu");
      await startEditing();
      toggleRow("Bob Liu");

      const row = within(rowOf("Bob Liu"));
      expect(row.queryByRole("combobox")).toBeNull();
      expect(row.queryByRole("textbox")).toBeNull();
    });
  });

  describe("unsaved changes", () => {
    it("survive switching tabs", async () => {
      renderPage();
      await screen.findByText("Cara Wang");
      await startEditing();
      toggleRow("Cara Wang");
      typeReason("Cara Wang", "Kept across tabs.");

      await userEvent.click(screen.getByRole("tab", { name: "Unmatched (2)" }));
      await screen.findByText("Hal Wu");
      expect(screen.getByText("Unsaved changes.")).toBeInTheDocument();

      await userEvent.click(screen.getByRole("tab", { name: "Matched (2)" }));
      await screen.findByText("Cara Wang");
      expect(
        within(rowOf("Cara Wang")).getAllByText("Kept across tabs.").length,
      ).toBeGreaterThan(0);
      toggleRow("Cara Wang");
      expect(reasonBox("Cara Wang")).toHaveValue("Kept across tabs.");
    });

    it("survive paging", async () => {
      getMatchingResults.mockImplementation((roundId, { offset }) =>
        Promise.resolve(
          resultsPage(offset === 0 ? [cara] : [eve], { total: 25 }),
        ),
      );
      renderPage();
      await screen.findByText("Cara Wang");
      await startEditing();
      toggleRow("Cara Wang");
      typeReason("Cara Wang", "Kept across pages.");

      fireEvent.click(screen.getByRole("button", { name: "Next" }));
      await screen.findByText("Eve Zhou");
      fireEvent.click(screen.getByRole("button", { name: "Prev" }));
      await screen.findByText("Cara Wang");

      expect(
        within(rowOf("Cara Wang")).getAllByText("Kept across pages.").length,
      ).toBeGreaterThan(0);
      expect(screen.getByText("Unsaved changes.")).toBeInTheDocument();
    });
  });

  describe("saving and discarding", () => {
    it("saves every changed row, leaves edit mode and fetches again", async () => {
      const user = userEvent.setup();
      renderPage();
      await screen.findByText("Cara Wang");
      await startEditing();
      toggleRow("Cara Wang");
      await pickMentor(user, "Cara Wang", /^ID 103/);
      typeReason("Cara Wang", "Strong in payments.");

      await userEvent.click(screen.getByRole("tab", { name: "Unmatched (2)" }));
      await screen.findByText("Hal Wu");
      toggleRow("Hal Wu");
      await pickMentor(user, "Hal Wu", /^Dan Ma/);
      typeReason("Hal Wu", "Dan has room.");
      const resultsCalls = getMatchingUnmatched.mock.calls.length;

      fireEvent.click(screen.getByRole("button", { name: "Save draft" }));

      await waitFor(() =>
        expect(screen.queryByRole("button", { name: "Save draft" })).toBeNull(),
      );
      expect(saveMatchingDraft).toHaveBeenCalledTimes(1);
      expect(saveMatchingDraft).toHaveBeenCalledWith("7", [
        {
          menteeId: "201",
          mentorId: "103",
          recommendationReason: "Strong in payments.",
        },
        {
          menteeId: "203",
          mentorId: "102",
          recommendationReason: "Dan has room.",
        },
      ]);
      expect(screen.queryByText("Unsaved changes.")).toBeNull();
      expect(editButton()).toBeInTheDocument();
      await waitFor(() => expect(getMatchingRun).toHaveBeenCalledTimes(2));
      await waitFor(() =>
        expect(getMatchingUnmatched.mock.calls.length).toBe(resultsCalls + 1),
      );
      expect(getMatchingUnmatched).toHaveBeenLastCalledWith("7", {
        limit: 20,
        offset: 0,
      });
      expect(releaseMatchingEditLock).not.toHaveBeenCalled();
    });

    it("stays in edit mode with the changes when saving fails", async () => {
      const toastError = vi.spyOn(toast, "error");
      saveMatchingDraft.mockRejectedValue(
        conflict("You do not hold the edit lock."),
      );
      renderPage();
      await screen.findByText("Cara Wang");
      await startEditing();
      toggleRow("Cara Wang");
      typeReason("Cara Wang", "Unsaved still.");

      fireEvent.click(screen.getByRole("button", { name: "Save draft" }));

      await waitFor(() =>
        expect(toastError).toHaveBeenCalledWith(
          "You do not hold the edit lock.",
        ),
      );
      expect(screen.getByText("Unsaved changes.")).toBeInTheDocument();
      expect(reasonBox("Cara Wang")).toHaveValue("Unsaved still.");
    });

    it("discards the changes and releases the lock", async () => {
      renderPage();
      await screen.findByText("Cara Wang");
      await startEditing();
      toggleRow("Cara Wang");
      typeReason("Cara Wang", "Thrown away.");

      fireEvent.click(screen.getByRole("button", { name: "Discard changes" }));

      await waitFor(() =>
        expect(releaseMatchingEditLock).toHaveBeenCalledWith("7"),
      );
      expect(screen.queryByRole("button", { name: "Save draft" })).toBeNull();
      expect(screen.queryByText("Thrown away.")).toBeNull();
      expect(editButton()).toBeInTheDocument();
      expect(saveMatchingDraft).not.toHaveBeenCalled();
    });
  });

  describe("leaving the page", () => {
    it("releases the lock when the page unmounts in edit mode", async () => {
      const { unmount } = renderPage();
      await screen.findByText("Cara Wang");
      await startEditing();

      unmount();

      expect(releaseMatchingEditLockOnLeave).toHaveBeenCalledWith("7");
    });

    it("releases the lock when the tab is closed in edit mode", async () => {
      renderPage();
      await screen.findByText("Cara Wang");
      await startEditing();

      fireEvent(window, new Event("pagehide"));

      expect(releaseMatchingEditLockOnLeave).toHaveBeenCalledWith("7");
    });

    it("releases nothing when not editing", async () => {
      const { unmount } = renderPage();
      await screen.findByText("Cara Wang");

      fireEvent(window, new Event("pagehide"));
      unmount();

      expect(releaseMatchingEditLockOnLeave).not.toHaveBeenCalled();
    });
  });

  describe("what everyone sees", () => {
    beforeEach(() => {
      useAuth.mockReturnValue({ permissions: [READ], user: { userId: ME } });
    });

    it("marks a saved edit and shows its saved score", async () => {
      renderPage();
      await screen.findByText("Eve Zhou");

      const row = within(rowOf("Eve Zhou"));
      expect(row.getByText("Edited")).toBeInTheDocument();
      expect(row.queryByText("Both asked")).toBeNull();
      expect(row.getByText("0.62")).toBeInTheDocument();
      expect(
        within(rowOf("Cara Wang")).getByText("Scored"),
      ).toBeInTheDocument();

      toggleRow("Eve Zhou");
      expect(
        row.getByText(
          "The matcher proposed: Fay Qi (ID 104) — You both asked for each other.",
        ),
      ).toBeInTheDocument();
      expect(
        row.queryByRole("button", { name: "Revert to the matcher's result" }),
      ).toBeNull();
    });

    it("lists the saved draft's problems", async () => {
      getMatchingRun.mockResolvedValue({
        data: overviewOf({
          problems: [
            {
              code: "over_slots",
              mentor: { userId: 102, name: "Dan Ma" },
              assigned: 3,
              slots: 2,
            },
            {
              code: "over_slots",
              mentor: { userId: 104, name: null },
              assigned: 2,
              slots: 1,
            },
            {
              code: "reason_too_long",
              mentee: { userId: 201, name: "Cara Wang" },
            },
            { code: "no_reason", mentee: { userId: 203, name: "Hal Wu" } },
          ],
        }),
      });
      renderPage();

      expect(
        await screen.findByText("Problems to fix before publishing"),
      ).toBeInTheDocument();
      const lines = within(screen.getByRole("region", { name: "Problems" }))
        .getAllByRole("listitem")
        .map((li) => li.textContent);
      expect(lines).toEqual([
        "Dan Ma (ID 102) is given 3 mentees but has 2 slots this run.",
        "ID 104 is given 2 mentees but has 1 slot this run.",
        "The reason for Cara Wang (ID 201) is over 300 characters.",
        "Hal Wu (ID 203) is matched with no reason.",
      ]);
    });

    it("lists no problems when there are none", async () => {
      renderPage();
      await screen.findByText("Cara Wang");

      expect(
        screen.queryByText("Problems to fix before publishing"),
      ).toBeNull();
    });
  });
});
