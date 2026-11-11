import { describe, test, expect, beforeEach, afterEach, vi } from "vitest";
import {
  render,
  screen,
  cleanup,
  waitFor,
  within,
  act,
} from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter, Routes, Route } from "react-router-dom";
import "@testing-library/jest-dom/vitest";

import Header from "@/components/layout/Header";
import { WhatsNewProvider } from "@/whatsNew/WhatsNewProvider";
import { FlagsContext } from "@/context/flags";
import { listGuideProgress, recordGuideProgress } from "@/api/guidesApi";
import { useAuth } from "@/context/auth";

vi.mock("@/api/guidesApi", () => ({
  listGuideProgress: vi.fn(),
  recordGuideProgress: vi.fn(),
}));

vi.mock("@/context/auth", () => ({
  useAuth: vi.fn(),
}));

vi.mock("@/utils/auth", () => ({
  getCookie: vi.fn(() => null),
  extractCloudflareUserName: vi.fn(() => ""),
  extractCloudflareUserPicture: vi.fn(() => null),
  performGlobalLogout: vi.fn(),
}));

vi.mock("@/components/layout/NotificationBell", () => ({
  default: () => <div data-testid="notification-bell" />,
}));

const SIGNED_IN = {
  loading: false,
  hasVerifiedEmail: true,
  accessDenied: false,
  authError: false,
  permissions: ["beta.read"],
};

// Four entries with distinct routes and anchors. Delta needs a permission the
// viewer lacks; gamma needs a flag that is on.
const ENTRIES = [
  {
    id: "delta-feature",
    date: "2026-11-09",
    title: "Delta title",
    body: "Delta body.",
    showMe: { route: "/delta", anchor: "delta-anchor" },
    audience: ({ permissions }) => permissions.includes("delta.write"),
  },
  {
    id: "gamma-feature",
    date: "2026-11-08",
    title: "Gamma title",
    body: "Gamma body.",
    showMe: { route: "/gamma", anchor: "gamma-anchor" },
    flag: "gamma-flag",
  },
  {
    id: "beta-feature",
    date: "2026-10-03",
    title: "Beta title",
    body: "Beta body.",
    showMe: { route: "/beta", anchor: "beta-anchor" },
    audience: ({ permissions }) => permissions.includes("beta.read"),
  },
  {
    id: "alpha-feature",
    date: "2026-07-18",
    title: "Alpha title",
    body: "Alpha body.",
    showMe: { route: "/alpha", anchor: "alpha-anchor" },
  },
];

// Shaped like the unwrapped `data` of GET /guides/progress.
const row = (guideKey, status, snoozeCount, updatedAt) => ({
  guideKey,
  status,
  snoozeCount,
  updatedAt,
});
const INTRO_DONE = row(
  "whats-new-intro",
  "completed",
  0,
  "2026-11-01T08:00:00Z",
);
const ALPHA_COMPLETED = row(
  "whats-new-alpha-feature",
  "completed",
  0,
  "2026-11-02T09:00:00Z",
);
const BETA_DISMISSED = row(
  "whats-new-beta-feature",
  "dismissed",
  0,
  "2026-11-03T10:00:00Z",
);
// A guide row unrelated to What's new must not count for anything.
const OTHER_GUIDE = row("welcome", "snoozed", 2, "2026-11-04T11:00:00Z");

const FLAGS_ON = {
  flags: { "whats-new": true, "gamma-flag": true },
  ready: true,
};

const renderApp = ({ flagState = FLAGS_ON, entries = ENTRIES } = {}) =>
  render(
    <FlagsContext.Provider
      value={{ ...flagState, setFlags: () => {}, setReady: () => {} }}
    >
      <MemoryRouter initialEntries={["/home"]}>
        <WhatsNewProvider entries={entries}>
          <Header />
          <Routes>
            <Route path="/home" element={<p>Home page</p>} />
            <Route
              path="/beta"
              element={
                <div>
                  <p>Beta page</p>
                  <button data-whats-new="beta-anchor">Beta target</button>
                </div>
              }
            />
            <Route path="/gamma" element={<p>Gamma page</p>} />
          </Routes>
        </WhatsNewProvider>
      </MemoryRouter>
    </FlagsContext.Provider>,
  );

