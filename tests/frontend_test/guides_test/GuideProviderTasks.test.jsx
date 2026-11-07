import { describe, test, expect, beforeEach, afterEach, vi } from "vitest";
import {
  render,
  screen,
  cleanup,
  waitFor,
  act,
  within,
} from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { useEffect, useState } from "react";
import {
  MemoryRouter,
  Route,
  Routes,
  useLocation,
  useNavigate,
  useParams,
} from "react-router-dom";
import "@testing-library/jest-dom/vitest";

import { GuideProvider } from "@/guides/GuideProvider";
import { FlagsContext } from "@/context/flags";
import { useGuides } from "@/guides/GuideContext";
import { resetGuideSession } from "@/guides/session";
import { listGuideProgress, recordGuideProgress } from "@/api/guidesApi";
import { listMyApplications } from "@/api/recruitingApi";
import { useAuth } from "@/context/auth";

vi.mock("@/api/guidesApi", () => ({
  listGuideProgress: vi.fn(),
  recordGuideProgress: vi.fn(),
}));

vi.mock("@/api/recruitingApi", () => ({
  listMyApplications: vi.fn(),
}));

vi.mock("@/context/auth", () => ({
  useAuth: vi.fn(),
}));

// Stands in for react-joyride so these tests check the engine's decisions,
// not the library's DOM.
vi.mock("@/guides/GuideTourRenderer", () => ({
  default: ({
    steps,
    stepIndex,
    showBack,
    isLastStep,
    showDismiss,
    onBack,
    onNext,
    onDone,
    onClose,
    onDismiss,
  }) => (
    <div data-testid="tour" data-step={stepIndex}>
      <p>{steps[stepIndex].title}</p>
      <button onClick={onClose}>Close tour</button>
      {showDismiss && <button onClick={onDismiss}>Don't show again</button>}
      {showBack && <button onClick={onBack}>Back</button>}
      {isLastStep ? (
        <button onClick={onDone}>Done</button>
      ) : (
        <button onClick={onNext}>Next</button>
      )}
    </div>
  ),
}));

const SIGNED_IN = {
  loading: false,
  hasVerifiedEmail: true,
  accessDenied: false,
  authError: false,
  permissions: [],
};

const FLAG_ON = { flags: { "onboarding-guides": true }, ready: true };

const step = (anchor, title) => ({ anchor, title, body: `${title} body` });

const BASICS = {
  key: "welcome",
  type: "tour",
  priority: 100,
  basics: true,
  audience: () => true,
  trigger: { kind: "first-visit" },
  steps: [step("basics-1", "Basics one"), step("basics-2", "Basics two")],
};

// The item segment reads its id off the home page, where the previous
// segment ran.
const ALPHA = {
  key: "task-alpha",
  type: "task",
  title: "Do alpha",
  priority: 50,
  audience: ({ mentorshipRoles }) => mentorshipRoles.includes("mentee"),
  segments: [
    {
      key: "alpha-home",
      route: "/home",
      steps: [step("home-1", "Home one"), step("home-2", "Home two")],
    },
    {
      key: "alpha-item",
      route: "/items/:itemId",
      params: () => ({
        itemId: document.querySelector('[data-tour="home-2"]')?.dataset.itemId,
      }),
      steps: [step("item-1", "Item one")],
    },
  ],
};

const GAMMA = {
  key: "task-gamma",
  type: "task",
  title: "Do gamma",
  priority: 40,
  audience: () => true,
  segments: [
    {
      key: "gamma-page",
      route: "/gamma",
      steps: [step("gamma-1", "Gamma one"), step("gamma-2", "Gamma two")],
    },
  ],
};

const ItemPage = () => {
  const { itemId } = useParams();
  return <span data-tour="item-1">item {itemId}</span>;
};

// Renders its anchor only once the button is clicked, as a page that is
// still loading would.
const Reveal = ({ anchor }) => {
  const [shown, setShown] = useState(false);
  return shown ? (
    <span data-tour={anchor}>{anchor}</span>
  ) : (
    <button onClick={() => setShown(true)}>Reveal {anchor}</button>
  );
};

const Late = ({ anchor }) => {
  const [shown, setShown] = useState(false);
  useEffect(() => {
    const timer = setTimeout(() => setShown(true), 30);
    return () => clearTimeout(timer);
  }, []);
  return shown ? <span data-tour={anchor}>{anchor}</span> : null;
};

const HOME = (
  <>
    <span data-tour="home-1">home one</span>
    <span data-tour="home-2" data-item-id="42">
      home two
    </span>
  </>
);

const DEFAULT_PAGES = {
  "/start": <span>start page</span>,
  "/home": HOME,
  "/items/:itemId": <ItemPage />,
  "/gamma": (
    <>
      <span data-tour="gamma-1">g1</span>
      <span data-tour="gamma-2">g2</span>
    </>
  ),
  "/elsewhere": <span>elsewhere page</span>,
};

const Controls = () => {
  const navigate = useNavigate();
  const { pathname } = useLocation();
  const { start } = useGuides();
  return (
    <>
      <output data-testid="path">{pathname}</output>
      {["/start", "/home", "/elsewhere"].map((path) => (
        <button key={path} onClick={() => navigate(path)}>
          Go {path}
        </button>
      ))}
      <button onClick={() => start("welcome")}>Replay</button>
      <button onClick={() => start("task-solo")}>Start solo</button>
    </>
  );
};

const renderTasks = ({
  guides = [BASICS, ALPHA],
  pages = {},
  at = "/start",
  anchorTimeoutMs = 100,
} = {}) =>
  render(
    <FlagsContext.Provider
      value={{ ...FLAG_ON, setFlags: () => {}, setReady: () => {} }}
    >
      <MemoryRouter initialEntries={[at]}>
        <GuideProvider guides={guides} anchorTimeoutMs={anchorTimeoutMs}>
          <span data-tour="basics-1">b1</span>
          <span data-tour="basics-2">b2</span>
          <Routes>
            {Object.entries({ ...DEFAULT_PAGES, ...pages }).map(
              ([path, element]) => (
                <Route key={path} path={path} element={element} />
              ),
            )}
          </Routes>
          <Controls />
        </GuideProvider>
      </MemoryRouter>
    </FlagsContext.Provider>,
  );

const rolesResponse = (mentorshipRoles) => ({
  success: true,
  data: { applications: [], mentorshipRoles },
});

const click = (name) => userEvent.click(screen.getByRole("button", { name }));

// Long enough for any anchor wait (100ms here) to run out.
const pause = () =>
  act(() => new Promise((resolve) => setTimeout(resolve, 250)));

const settle = async () => {
  await waitFor(() => expect(listGuideProgress).toHaveBeenCalled());
  await waitFor(() => expect(listMyApplications).toHaveBeenCalled());
  await pause();
};

const finishBasics = async () => {
  await screen.findByText("Basics one");
  await click("Next");
  await screen.findByText("Basics two");
  await click("Done");
};

const path = () => screen.getByTestId("path").textContent;

describe("GuideProvider tasks", () => {
  beforeEach(() => {
    resetGuideSession();
    useAuth.mockReturnValue(SIGNED_IN);
    recordGuideProgress.mockResolvedValue({});
    listGuideProgress.mockResolvedValue([]);
    listMyApplications.mockResolvedValue(rolesResponse(["mentee"]));
  });

  afterEach(() => {
    cleanup();
    vi.resetAllMocks();
    vi.restoreAllMocks();
  });

  describe("after the basics tour", () => {
    test("walks the one qualifying task across its pages", async () => {
      renderTasks();
      await finishBasics();

      expect(await screen.findByText("Home one")).toBeInTheDocument();
      expect(path()).toBe("/home");
      expect(
        screen.queryByRole("button", { name: "Back" }),
      ).not.toBeInTheDocument();
      await click("Next");
      await screen.findByText("Home two");
      // The item segment can still run, so this is not the end.
      await click("Next");

      expect(await screen.findByText("Item one")).toBeInTheDocument();
      expect(path()).toBe("/items/42");
      expect(screen.getByText("item 42")).toBeInTheDocument();
      await click("Done");

      // The engine's own navigation did not end the task as a snooze.
      expect(recordGuideProgress.mock.calls).toEqual([
        ["welcome", "completed"],
        ["task-alpha", "completed"],
      ]);
      expect(screen.queryByTestId("tour")).not.toBeInTheDocument();
    });

    test("skips a segment whose params cannot be resolved", async () => {
      renderTasks({
        pages: {
          "/home": (
            <>
              <span data-tour="home-1">h1</span>
              <span data-tour="home-2">h2 without an id</span>
            </>
          ),
        },
      });
      await finishBasics();
      await screen.findByText("Home one");
      await click("Next");
      await screen.findByText("Home two");

      await click("Done");

      expect(path()).toBe("/home");
      expect(recordGuideProgress).toHaveBeenLastCalledWith(
        "task-alpha",
        "completed",
      );
    });

    test("waits for a segment's anchors to render", async () => {
      renderTasks({
        pages: {
          "/home": (
            <>
              <Late anchor="home-1" />
              <Late anchor="home-2" />
            </>
          ),
        },
      });
      await finishBasics();

      expect(await screen.findByText("Home one")).toBeInTheDocument();
    });

    test("skips a segment whose anchors never render", async () => {
      const guides = [
        BASICS,
        {
          ...ALPHA,
          segments: [
            {
              key: "alpha-empty",
              route: "/elsewhere",
              steps: [step("never", "Never shown")],
            },
            ALPHA.segments[0],
          ],
        },
      ];
      renderTasks({ guides });
      await finishBasics();

      expect(await screen.findByText("Home one")).toBeInTheDocument();
      expect(path()).toBe("/home");
      expect(screen.queryByText("Never shown")).not.toBeInTheDocument();
    });

    test("a route change the viewer makes ends the task as snoozed", async () => {
      renderTasks();
      await finishBasics();
      await screen.findByText("Home one");

      await click("Go /elsewhere");

      await waitFor(() =>
        expect(screen.queryByTestId("tour")).not.toBeInTheDocument(),
      );
      expect(recordGuideProgress).toHaveBeenLastCalledWith(
        "task-alpha",
        "snoozed",
      );
    });

    test("just ends for a viewer no task is for", async () => {
      listMyApplications.mockResolvedValue(rolesResponse([]));
      renderTasks();
      await finishBasics();
      await pause();

      expect(screen.queryByTestId("tour")).not.toBeInTheDocument();
      expect(path()).toBe("/start");
      expect(recordGuideProgress.mock.calls).toEqual([
        ["welcome", "completed"],
      ]);
    });

    test("judges audiences on the viewer's mentorship roles", async () => {
      const audience = vi.fn(() => false);
      listMyApplications.mockResolvedValue(rolesResponse(["mentor"]));
      renderTasks({ guides: [BASICS, { ...ALPHA, audience }] });
      await finishBasics();

      expect(audience).toHaveBeenCalledWith({
        permissions: [],
        flags: { "onboarding-guides": true },
        mentorshipRoles: ["mentor"],
      });
    });

    test("counts a failed roles fetch as no roles", async () => {
      listMyApplications.mockRejectedValue(new Error("down"));
      renderTasks();
      await finishBasics();
      await pause();

      expect(screen.queryByTestId("tour")).not.toBeInTheDocument();
      expect(path()).toBe("/start");
    });

    test("offers a chooser when several tasks qualify", async () => {
      renderTasks({ guides: [BASICS, ALPHA, GAMMA] });
      await finishBasics();

      const dialog = await screen.findByRole("dialog", {
        name: "What would you like to do?",
      });
      expect(
        within(dialog)
          .getAllByRole("button")
          .map((button) => button.textContent),
      ).toEqual(["Do alpha", "Do gamma", "I'll explore on my own", "Close"]);
      await userEvent.click(
        within(dialog).getByRole("button", { name: "Do gamma" }),
      );

      expect(await screen.findByText("Gamma one")).toBeInTheDocument();
      expect(path()).toBe("/gamma");
      await click("Next");
      await screen.findByText("Gamma two");
      await click("Done");

      // Back to the chooser, with the finished task checked off.
      const again = await screen.findByRole("dialog");
      expect(
        within(again).getByRole("button", { name: "Do gamma (completed)" }),
      ).toBeInTheDocument();
      expect(
        within(again).getByRole("button", { name: "Do alpha" }),
      ).toBeInTheDocument();
      await userEvent.click(
        within(again).getByRole("button", { name: "I'll explore on my own" }),
      );

      await waitFor(() =>
        expect(screen.queryByRole("dialog")).not.toBeInTheDocument(),
      );
      expect(recordGuideProgress.mock.calls).toEqual([
        ["welcome", "completed"],
        ["task-gamma", "completed"],
      ]);
    });

    test("does not return to the chooser after a task is closed", async () => {
      renderTasks({ guides: [BASICS, ALPHA, GAMMA] });
      await finishBasics();
      const dialog = await screen.findByRole("dialog");
      await userEvent.click(
        within(dialog).getByRole("button", { name: "Do gamma" }),
      );
      await screen.findByText("Gamma one");

      await click("Close tour");
      await pause();

      expect(screen.queryByRole("dialog")).not.toBeInTheDocument();
      expect(recordGuideProgress).toHaveBeenLastCalledWith(
        "task-gamma",
        "snoozed",
      );
    });

    test("does not follow a basics tour that was closed", async () => {
      renderTasks();
      await screen.findByText("Basics one");

      await click("Close tour");
      await pause();

      expect(screen.queryByTestId("tour")).not.toBeInTheDocument();
      expect(path()).toBe("/start");
    });
  });

  describe("page intros", () => {
    beforeEach(() => {
      listGuideProgress.mockResolvedValue([
        { guideKey: "welcome", status: "completed", snoozeCount: 0 },
      ]);
    });

    test("show a task's segment alone on a page the viewer opens", async () => {
      renderTasks();
      await settle();

      await click("Go /home");

      expect(await screen.findByText("Home one")).toBeInTheDocument();
      expect(
        screen.getByRole("button", { name: "Don't show again" }),
      ).toBeInTheDocument();
      await click("Next");
      await screen.findByText("Home two");
      // Only this page's segment: the item page is not part of the intro.
      await click("Done");

      expect(path()).toBe("/home");
      expect(recordGuideProgress.mock.calls).toEqual([
        ["page-alpha-home", "completed"],
      ]);
    });

    test.each([
      ["snoozed", true],
      ["completed", false],
      ["dismissed", false],
    ])("with a %s row shows: %s", async (status, shown) => {
      listGuideProgress.mockResolvedValue([
        { guideKey: "welcome", status: "completed", snoozeCount: 0 },
        { guideKey: "page-alpha-home", status, snoozeCount: 1 },
      ]);
      renderTasks({ at: "/home" });
      await settle();

      expect(screen.queryByText("Home one") !== null).toBe(shown);
    });

    test("do not show once the task is completed", async () => {
      listGuideProgress.mockResolvedValue([
        { guideKey: "welcome", status: "completed", snoozeCount: 0 },
        { guideKey: "task-alpha", status: "completed", snoozeCount: 0 },
      ]);
      renderTasks({ at: "/home" });
      await settle();

      expect(screen.queryByTestId("tour")).not.toBeInTheDocument();
    });

    test("need two visible steps and write nothing otherwise", async () => {
      renderTasks({
        at: "/home",
        pages: { "/home": <span data-tour="home-1">only one</span> },
      });
      await settle();

      expect(screen.queryByTestId("tour")).not.toBeInTheDocument();
      expect(recordGuideProgress).not.toHaveBeenCalled();
    });

    test("count variants of one step once", async () => {
      const guides = [
        {
          ...ALPHA,
          segments: [
            {
              key: "alpha-home",
              route: "/home",
              steps: [
                { ...step("variant-a", "Variant A"), alternative: "v" },
                { ...step("variant-b", "Variant B"), alternative: "v" },
                step("home-2", "Home two"),
              ],
            },
          ],
        },
      ];
      renderTasks({
        guides,
        at: "/home",
        pages: {
          "/home": (
            <>
              <span data-tour="variant-a">a</span>
              <span data-tour="variant-b">b</span>
              <span data-tour="home-2">h2</span>
            </>
          ),
        },
      });

      expect(await screen.findByText("Variant A")).toBeInTheDocument();
      await click("Next");

      expect(await screen.findByText("Home two")).toBeInTheDocument();
      expect(screen.queryByText("Variant B")).not.toBeInTheDocument();
    });

    test("show at most once per session", async () => {
      renderTasks();
      await settle();
      await click("Go /home");
      await screen.findByText("Home one");
      await click("Close tour");

      await click("Go /start");
      await click("Go /home");
      await pause();

      expect(screen.queryByTestId("tour")).not.toBeInTheDocument();
      expect(recordGuideProgress.mock.calls).toEqual([
        ["page-alpha-home", "snoozed"],
      ]);
    });

    test("show again after a replay of the basics tour", async () => {
      listGuideProgress.mockResolvedValue([
        { guideKey: "welcome", status: "completed", snoozeCount: 0 },
        {
          guideKey: "page-alpha-home",
          status: "completed",
          snoozeCount: 0,
          updatedAt: "2026-11-01T10:00:00Z",
        },
      ]);
      listMyApplications.mockResolvedValue(rolesResponse([]));
      const guides = [BASICS, { ...ALPHA, audience: () => true }];
      renderTasks({ guides });
      await settle();
      await click("Go /home");
      await pause();
      expect(screen.queryByTestId("tour")).not.toBeInTheDocument();

      await click("Replay");
      await screen.findByText("Basics one");
      expect(recordGuideProgress).toHaveBeenCalledWith(
        "tour-reset",
        "completed",
      );
      await click("Close tour");
      await click("Go /start");
      await click("Go /home");

      expect(await screen.findByText("Home one")).toBeInTheDocument();
    });

    test.each([
      ["older than", true, "2026-11-01T10:00:00Z"],
      ["newer than", false, "2026-11-03T10:00:00Z"],
    ])(
      "with a row %s the last reset show: %s",
      async (_label, shown, updatedAt) => {
        listGuideProgress.mockResolvedValue([
          { guideKey: "welcome", status: "completed", snoozeCount: 0 },
          {
            guideKey: "tour-reset",
            status: "completed",
            snoozeCount: 0,
            updatedAt: "2026-11-02T10:00:00Z",
          },
          {
            guideKey: "page-alpha-home",
            status: "completed",
            snoozeCount: 0,
            updatedAt,
          },
        ]);
        renderTasks({ at: "/home" });
        await settle();

        expect(screen.queryByText("Home one") !== null).toBe(shown);
      },
    );
  });

  describe("pacing", () => {
    test("waits for a page change before the next guide", async () => {
      listGuideProgress.mockResolvedValue([]);
      renderTasks({ at: "/home" });
      await screen.findByText("Basics one");

      await click("Close tour");
      await pause();
      expect(screen.queryByTestId("tour")).not.toBeInTheDocument();

      await click("Go /start");
      await click("Go /home");

      expect(await screen.findByText("Home one")).toBeInTheDocument();
    });

    test("does not start a guide whose skipIf rejects the page", async () => {
      listGuideProgress.mockResolvedValue([]);
      const guides = [
        {
          ...BASICS,
          trigger: {
            kind: "first-visit",
            skipIf: ({ pathname }) => pathname === "/start",
          },
        },
      ];
      renderTasks({ guides });
      await settle();
      expect(screen.queryByTestId("tour")).not.toBeInTheDocument();

      await click("Go /home");

      expect(await screen.findByText("Basics one")).toBeInTheDocument();
    });

    test.each([
      ["a new-feature guide", "new-feature", true],
      ["any other guide", undefined, false],
    ])("%s with one step starts: %s", async (_label, kind, shown) => {
      listGuideProgress.mockResolvedValue([
        { guideKey: "welcome", status: "dismissed", snoozeCount: 0 },
      ]);
      const guides = [
        {
          key: "feature",
          type: "tour",
          kind,
          priority: 10,
          requires: { seen: "welcome" },
          audience: () => true,
          trigger: { kind: "first-visit" },
          steps: [step("basics-1", "Something new")],
        },
      ];
      renderTasks({ guides });
      await settle();

      expect(screen.queryByText("Something new") !== null).toBe(shown);
    });

    test("holds a guide that requires another until that one is seen", async () => {
      const guides = [
        {
          key: "feature",
          type: "tour",
          kind: "new-feature",
          priority: 10,
          requires: { seen: "welcome" },
          audience: () => true,
          trigger: { kind: "first-visit" },
          steps: [step("basics-1", "Something new")],
        },
      ];
      renderTasks({ guides });
      await settle();

      expect(screen.queryByTestId("tour")).not.toBeInTheDocument();
    });
  });

  describe("steps", () => {
    const SOLO = {
      key: "task-solo",
      type: "task",
      title: "Solo",
      priority: 1,
      audience: () => true,
      segments: [
        {
          key: "solo-first",
          route: "/home",
          steps: [step("home-1", "Home one")],
        },
        {
          key: "solo-second",
          route: "/home",
          steps: [step("home-2", "Home two"), step("late", "Late step")],
        },
      ],
    };

    beforeEach(() => {
      listGuideProgress.mockResolvedValue([
        { guideKey: "welcome", status: "completed", snoozeCount: 0 },
        { guideKey: "task-solo", status: "completed", snoozeCount: 0 },
      ]);
    });

    test("Back reaches the previous segment on the same page", async () => {
      renderTasks({ guides: [SOLO], at: "/home" });
      await settle();
      await click("Start solo");
      await screen.findByText("Home one");
      await click("Next");
      await screen.findByText("Home two");

      await click("Back");

      expect(await screen.findByText("Home one")).toBeInTheDocument();
    });

    test("skips a segment missing from the page it is on without waiting", async () => {
      const guides = [
        {
          ...SOLO,
          segments: [
            SOLO.segments[0],
            {
              key: "solo-absent",
              route: "/home",
              steps: [step("absent", "Absent step")],
            },
            GAMMA.segments[0],
          ],
        },
      ];
      // Waiting out this timeout would fail the test.
      renderTasks({ guides, at: "/home", anchorTimeoutMs: 60000 });
      await settle();
      await click("Start solo");
      await screen.findByText("Home one");

      await click("Next");

      expect(await screen.findByText("Gamma one")).toBeInTheDocument();
      expect(screen.queryByText("Absent step")).not.toBeInTheDocument();
    });

    test("decides Done again when an anchor renders late", async () => {
      renderTasks({
        guides: [SOLO],
        at: "/home",
        pages: {
          "/home": (
            <>
              {HOME}
              <Reveal anchor="late" />
            </>
          ),
        },
      });
      await settle();
      await click("Start solo");
      await screen.findByText("Home one");
      await click("Next");
      await screen.findByText("Home two");
      expect(screen.getByRole("button", { name: "Done" })).toBeInTheDocument();

      await click("Reveal late");

      expect(
        await screen.findByRole("button", { name: "Next" }),
      ).toBeInTheDocument();
      await click("Next");
      expect(await screen.findByText("Late step")).toBeInTheDocument();
    });
  });
});
