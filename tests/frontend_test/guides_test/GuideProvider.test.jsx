import { describe, test, expect, beforeEach, afterEach, vi } from "vitest";
import {
  render,
  screen,
  cleanup,
  waitFor,
  act,
  fireEvent,
} from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter, useNavigate } from "react-router-dom";
import "@testing-library/jest-dom/vitest";

import { GuideProvider } from "@/guides/GuideProvider";
import { FlagsContext } from "@/context/flags";
import { useGuides } from "@/guides/GuideContext";
import { resetGuideSession } from "@/guides/session";
import { listGuideProgress, recordGuideProgress } from "@/api/guidesApi";
import { useAuth } from "@/context/auth";
import { PERMISSIONS } from "@/constants/Permissions";

vi.mock("@/api/guidesApi", () => ({
  listGuideProgress: vi.fn(),
  recordGuideProgress: vi.fn(),
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
      <div data-testid="tour-body">
        {[].concat(steps[stepIndex].body).join(" | ")}
      </div>
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

const Controls = () => {
  const navigate = useNavigate();
  const { start } = useGuides();
  return (
    <>
      <button onClick={() => navigate("/elsewhere")}>Go elsewhere</button>
      <button onClick={() => start("welcome")}>Replay</button>
    </>
  );
};

const FLAG_ON = { flags: { "onboarding-guides": true }, ready: true };

const engineTree = ({ anchors, guides, actions, flagState }) => (
  <FlagsContext.Provider
    value={{ ...flagState, setFlags: () => {}, setReady: () => {} }}
  >
    <MemoryRouter initialEntries={["/start"]}>
      <GuideProvider guides={guides} actions={actions}>
        {anchors.map((anchor) => (
          <span key={anchor} data-tour={anchor}>
            {anchor}
          </span>
        ))}
        <Controls />
      </GuideProvider>
    </MemoryRouter>
  </FlagsContext.Provider>
);

const renderEngine = ({
  anchors = ["avatar-menu", "nav-group-apply"],
  guides,
  actions,
  flagState = FLAG_ON,
} = {}) => render(engineTree({ anchors, guides, actions, flagState }));

// Lets the progress fetch settle so a "did not start" assertion is not
// vacuously early.
const settle = async () => {
  await waitFor(() => expect(listGuideProgress).toHaveBeenCalled());
  await act(async () => {});
};

describe("GuideProvider", () => {
  beforeEach(() => {
    resetGuideSession();
    useAuth.mockReturnValue(SIGNED_IN);
    recordGuideProgress.mockResolvedValue({});
  });

  afterEach(() => {
    cleanup();
    vi.resetAllMocks();
    vi.restoreAllMocks();
  });

  test("starts the welcome tour when it has no progress row", async () => {
    // A row for a different guide must not be read as welcome's.
    listGuideProgress.mockResolvedValue([
      { guideKey: "inbox-intro", status: "completed", snoozeCount: 0 },
    ]);
    renderEngine();

    expect(await screen.findByText("Your account menu")).toBeInTheDocument();
    expect(listGuideProgress).toHaveBeenCalledTimes(1);
  });

  test("starts the welcome tour again when it was snoozed", async () => {
    listGuideProgress.mockResolvedValue([
      { guideKey: "inbox-intro", status: "completed", snoozeCount: 0 },
      { guideKey: "welcome", status: "snoozed", snoozeCount: 1 },
    ]);
    renderEngine();

    expect(await screen.findByText("Your account menu")).toBeInTheDocument();
  });

  test.each(["completed", "dismissed"])(
    "does not start a guide that was %s",
    async (status) => {
      listGuideProgress.mockResolvedValue([
        { guideKey: "inbox-intro", status: "snoozed", snoozeCount: 1 },
        { guideKey: "welcome", status, snoozeCount: 0 },
      ]);
      renderEngine();
      await settle();

      expect(screen.queryByTestId("tour")).not.toBeInTheDocument();
    },
  );

  test("starts nothing when the progress fetch fails", async () => {
    const error = vi.spyOn(console, "error").mockImplementation(() => {});
    listGuideProgress.mockRejectedValue(new Error("boom"));
    renderEngine();
    await settle();

    expect(screen.queryByTestId("tour")).not.toBeInTheDocument();
    expect(error).toHaveBeenCalled();
  });

  test("auto-starts only the highest-priority eligible guide", async () => {
    const guides = [
      {
        key: "low",
        type: "tour",
        priority: 10,
        audience: () => true,
        trigger: { kind: "first-visit" },
        steps: [{ anchor: "avatar-menu", title: "Low guide", body: "l" }],
      },
      {
        key: "high",
        type: "tour",
        priority: 50,
        audience: () => true,
        trigger: { kind: "first-visit" },
        steps: [{ anchor: "avatar-menu", title: "High guide", body: "h" }],
      },
    ];
    listGuideProgress.mockResolvedValue([]);
    renderEngine({ guides });

    expect(await screen.findByText("High guide")).toBeInTheDocument();
    await userEvent.click(screen.getByRole("button", { name: "Close tour" }));

    expect(recordGuideProgress).toHaveBeenCalledWith("high", "snoozed");
    expect(screen.queryByText("Low guide")).not.toBeInTheDocument();
  });

  test("skips a guide whose audience excludes the viewer", async () => {
    useAuth.mockReturnValue({ ...SIGNED_IN, permissions: ["a.read"] });
    const audience = vi.fn(({ permissions }) => permissions.includes("b"));
    const guides = [
      {
        key: "admins",
        type: "tour",
        priority: 10,
        audience,
        trigger: { kind: "first-visit" },
        steps: [{ anchor: "avatar-menu", title: "Admins", body: "a" }],
      },
    ];
    listGuideProgress.mockResolvedValue([]);
    renderEngine({ guides });
    await settle();

    expect(audience).toHaveBeenCalledWith({
      permissions: ["a.read"],
      flags: { "onboarding-guides": true },
    });
    expect(screen.queryByTestId("tour")).not.toBeInTheDocument();
  });

  test("does nothing while the onboarding-guides flag is off", async () => {
    listGuideProgress.mockResolvedValue([]);
    renderEngine({ flagState: { flags: {}, ready: true } });
    await act(async () => {});

    await userEvent.click(screen.getByRole("button", { name: "Replay" }));
    await act(async () => {});

    expect(listGuideProgress).not.toHaveBeenCalled();
    expect(screen.queryByTestId("tour")).not.toBeInTheDocument();
  });

  test("waits for LaunchDarkly to answer before starting", async () => {
    listGuideProgress.mockResolvedValue([]);
    const anchors = ["avatar-menu", "nav-group-apply"];
    const { rerender } = renderEngine({
      flagState: { flags: { "onboarding-guides": true }, ready: false },
    });
    await act(async () => {});
    expect(listGuideProgress).not.toHaveBeenCalled();

    rerender(engineTree({ anchors, flagState: FLAG_ON }));

    expect(await screen.findByTestId("tour")).toBeInTheDocument();
  });

  test("auto-starts at most one guide per session", async () => {
    listGuideProgress.mockResolvedValue([]);
    const first = renderEngine();
    await screen.findByText("Your account menu");
    await userEvent.click(screen.getByRole("button", { name: "Close tour" }));
    first.unmount();

    listGuideProgress.mockResolvedValue([
      { guideKey: "welcome", status: "snoozed", snoozeCount: 1 },
    ]);
    renderEngine();
    await act(async () => {});

    expect(screen.queryByTestId("tour")).not.toBeInTheDocument();
  });

  test("Done on the last step records completed", async () => {
    listGuideProgress.mockResolvedValue([]);
    renderEngine();
    await screen.findByText("Your account menu");

    await userEvent.click(screen.getByRole("button", { name: "Next" }));
    await screen.findByText("Open Positions");
    await userEvent.click(screen.getByRole("button", { name: "Next" }));
    await screen.findByText("That's it for now");
    await userEvent.click(screen.getByRole("button", { name: "Done" }));

    expect(recordGuideProgress).toHaveBeenCalledTimes(1);
    expect(recordGuideProgress).toHaveBeenCalledWith("welcome", "completed");
    expect(screen.queryByTestId("tour")).not.toBeInTheDocument();
  });

  test("Back returns to the previous step", async () => {
    listGuideProgress.mockResolvedValue([]);
    renderEngine();
    await screen.findByText("Your account menu");
    expect(
      screen.queryByRole("button", { name: "Back" }),
    ).not.toBeInTheDocument();

    await userEvent.click(screen.getByRole("button", { name: "Next" }));
    await screen.findByText("Open Positions");
    await userEvent.click(screen.getByRole("button", { name: "Back" }));

    expect(await screen.findByText("Your account menu")).toBeInTheDocument();
    expect(recordGuideProgress).not.toHaveBeenCalled();
  });

  test("Don't show again records dismissed", async () => {
    listGuideProgress.mockResolvedValue([]);
    renderEngine();
    await screen.findByText("Your account menu");

    await userEvent.click(
      screen.getByRole("button", { name: "Don't show again" }),
    );

    expect(recordGuideProgress).toHaveBeenCalledWith("welcome", "dismissed");
    expect(screen.queryByTestId("tour")).not.toBeInTheDocument();
  });

  test("the close button records snoozed", async () => {
    listGuideProgress.mockResolvedValue([]);
    renderEngine();
    await screen.findByText("Your account menu");

    await userEvent.click(screen.getByRole("button", { name: "Close tour" }));

    expect(recordGuideProgress).toHaveBeenCalledTimes(1);
    expect(recordGuideProgress).toHaveBeenCalledWith("welcome", "snoozed");
  });

  test("Escape records snoozed", async () => {
    listGuideProgress.mockResolvedValue([]);
    renderEngine();
    await screen.findByText("Your account menu");

    fireEvent.keyDown(document, { key: "Escape" });

    await waitFor(() =>
      expect(screen.queryByTestId("tour")).not.toBeInTheDocument(),
    );
    expect(recordGuideProgress).toHaveBeenCalledWith("welcome", "snoozed");
  });

  test("a route change ends the tour as snoozed", async () => {
    listGuideProgress.mockResolvedValue([]);
    renderEngine();
    await screen.findByText("Your account menu");

    // The mocked tooltip is not modal, so the page stays clickable here.
    await userEvent.click(screen.getByRole("button", { name: "Go elsewhere" }));

    await waitFor(() =>
      expect(screen.queryByTestId("tour")).not.toBeInTheDocument(),
    );
    expect(recordGuideProgress).toHaveBeenCalledWith("welcome", "snoozed");
  });

  test("still treats the guide as handled when the write fails", async () => {
    const error = vi.spyOn(console, "error").mockImplementation(() => {});
    listGuideProgress.mockResolvedValue([]);
    recordGuideProgress.mockRejectedValue(new Error("down"));
    renderEngine();
    await screen.findByText("Your account menu");

    await userEvent.click(screen.getByRole("button", { name: "Close tour" }));

    await waitFor(() => expect(error).toHaveBeenCalled());
    expect(screen.queryByTestId("tour")).not.toBeInTheDocument();
  });

  describe("a manually started tour", () => {
    beforeEach(() => {
      listGuideProgress.mockResolvedValue([
        { guideKey: "inbox-intro", status: "snoozed", snoozeCount: 1 },
        { guideKey: "welcome", status: "completed", snoozeCount: 0 },
      ]);
    });

    test("hides Don't show again and writes nothing on close", async () => {
      renderEngine();
      await settle();
      expect(screen.queryByTestId("tour")).not.toBeInTheDocument();

      await userEvent.click(screen.getByRole("button", { name: "Replay" }));

      expect(await screen.findByText("Your account menu")).toBeInTheDocument();
      expect(
        screen.queryByRole("button", { name: "Don't show again" }),
      ).not.toBeInTheDocument();
      await userEvent.click(screen.getByRole("button", { name: "Close tour" }));

      expect(screen.queryByTestId("tour")).not.toBeInTheDocument();
      expect(recordGuideProgress).not.toHaveBeenCalled();
    });

    test("writes nothing on Escape or a route change", async () => {
      renderEngine();
      await settle();

      await userEvent.click(screen.getByRole("button", { name: "Replay" }));
      await screen.findByText("Your account menu");
      fireEvent.keyDown(document, { key: "Escape" });
      await waitFor(() =>
        expect(screen.queryByTestId("tour")).not.toBeInTheDocument(),
      );

      await userEvent.click(screen.getByRole("button", { name: "Replay" }));
      await screen.findByText("Your account menu");
      await userEvent.click(
        screen.getByRole("button", { name: "Go elsewhere" }),
      );
      await waitFor(() =>
        expect(screen.queryByTestId("tour")).not.toBeInTheDocument(),
      );

      expect(recordGuideProgress).not.toHaveBeenCalled();
    });

    test("records completed on Done", async () => {
      renderEngine();
      await settle();

      await userEvent.click(screen.getByRole("button", { name: "Replay" }));
      await screen.findByText("Your account menu");
      await userEvent.click(screen.getByRole("button", { name: "Next" }));
      await screen.findByText("Open Positions");
      await userEvent.click(screen.getByRole("button", { name: "Next" }));
      await screen.findByText("That's it for now");
      await userEvent.click(screen.getByRole("button", { name: "Done" }));

      expect(recordGuideProgress).toHaveBeenCalledTimes(1);
      expect(recordGuideProgress).toHaveBeenCalledWith("welcome", "completed");
    });

    test("can be started after an auto-started tour this session", async () => {
      listGuideProgress.mockResolvedValue([]);
      renderEngine();
      await screen.findByText("Your account menu");
      await userEvent.click(screen.getByRole("button", { name: "Close tour" }));

      await userEvent.click(screen.getByRole("button", { name: "Replay" }));

      expect(await screen.findByText("Your account menu")).toBeInTheDocument();
    });
  });

  describe("anchors", () => {
    test("does not start a guide none of whose anchors are on the page", async () => {
      listGuideProgress.mockResolvedValue([]);
      renderEngine({ anchors: [] });
      await settle();

      await userEvent.click(screen.getByRole("button", { name: "Replay" }));
      await act(async () => {});

      expect(screen.queryByTestId("tour")).not.toBeInTheDocument();
      expect(recordGuideProgress).not.toHaveBeenCalled();
    });

    test("skips a step whose anchor is missing", async () => {
      listGuideProgress.mockResolvedValue([]);
      renderEngine({ anchors: ["avatar-menu"] });
      await screen.findByText("Your account menu");

      await userEvent.click(screen.getByRole("button", { name: "Next" }));

      expect(await screen.findByText("That's it for now")).toBeInTheDocument();
      // Index into the resolved steps: avatar, me, apply, closing.
      expect(screen.getByTestId("tour")).toHaveAttribute("data-step", "3");
      expect(screen.queryByText("Open Positions")).not.toBeInTheDocument();
    });

    test("starts at the first step whose anchor exists", async () => {
      listGuideProgress.mockResolvedValue([]);
      renderEngine({ anchors: ["nav-group-apply"] });

      expect(await screen.findByText("Open Positions")).toBeInTheDocument();
      // No later step's anchor exists, so this one is the last.
      expect(screen.getByRole("button", { name: "Done" })).toBeInTheDocument();
      expect(
        screen.queryByRole("button", { name: "Back" }),
      ).not.toBeInTheDocument();
    });
  });

  describe("steps built from the sidebar", () => {
    const ALL_ANCHORS = [
      "avatar-menu",
      "nav-group-me",
      "nav-group-apply",
      "nav-group-recruiting",
      "nav-group-mentorship",
      "nav-group-activity",
      "nav-group-admin",
    ];

    test("lists only the entries the viewer can see", async () => {
      useAuth.mockReturnValue({
        ...SIGNED_IN,
        permissions: [
          PERMISSIONS.RECRUITING_AUDIT_READ,
          PERMISSIONS.RECRUITING_INTERVIEW_EVALUATE,
          PERMISSIONS.INTERNAL_ACTIVITY_READ,
        ],
      });
      listGuideProgress.mockResolvedValue([]);
      renderEngine({ anchors: ALL_ANCHORS });
      await screen.findByText("Your account menu");

      await userEvent.click(screen.getByRole("button", { name: "Next" }));
      await screen.findByText("Your dashboard");
      await userEvent.click(screen.getByRole("button", { name: "Next" }));
      await screen.findByText("Open Positions");
      await userEvent.click(screen.getByRole("button", { name: "Next" }));

      expect(await screen.findByText("Recruiting")).toBeInTheDocument();
      expect(screen.getByTestId("tour-body")).toHaveTextContent(
        "My Interview Evaluations lists the interviews you were assigned to score. | " +
          "Recruiting Audit reports on applications across postings.",
      );

      // Mentorship's anchor is on the page, but the viewer sees none of it.
      await userEvent.click(screen.getByRole("button", { name: "Next" }));
      expect(await screen.findByText("Activity data")).toBeInTheDocument();
      expect(screen.getByTestId("tour-body")).toHaveTextContent(
        /^DataSearch looks up work activity by person and date\.$/,
      );

      await userEvent.click(screen.getByRole("button", { name: "Next" }));
      expect(await screen.findByText("That's it for now")).toBeInTheDocument();
    });
  });

  test("runs a step's before action and waits for the layout to settle", async () => {
    const expandSidebar = vi.fn(() => true);
    listGuideProgress.mockResolvedValue([]);
    renderEngine({ actions: { "expand-sidebar": expandSidebar } });
    await screen.findByText("Your account menu");
    expect(expandSidebar).not.toHaveBeenCalled();

    await userEvent.click(screen.getByRole("button", { name: "Next" }));

    expect(expandSidebar).toHaveBeenCalledTimes(1);
    // Still on the first step while the sidebar transition runs.
    expect(screen.getByText("Your account menu")).toBeInTheDocument();
    expect(await screen.findByText("Open Positions")).toBeInTheDocument();
  });

  test("does not wait when the before action changed nothing", async () => {
    const expandSidebar = vi.fn(() => false);
    listGuideProgress.mockResolvedValue([]);
    renderEngine({ actions: { "expand-sidebar": expandSidebar } });
    await screen.findByText("Your account menu");

    await userEvent.click(screen.getByRole("button", { name: "Next" }));

    expect(expandSidebar).toHaveBeenCalledTimes(1);
    await waitFor(() =>
      expect(screen.getByText("Open Positions")).toBeInTheDocument(),
    );
  });

  describe("is inactive", () => {
    test.each([
      ["while auth is loading", { loading: true }],
      ["for an unverified email", { hasVerifiedEmail: false }],
      ["for a forbidden account", { accessDenied: true }],
      ["after an auth error", { authError: true }],
    ])("%s", async (_label, override) => {
      useAuth.mockReturnValue({ ...SIGNED_IN, ...override });
      listGuideProgress.mockResolvedValue([]);
      renderEngine();
      await act(async () => {});

      await userEvent.click(screen.getByRole("button", { name: "Replay" }));
      await act(async () => {});

      expect(listGuideProgress).not.toHaveBeenCalled();
      expect(screen.queryByTestId("tour")).not.toBeInTheDocument();
    });
  });
});
