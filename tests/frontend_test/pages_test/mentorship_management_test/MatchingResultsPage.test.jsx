import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, it, expect, vi, beforeEach } from "vitest";
import { MemoryRouter, Route, Routes, useLocation } from "react-router-dom";
import MatchingResultsPage from "@/pages/MentorshipManagement/MatchingResultsPage";
import {
  getAllMentorshipRounds,
  getMatchingResults,
  getMatchingRun,
  getMatchingUnmatched,
} from "@/api/mentorshipApi";
import { useFeatureFlags } from "@/hooks/useFeatureFlags";
import { useAuth } from "@/context/auth";
import { FEATURE_FLAGS } from "@/constants/FeatureFlags";
import { formatInTz } from "@/utils/dateTime";

vi.mock("@/api/mentorshipApi", () => ({
  getAllMentorshipRounds: vi.fn(),
  getMatchingRun: vi.fn(),
  getMatchingResults: vi.fn(),
  getMatchingUnmatched: vi.fn(),
  takeMatchingEditLock: vi.fn(() => Promise.resolve({ data: null })),
  releaseMatchingEditLock: vi.fn(() => Promise.resolve({ data: null })),
  releaseMatchingEditLockOnLeave: vi.fn(() => Promise.resolve()),
  saveMatchingDraft: vi.fn(() => Promise.resolve({ data: { draftCount: 0 } })),
  getMentorshipApprovers: vi.fn(() => Promise.resolve({ data: [] })),
  requestMatchingPublish: vi.fn(() => Promise.resolve({ data: {} })),
  reassignMentorshipApproval: vi.fn(() => Promise.resolve({ data: {} })),
  decideMentorshipApproval: vi.fn(() => Promise.resolve({ data: {} })),
  withdrawMentorshipApproval: vi.fn(() => Promise.resolve({ data: {} })),
}));

vi.mock("@/hooks/useFeatureFlags", () => ({ useFeatureFlags: vi.fn() }));

vi.mock("@/context/auth", () => ({ useAuth: vi.fn() }));

const ROUNDS = [
  { id: 7, name: "Fall 2026", isInProgress: true },
  { id: 3, name: "Spring 2026", isInProgress: false },
];

const STARTED_AT = new Date(Date.now() - 60 * 60 * 1000).toISOString();

const runOf = (overrides = {}) => ({
  status: "running",
  runId: 4,
  startedAt: STARTED_AT,
  triggeredByUserId: "5845",
  triggeredByName: "Dev Admin",
  mentorCount: 3,
  menteeCount: 5,
  ...overrides,
});

const succeededRun = (overrides = {}) =>
  runOf({
    status: "succeeded",
    finishedAt: STARTED_AT,
    matcherVersion: "1.2.0",
    runDate: STARTED_AT.slice(0, 10),
    inputWrittenAt: STARTED_AT,
    matchedCount: 2,
    unmatchedCount: 1,
    menteeCount: 3,
    unmatchedMentors: [
      { userId: 3102, name: "Bob Liu" },
      { userId: 3999, name: null },
    ],
    editLock: null,
    draftCount: 0,
    mentorSlots: [
      { userId: 101, name: "Ann Lee", slots: 2, assigned: 1 },
      { userId: 102, name: "Dan Ma", slots: 1, assigned: 0 },
      { userId: 104, name: "Fay Qi", slots: 1, assigned: 1 },
      { userId: 3102, name: "Bob Liu", slots: 2, assigned: 0 },
      { userId: 3999, name: null, slots: 1, assigned: 0 },
    ],
    problems: [],
    ...overrides,
  });