const settle = async () => {
  await waitFor(() => expect(listGuideProgress).toHaveBeenCalled());
  await act(async () => {});
};

const openMenu = async (user) => {
  await user.click(screen.getByRole("button", { name: /^User menu/ }));
  await screen.findByRole("menuitem", { name: "Log out" });
};

const openPanel = async (user) => {
  await openMenu(user);
  await user.click(screen.getByRole("menuitem", { name: /^What's new/ }));
  return screen.findByRole("dialog", { name: "What's new" });
};

describe("WhatsNewProvider with the Header", () => {
  beforeEach(() => {
    useAuth.mockReturnValue(SIGNED_IN);
    recordGuideProgress.mockImplementation(async (guideKey, status) =>
      row(guideKey, status, 0, "2026-11-11T00:00:00Z"),
    );
  });

  afterEach(() => {
    cleanup();
    vi.resetAllMocks();
    vi.restoreAllMocks();
  });

  test("renders nothing and fetches nothing when the flag is off", async () => {
    listGuideProgress.mockResolvedValue([]);
    const user = userEvent.setup();
    renderApp({
      flagState: { flags: { "gamma-flag": true }, ready: true },
    });

    await act(async () => {});
    expect(listGuideProgress).not.toHaveBeenCalled();
    expect(screen.queryByTestId("whats-new-dot")).not.toBeInTheDocument();
    expect(
      screen.queryByText(/New features and tips for Purrf/),
    ).not.toBeInTheDocument();
    await openMenu(user);
    expect(
      screen.queryByRole("menuitem", { name: /What's new/ }),
    ).not.toBeInTheDocument();
    expect(recordGuideProgress).not.toHaveBeenCalled();
  });

  test("an entry whose flag is off is neither listed nor counted", async () => {
    listGuideProgress.mockResolvedValue([
      INTRO_DONE,
      ALPHA_COMPLETED,
      BETA_DISMISSED,
    ]);
    const user = userEvent.setup();
    renderApp({ flagState: { flags: { "whats-new": true }, ready: true } });
    await settle();

    // Gamma is the only row-less entry this viewer qualifies for, but its
    // flag is off, so nothing is unread.
    expect(screen.queryByTestId("whats-new-dot")).not.toBeInTheDocument();

    const panel = await openPanel(user);
    const titles = within(panel)
      .getAllByRole("heading", { level: 3 })
      .map((h) => h.textContent);
    expect(titles).toEqual(["Beta title", "Alpha title"]);
    expect(recordGuideProgress).not.toHaveBeenCalled();
  });

  test("an entry not yet released shows without a date", async () => {
    listGuideProgress.mockResolvedValue([INTRO_DONE]);
    const user = userEvent.setup();
    renderApp({
      entries: [
        {
          id: "epsilon-feature",
          title: "Epsilon title",
          body: "Epsilon body.",
          showMe: { route: "/beta", anchor: "beta-anchor" },
        },
      ],
    });
    await settle();

    await openPanel(user);
    const item = screen.getByTestId("whats-new-entry-epsilon-feature");
    expect(within(item).getByText("Epsilon title")).toBeInTheDocument();
    expect(item.querySelector("time")).toBeNull();
  });

  test("stays off until LaunchDarkly has answered", async () => {
    listGuideProgress.mockResolvedValue([]);
    renderApp({ flagState: { flags: { "whats-new": true }, ready: false } });

    await act(async () => {});
    expect(listGuideProgress).not.toHaveBeenCalled();
  });

  test("the dot and count cover visible entries with no progress row", async () => {
    listGuideProgress.mockResolvedValue([
      INTRO_DONE,
      ALPHA_COMPLETED,
      BETA_DISMISSED,
      OTHER_GUIDE,
    ]);
    const user = userEvent.setup();
    renderApp();
    await settle();

    // Only gamma is visible and row-less; delta has no row but is hidden.
    expect(await screen.findByTestId("whats-new-dot")).toBeInTheDocument();
    const avatar = screen.getByRole("button", {
      name: "User menu, 1 unread update",
    });
    await user.click(avatar);
    const item = await screen.findByRole("menuitem", {
      name: "What's new, 1 unread update",
    });
    expect(within(item).getByText("1")).toBeInTheDocument();
  });

  test("counts every visible row-less entry, whatever its date", async () => {
    listGuideProgress.mockResolvedValue([INTRO_DONE]);
    renderApp();
    await settle();

    expect(
      await screen.findByRole("button", {
        name: "User menu, 3 unread updates",
      }),
    ).toBeInTheDocument();
  });

  test("no dot once every visible entry has a row", async () => {
    listGuideProgress.mockResolvedValue([
      INTRO_DONE,
      ALPHA_COMPLETED,
      BETA_DISMISSED,
      row("whats-new-gamma-feature", "dismissed", 0, "2026-11-05T12:00:00Z"),
    ]);
    const user = userEvent.setup();
    renderApp();
    await settle();

    expect(screen.queryByTestId("whats-new-dot")).not.toBeInTheDocument();
    expect(screen.getByRole("button", { name: "User menu" })).toBeVisible();
    await openMenu(user);
    expect(
      screen.getByRole("menuitem", { name: "What's new" }),
    ).toBeInTheDocument();
  });

  test("opening the panel lists only the audience's entries and dismisses the row-less ones", async () => {
    listGuideProgress.mockResolvedValue([
      INTRO_DONE,
      ALPHA_COMPLETED,
      BETA_DISMISSED,
    ]);
    const user = userEvent.setup();
    renderApp();
    await settle();

    const panel = await openPanel(user);

    const titles = within(panel)
      .getAllByRole("heading", { level: 3 })
      .map((h) => h.textContent);
    expect(titles).toEqual(["Gamma title", "Beta title", "Alpha title"]);
    expect(within(panel).queryByText("Delta title")).not.toBeInTheDocument();

    expect(recordGuideProgress).toHaveBeenCalledTimes(1);
    expect(recordGuideProgress).toHaveBeenCalledWith(
      "whats-new-gamma-feature",
      "dismissed",
    );

    // New until completed: gamma (no row) and beta (dismissed), not alpha.
    const isNew = (id) =>
      within(screen.getByTestId(`whats-new-entry-${id}`)).queryByText("New");
    expect(isNew("gamma-feature")).toBeInTheDocument();
    expect(isNew("beta-feature")).toBeInTheDocument();
    expect(isNew("alpha-feature")).not.toBeInTheDocument();
    expect(
      within(screen.getByTestId("whats-new-entry-alpha-feature")).getByText(
        "Jul 18, 2026",
      ),
    ).toBeInTheDocument();

    expect(screen.queryByTestId("whats-new-dot")).not.toBeInTheDocument();
  });

  test("Show me completes the entry, closes the panel, navigates and outlines the anchor", async () => {
    listGuideProgress.mockResolvedValue([INTRO_DONE, BETA_DISMISSED]);
    const user = userEvent.setup();
    renderApp();
    await settle();

    const panel = await openPanel(user);
    recordGuideProgress.mockClear();
    await user.click(
      within(panel).getByRole("button", { name: "Show me: Beta title" }),
    );

    expect(recordGuideProgress).toHaveBeenCalledTimes(1);
    expect(recordGuideProgress).toHaveBeenCalledWith(
      "whats-new-beta-feature",
      "completed",
    );
    expect(await screen.findByText("Beta page")).toBeInTheDocument();
    await waitFor(() =>
      expect(
        screen.queryByRole("dialog", { name: "What's new" }),
      ).not.toBeInTheDocument(),
    );
    await waitFor(() =>
      expect(screen.getByText("Beta target").style.outline).toBe(
        "3px solid var(--primary)",
      ),
    );

    const reopened = await openPanel(user);
    expect(
      within(
        within(reopened).getByTestId("whats-new-entry-beta-feature"),
      ).queryByText("New"),
    ).not.toBeInTheDocument();
  });

  test("a failed write is logged and the panel keeps working", async () => {
    listGuideProgress.mockResolvedValue([INTRO_DONE]);
    recordGuideProgress.mockRejectedValue(new Error("boom"));
    const consoleError = vi
      .spyOn(console, "error")
      .mockImplementation(() => {});
    const user = userEvent.setup();
    renderApp();
    await settle();

    await openPanel(user);

    await waitFor(() =>
      expect(consoleError).toHaveBeenCalledWith(
        expect.stringContaining("whats-new-alpha-feature"),
        expect.any(Error),
      ),
    );
    expect(screen.getByText("Gamma title")).toBeInTheDocument();
    expect(screen.queryByTestId("whats-new-dot")).not.toBeInTheDocument();
  });

  describe("first-login pointer", () => {
    test("shows when there is no intro row and Got it records it as completed", async () => {
      listGuideProgress.mockResolvedValue([ALPHA_COMPLETED]);
      const user = userEvent.setup();
      renderApp();

      expect(
        await screen.findByText(
          "New features and tips for Purrf show up here. Look for the dot.",
        ),
      ).toBeInTheDocument();
      await user.click(screen.getByRole("button", { name: "Got it" }));

      expect(recordGuideProgress).toHaveBeenCalledTimes(1);
      expect(recordGuideProgress).toHaveBeenCalledWith(
        "whats-new-intro",
        "completed",
      );
      await waitFor(() =>
        expect(
          screen.queryByText(/New features and tips for Purrf/),
        ).not.toBeInTheDocument(),
      );
    });

    test("does not show again once the intro row exists", async () => {
      listGuideProgress.mockResolvedValue([
        row("whats-new-intro", "completed", 0, "2026-11-01T08:00:00Z"),
      ]);
      renderApp();
      await settle();

      expect(
        screen.queryByText(/New features and tips for Purrf/),
      ).not.toBeInTheDocument();
    });

    test("Show me records the intro and opens the panel", async () => {
      listGuideProgress.mockResolvedValue([ALPHA_COMPLETED, BETA_DISMISSED]);
      const user = userEvent.setup();
      renderApp();

      await screen.findByText(/New features and tips for Purrf/);
      await user.click(screen.getByRole("button", { name: "Show me" }));

      expect(
        await screen.findByRole("dialog", { name: "What's new" }),
      ).toBeInTheDocument();
      expect(recordGuideProgress).toHaveBeenCalledWith(
        "whats-new-intro",
        "completed",
      );
      expect(recordGuideProgress).toHaveBeenCalledWith(
        "whats-new-gamma-feature",
        "dismissed",
      );
      expect(recordGuideProgress).toHaveBeenCalledTimes(2);
    });

    test("does not show while the progress fetch is still loading", async () => {
      listGuideProgress.mockReturnValue(new Promise(() => {}));
      renderApp();
      await settle();

      expect(
        screen.queryByText(/New features and tips for Purrf/),
      ).not.toBeInTheDocument();
      expect(screen.queryByTestId("whats-new-dot")).not.toBeInTheDocument();
    });
  });

  test("a failed fetch hides the dot, the pointer and the menu item", async () => {
    listGuideProgress.mockRejectedValue(new Error("offline"));
    const consoleError = vi
      .spyOn(console, "error")
      .mockImplementation(() => {});
    const user = userEvent.setup();
    renderApp();
    await settle();

    expect(consoleError).toHaveBeenCalled();
    expect(screen.queryByTestId("whats-new-dot")).not.toBeInTheDocument();
    expect(
      screen.queryByText(/New features and tips for Purrf/),
    ).not.toBeInTheDocument();
    await openMenu(user);
    expect(
      screen.queryByRole("menuitem", { name: /What's new/ }),
    ).not.toBeInTheDocument();
  });

  test("does nothing before the email is verified", async () => {
    useAuth.mockReturnValue({ ...SIGNED_IN, hasVerifiedEmail: false });
    listGuideProgress.mockResolvedValue([]);
    renderApp();

    await act(async () => {});
    expect(listGuideProgress).not.toHaveBeenCalled();
  });
});