const menteeProfile = {
  userId: 201,
  timezone: "Asia/Shanghai",
  goal: "Land a first SWE job",
  skills: {
    resume_guidance: true,
    networking: false,
    technical_skills: true,
  },
  education: [
    {
      degree: "MS",
      school: "State University",
      fieldOfStudy: "Computer Science",
      startDate: "2022-09-01",
      endDate: "2024-06-01",
    },
  ],
  workHistory: [
    {
      title: "Analyst",
      company: "Acme",
      startDate: "2024-07-01",
      endDate: null,
      isCurrentJob: true,
    },
  ],
  specificIndustry: { swe: true, ds: false, pm: true, uiux: false },
  maxPartners: null,
  careerTransition: null,
  careerTransitionOther: null,
  developmentRegion: null,
  developmentRegionOther: null,
  externalMentoringExp: null,
  mentorshipRoundsParticipated: 2,
  mentorshipRoundsCompleted: 1,
  transitionType: "via_cs_masters",
  transitionTypeOther: null,
  urgency: "6m",
  jobMarketRegion: "canada",
  jobMarketRegionOther: "Toronto only",
  menteeStage: "job_searching",
  expectedPartners: [{ userId: 101, name: "Ann Lee" }],
  unexpectedPartners: [],
};

const mentorProfile = {
  userId: 101,
  timezone: "America/New_York",
  goal: null,
  skills: { career_path_guidance: true },
  education: [],
  workHistory: [
    {
      title: "Staff Engineer",
      company: "Globex",
      startDate: "2015-01-01",
      endDate: "2023-12-31",
      isCurrentJob: false,
    },
  ],
  specificIndustry: null,
  maxPartners: 2,
  careerTransition: "none_cs_background",
  careerTransitionOther: "Physics PhD",
  developmentRegion: "us",
  developmentRegionOther: null,
  externalMentoringExp: "1_to_3",
  mentorshipRoundsParticipated: null,
  mentorshipRoundsCompleted: null,
  transitionType: null,
  transitionTypeOther: null,
  urgency: null,
  jobMarketRegion: null,
  jobMarketRegionOther: null,
  menteeStage: null,
  expectedPartners: [],
  unexpectedPartners: [{ userId: 205, name: null }],
};

const scoredItem = {
  mentee: { userId: 201, name: "Cara Wang" },
  mentor: { userId: 101, name: "Ann Lee" },
  score: 0.87342,
  matchType: "hungarian",
  recommendationReason: "Both work in fintech and share a timezone overlap.",
  edited: false,
  matcherMentor: { userId: 101, name: "Ann Lee" },
  matcherReason: "Both work in fintech and share a timezone overlap.",
  diagnosticReason: "Second-best total cost was 0.4 higher.",
  candidates: [
    { userId: 102, name: "Dan Ma", score: 0.91 },
    { userId: 103, name: null, score: 0.5 },
  ],
  menteeProfile,
  mentorProfile,
};

const mutualItem = {
  mentee: { userId: 202, name: "Eve Zhou" },
  mentor: { userId: 104, name: "Fay Qi" },
  score: null,
  matchType: "mutual_yes",
  recommendationReason: "You both asked for each other.",
  edited: false,
  matcherMentor: { userId: 104, name: "Fay Qi" },
  matcherReason: "You both asked for each other.",
  diagnosticReason: "",
  candidates: [],
  menteeProfile: null,
  mentorProfile: null,
};

const unmatchedMentee = {
  person: { userId: 203, name: null },
  role: "mentee",
  profile: null,
  edited: false,
  matcherMentor: null,
  matcherReason: "",
  recommendationReason: "",
  diagnosticReason: "No mentor had a free slot.",
  candidates: [{ userId: 102, name: "Dan Ma", score: 0.4 }],
};

const quietMentee = {
  person: { userId: 204, name: "Gus Ho" },
  role: "mentee",
  profile: null,
  edited: false,
  matcherMentor: null,
  matcherReason: "",
  recommendationReason: "",
  diagnosticReason: "",
  candidates: [],
};

const unmatchedMentor = {
  person: { userId: 3102, name: "Bob Liu" },
  role: "mentor",
  profile: mentorProfile,
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

const unmatchedPage = (items, overrides = {}) => ({
  data: { status: "succeeded", total: items.length, items, ...overrides },
});

const LocationProbe = () => {
  const location = useLocation();
  return (
    <>
      <div data-testid="location-path">{location.pathname}</div>
      <div data-testid="location-search">{location.search}</div>
    </>
  );
};

const renderPage = ({ search = "", state } = {}) =>
  render(
    <MemoryRouter
      initialEntries={[
        { pathname: "/mentorship-management/matching/7", search, state },
      ]}
    >
      <Routes>
        <Route
          path="/mentorship-management/matching/:roundId"
          element={<MatchingResultsPage />}
        />
        <Route path="/mentorship-management" element={<div>Console</div>} />
      </Routes>
      <LocationProbe />
    </MemoryRouter>,
  );

const CANDIDATES_NOTE =
  "A candidate can score higher than the chosen mentor: the matcher finds the best set of pairs overall, not the best mentor for each mentee alone.";

const urlParams = () =>
  new URLSearchParams(screen.getByTestId("location-search").textContent);

const rowOf = (text) => screen.getByText(text).closest("li");

const toggleRow = (text) =>
  userEvent.click(within(rowOf(text)).getAllByRole("button")[0]);

describe("MatchingResultsPage", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    useFeatureFlags.mockReturnValue({ [FEATURE_FLAGS.MATCHING_RUN]: true });
    useAuth.mockReturnValue({
      permissions: ["mentorship.admin.read"],
      user: { userId: 5845 },
    });
    getAllMentorshipRounds.mockResolvedValue({ data: ROUNDS });
    getMatchingRun.mockResolvedValue({ data: { status: "never_run" } });
    getMatchingResults.mockResolvedValue(resultsPage([scoredItem, mutualItem]));
    getMatchingUnmatched.mockResolvedValue(
      unmatchedPage([unmatchedMentee, quietMentee, unmatchedMentor]),
    );
  });

  describe("header", () => {
    it("names the round and links back to the participants with their search", async () => {
      renderPage({ state: { returnSearch: "?round=7&eligible=1" } });

      expect(
        await screen.findByText("Matching — Fall 2026"),
      ).toBeInTheDocument();
      expect(
        screen.getByRole("link", { name: "Participants" }),
      ).toHaveAttribute("href", "/mentorship-management?round=7&eligible=1");
      expect(getMatchingRun).toHaveBeenCalledWith("7");
    });

    it("says who started the run, when, and over how many", async () => {
      getMatchingRun.mockResolvedValue({ data: runOf() });
      renderPage();

      const at = formatInTz(
        STARTED_AT,
        "America/Los_Angeles",
        "yyyy-MM-dd HH:mm",
      );
      expect(
        await screen.findByText(
          `Run 4 · started by Dev Admin at ${at} · 3 mentors, 5 mentees`,
        ),
      ).toBeInTheDocument();
    });

    it("names the starter by ID when the name did not resolve or is blank", async () => {
      for (const triggeredByName of [null, ""]) {
        getMatchingRun.mockResolvedValue({ data: runOf({ triggeredByName }) });
        const { unmount } = renderPage();

        expect(
          await screen.findByText(/started by ID 5845 at/),
        ).toBeInTheDocument();
        unmount();
      }
    });
  });

  describe("flag off", () => {
    it("says matching is not available and asks the API nothing about it", async () => {
      useFeatureFlags.mockReturnValue({
        [FEATURE_FLAGS.MATCHING_RUN]: false,
      });
      renderPage();

      expect(
        await screen.findByText("Matching — Fall 2026"),
      ).toBeInTheDocument();
      expect(
        screen.getByText("Matching runs are not available."),
      ).toBeInTheDocument();
      expect(
        screen.getByRole("link", { name: "Participants" }),
      ).toBeInTheDocument();
      expect(getMatchingRun).not.toHaveBeenCalled();
      expect(getMatchingResults).not.toHaveBeenCalled();
      expect(screen.queryByText(/^Run \d/)).not.toBeInTheDocument();
    });
  });

  describe("by status", () => {
    it("never run", async () => {
      renderPage();

      expect(
        await screen.findByText("No matching run for Fall 2026 yet."),
      ).toBeInTheDocument();
      expect(screen.getByText("Not run")).toBeInTheDocument();
      expect(screen.queryByText(/^Run \d/)).not.toBeInTheDocument();
      expect(getMatchingResults).not.toHaveBeenCalled();
    });

    it("running", async () => {
      getMatchingRun.mockResolvedValue({ data: runOf() });
      renderPage();

      expect(
        await screen.findByText(
          "Running. No other run can start in this round until it finishes; you will get an email when it does.",
        ),
      ).toBeInTheDocument();
      expect(screen.getByText("Running")).toBeInTheDocument();
      expect(getMatchingResults).not.toHaveBeenCalled();
    });

    it.each([
      ["failed", "Failed"],
      ["unusable", "Unusable"],
    ])("%s shows the badge and the error", async (status, badge) => {
      getMatchingRun.mockResolvedValue({
        data: runOf({ status, error: "Matcher exited with code 2" }),
      });
      renderPage();

      expect(
        await screen.findByText("Matcher exited with code 2"),
      ).toBeInTheDocument();
      expect(screen.getByText(badge)).toBeInTheDocument();
      expect(getMatchingResults).not.toHaveBeenCalled();
    });

    it("succeeded goes straight to the tabs, with no summary line", async () => {
      getMatchingRun.mockResolvedValue({ data: succeededRun() });
      renderPage();

      expect(
        await screen.findByRole("tab", { name: "Matched (2)" }),
      ).toBeInTheDocument();
      expect(screen.getByText("Succeeded")).toBeInTheDocument();
      expect(screen.queryByText(/mentees matched/)).not.toBeInTheDocument();
      expect(
        screen.queryByText(/Mentors without a mentee/),
      ).not.toBeInTheDocument();
    });

    it("has no Published badge, whatever the payload carries", async () => {
      getMatchingRun.mockResolvedValue({
        data: succeededRun({ published: true }),
      });
      renderPage();

      expect(await screen.findByText("Succeeded")).toBeInTheDocument();
      expect(screen.queryByText("Published")).not.toBeInTheDocument();
    });

    it("gives a reader nothing to edit or publish", async () => {
      getMatchingRun.mockResolvedValue({ data: succeededRun() });
      renderPage();
      await screen.findByText("Cara Wang");

      expect(
        screen.queryByRole("button", { name: /^edit$|save|publish/i }),
      ).not.toBeInTheDocument();
      expect(screen.queryByRole("textbox")).not.toBeInTheDocument();
    });
  });

  describe("tabs and paging", () => {
    beforeEach(() => {
      getMatchingRun.mockResolvedValue({ data: succeededRun() });
    });

    it("counts both tabs and opens on Matched", async () => {
      renderPage();

      expect(
        await screen.findByRole("tab", { name: "Matched (2)" }),
      ).toHaveAttribute("aria-selected", "true");
      // One unmatched mentee and two mentors without a mentee.
      expect(
        screen.getByRole("tab", { name: "Unmatched (3)" }),
      ).toBeInTheDocument();
      expect(screen.queryByRole("tab", { name: /^All/ })).toBeNull();
      await waitFor(() =>
        expect(getMatchingResults).toHaveBeenCalledWith("7", {
          limit: 20,
          offset: 0,
          matched: true,
        }),
      );
      expect(getMatchingUnmatched).not.toHaveBeenCalled();
    });

    it("keeps the backend's order", async () => {
      renderPage();
      await screen.findByText("Cara Wang");

      const rows = screen
        .getAllByRole("listitem")
        .filter((li) => li.querySelector("button[aria-expanded]"));
      expect(rows.map((li) => li.textContent)).toEqual([
        expect.stringContaining("Cara Wang"),
        expect.stringContaining("Eve Zhou"),
      ]);
    });

    it("Unmatched goes in the URL and asks for its people from the first page", async () => {
      renderPage({ search: "?offset=20" });
      await screen.findByText("Cara Wang");

      await userEvent.click(screen.getByRole("tab", { name: "Unmatched (3)" }));

      await waitFor(() => expect(urlParams().get("tab")).toBe("unmatched"));
      expect(urlParams().has("offset")).toBe(false);
      await waitFor(() =>
        expect(getMatchingUnmatched).toHaveBeenCalledWith("7", {
          limit: 20,
          offset: 0,
        }),
      );
      expect(await screen.findByText("Bob Liu")).toBeInTheDocument();
    });

    it("going back to Matched drops the tab from the URL", async () => {
      renderPage({ search: "?tab=unmatched" });
      await screen.findByText("Bob Liu");

      await userEvent.click(screen.getByRole("tab", { name: "Matched (2)" }));

      await waitFor(() => expect(urlParams().has("tab")).toBe(false));
      expect(await screen.findByText("Cara Wang")).toBeInTheDocument();
    });

    it("reads the tab and page from the URL", async () => {
      renderPage({ search: "?tab=unmatched&offset=20" });

      expect(
        await screen.findByRole("tab", { name: "Unmatched (3)" }),
      ).toHaveAttribute("aria-selected", "true");
      await waitFor(() =>
        expect(getMatchingUnmatched).toHaveBeenCalledWith("7", {
          limit: 20,
          offset: 20,
        }),
      );
      expect(getMatchingResults).not.toHaveBeenCalled();
    });

    it("pages through the Matched tab with Prev and Next", async () => {
      getMatchingResults.mockResolvedValue(
        resultsPage([scoredItem], { total: 45 }),
      );
      renderPage();
      await screen.findByText("Cara Wang");

      expect(screen.getByText("1–20 of 45")).toBeInTheDocument();
      expect(screen.getByRole("button", { name: "Prev" })).toBeDisabled();

      await userEvent.click(screen.getByRole("button", { name: "Next" }));

      await waitFor(() => expect(urlParams().get("offset")).toBe("20"));
      await waitFor(() =>
        expect(getMatchingResults).toHaveBeenLastCalledWith("7", {
          limit: 20,
          offset: 20,
          matched: true,
        }),
      );
      expect(await screen.findByText("21–40 of 45")).toBeInTheDocument();
      expect(screen.getByRole("button", { name: "Prev" })).toBeEnabled();
    });

    it("stops Next on the last page", async () => {
      getMatchingResults.mockResolvedValue(
        resultsPage([scoredItem], { total: 45 }),
      );
      renderPage({ search: "?offset=40" });

      expect(await screen.findByText("41–45 of 45")).toBeInTheDocument();
      expect(screen.getByRole("button", { name: "Next" })).toBeDisabled();
    });

    it("pages through the Unmatched tab, keeping the tab", async () => {
      getMatchingUnmatched.mockResolvedValue(
        unmatchedPage([unmatchedMentor], { total: 25 }),
      );
      renderPage({ search: "?tab=unmatched" });
      await screen.findByText("Bob Liu");
      expect(screen.getByText("1–20 of 25")).toBeInTheDocument();

      await userEvent.click(screen.getByRole("button", { name: "Next" }));

      await waitFor(() => expect(urlParams().get("offset")).toBe("20"));
      expect(urlParams().get("tab")).toBe("unmatched");
      await waitFor(() =>
        expect(getMatchingUnmatched).toHaveBeenLastCalledWith("7", {
          limit: 20,
          offset: 20,
        }),
      );
      expect(await screen.findByText("21–25 of 25")).toBeInTheDocument();
      expect(screen.getByRole("button", { name: "Next" })).toBeDisabled();
    });
  });

  describe("matched rows", () => {
    beforeEach(() => {
      getMatchingRun.mockResolvedValue({ data: succeededRun() });
    });

    it("sums up each pair on one line", async () => {
      renderPage();
      await screen.findByText("Cara Wang");

      const scored = within(rowOf("Cara Wang"));
      expect(scored.getByText("ID 201")).toBeInTheDocument();
      expect(scored.getByText("Ann Lee")).toBeInTheDocument();
      expect(scored.getByText("ID 101")).toBeInTheDocument();
      expect(scored.getByText("Scored")).toBeInTheDocument();
      expect(scored.getByText("0.87")).toBeInTheDocument();
      expect(
        scored.getByText("Both work in fintech and share a timezone overlap."),
      ).toHaveClass("truncate");

      const mutual = within(rowOf("Eve Zhou"));
      expect(mutual.getByText("Both asked")).toBeInTheDocument();
      expect(mutual.getByText("—")).toBeInTheDocument();
    });

    it("opens a row's detail with the reasons and other candidates", async () => {
      renderPage();
      await screen.findByText("Cara Wang");
      expect(screen.queryByText("Reason shown to the pair")).toBeNull();

      await toggleRow("Cara Wang");

      const row = within(rowOf("Cara Wang"));
      expect(row.getAllByRole("button")[0]).toHaveAttribute(
        "aria-expanded",
        "true",
      );
      expect(row.getByText("Reason shown to the pair")).toBeInTheDocument();
      expect(
        row.getAllByText("Both work in fintech and share a timezone overlap."),
      ).toHaveLength(2);
      expect(row.getByText("Matcher's notes")).toBeInTheDocument();
      expect(
        row.getByText("Second-best total cost was 0.4 higher."),
      ).toBeInTheDocument();
      expect(row.getByText("Dan Ma (ID 102) · 0.91")).toBeInTheDocument();
      expect(row.getByText("ID 103 · 0.5")).toBeInTheDocument();
      expect(row.getByText(CANDIDATES_NOTE)).toBeInTheDocument();

      await toggleRow("Cara Wang");
      expect(row.queryByText("Reason shown to the pair")).toBeNull();
    });

    it("keeps several rows open at once and fills empty parts", async () => {
      renderPage();
      await screen.findByText("Cara Wang");

      await toggleRow("Cara Wang");
      await toggleRow("Eve Zhou");

      expect(
        within(rowOf("Cara Wang")).getByText("Reason shown to the pair"),
      ).toBeInTheDocument();
      const mutual = within(rowOf("Eve Zhou"));
      expect(mutual.getByText("No notes.")).toBeInTheDocument();
      expect(mutual.getByText("No other candidates.")).toBeInTheDocument();
      expect(mutual.queryByText(CANDIDATES_NOTE)).toBeNull();
      expect(mutual.getAllByText("No profile on file.")).toHaveLength(2);
    });
  });

  describe("unmatched rows", () => {
    beforeEach(() => {
      getMatchingRun.mockResolvedValue({ data: succeededRun() });
    });

    const renderUnmatched = async () => {
      renderPage({ search: "?tab=unmatched" });
      await screen.findByText("Bob Liu");
    };

    it("lists one row per person, mentees first, with role and what they lack", async () => {
      await renderUnmatched();

      const rows = screen
        .getAllByRole("listitem")
        .filter((li) => li.querySelector("button[aria-expanded]"));
      expect(rows.map((li) => li.textContent)).toEqual([
        expect.stringContaining("ID 203"),
        expect.stringContaining("Gus Ho"),
        expect.stringContaining("Bob Liu"),
      ]);

      const mentee = within(rowOf("ID 203"));
      expect(mentee.getByText("Mentee")).toBeInTheDocument();
      expect(mentee.getByText("No mentor")).toBeInTheDocument();

      const mentor = within(rowOf("Bob Liu"));
      expect(mentor.getByText("ID 3102")).toBeInTheDocument();
      expect(mentor.getByText("Mentor")).toBeInTheDocument();
      expect(mentor.getByText("No mentee")).toBeInTheDocument();
    });

    it("opens a mentee's profile, notes and other candidates", async () => {
      await renderUnmatched();

      await toggleRow("ID 203");

      const row = within(rowOf("ID 203"));
      expect(
        row.getByRole("region", { name: "Mentee profile" }),
      ).toHaveTextContent("No profile on file.");
      expect(row.queryByRole("region", { name: "Mentor profile" })).toBeNull();
      expect(row.getByText("No mentor had a free slot.")).toBeInTheDocument();
      expect(row.getByText("Dan Ma (ID 102) · 0.4")).toBeInTheDocument();
      expect(row.getByText(CANDIDATES_NOTE)).toBeInTheDocument();
      expect(row.queryByText("Reason shown to the pair")).toBeNull();
    });

    it("fills a mentee's empty notes and candidates", async () => {
      await renderUnmatched();

      await toggleRow("Gus Ho");

      const row = within(rowOf("Gus Ho"));
      expect(row.getByText("No notes.")).toBeInTheDocument();
      expect(row.getByText("No other candidates.")).toBeInTheDocument();
    });

    it("opens a mentor to their profile card alone", async () => {
      await renderUnmatched();

      await toggleRow("Bob Liu");

      const row = within(rowOf("Bob Liu"));
      const profile = within(
        row.getByRole("region", { name: "Mentor profile" }),
      );
      expect(profile.getByText("Slots this run: 2")).toBeInTheDocument();
      expect(row.queryByText("Matcher's notes")).toBeNull();
      expect(row.queryByText("Other candidates")).toBeNull();
    });
  });

  describe("profile cards", () => {
    beforeEach(() => {
      getMatchingRun.mockResolvedValue({ data: succeededRun() });
    });

    const openProfiles = async () => {
      renderPage();
      await screen.findByText("Cara Wang");
      await toggleRow("Cara Wang");
      return {
        mentee: within(screen.getByRole("region", { name: "Mentee profile" })),
        mentor: within(screen.getByRole("region", { name: "Mentor profile" })),
      };
    };

    it("shows the mentee's history, goal, background, survey and wishes", async () => {
      const { mentee } = await openProfiles();

      expect(mentee.getByText("Mentee")).toBeInTheDocument();
      expect(mentee.getByText("Asia/Shanghai")).toBeInTheDocument();
      expect(
        mentee.getByText("Rounds taken part: 2 (with meetings: 1)"),
      ).toBeInTheDocument();
      expect(mentee.getByText("Land a first SWE job")).toBeInTheDocument();
      expect(
        mentee.getByText("Analyst at Acme, 2024-07-01–present"),
      ).toBeInTheDocument();
      expect(
        mentee.getByText(
          "MS, Computer Science, State University, 2022-09-01–2024-06-01",
        ),
      ).toBeInTheDocument();
      expect(
        mentee.getByText("Transition: Via a CS master's"),
      ).toBeInTheDocument();
      expect(mentee.getByText("Urgency: Within 6 months")).toBeInTheDocument();
      expect(
        mentee.getByText("Job market: Canada (Toronto only)"),
      ).toBeInTheDocument();
      expect(mentee.getByText("Stage: Job searching")).toBeInTheDocument();
      expect(
        mentee.getByText("Industry: Software engineering, Product management"),
      ).toBeInTheDocument();
      expect(
        mentee.getByText("Skills: Resume guidance, Technical skills"),
      ).toBeInTheDocument();
      expect(mentee.getByText("Wants: Ann Lee (ID 101)")).toBeInTheDocument();
      expect(mentee.queryByText(/Does not want/)).toBeNull();
      expect(mentee.queryByText(/Slots this run/)).toBeNull();
    });

    it("shows the mentor's survey and leaves out what is empty", async () => {
      const { mentor } = await openProfiles();

      expect(mentor.getByText("Mentor")).toBeInTheDocument();
      expect(mentor.getByText("America/New_York")).toBeInTheDocument();
      expect(
        mentor.getByText("Rounds taken part: 0 (with meetings: 0)"),
      ).toBeInTheDocument();
      expect(
        mentor.getByText("Staff Engineer at Globex, 2015-01-01–2023-12-31"),
      ).toBeInTheDocument();
      expect(
        mentor.getByText("Career transition: No CS background (Physics PhD)"),
      ).toBeInTheDocument();
      expect(mentor.getByText("Development region: US")).toBeInTheDocument();
      expect(mentor.getByText("Mentoring elsewhere: 1–3")).toBeInTheDocument();
      expect(mentor.getByText("Slots this run: 2")).toBeInTheDocument();
      expect(
        mentor.getByText("Skills: Career path guidance"),
      ).toBeInTheDocument();
      expect(mentor.getByText("Does not want: ID 205")).toBeInTheDocument();
      expect(mentor.queryByText("Goal")).toBeNull();
      expect(mentor.queryByText("Education")).toBeNull();
      expect(mentor.queryByText(/^Wants:/)).toBeNull();
      expect(mentor.queryByText(/Urgency|Industry/)).toBeNull();
    });
  });
});
