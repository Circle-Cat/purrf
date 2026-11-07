import { describe, test, expect, afterEach, vi } from "vitest";
import { render, screen, cleanup } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import "@testing-library/jest-dom/vitest";

import GuideTourRenderer from "@/guides/GuideTourRenderer";

const STEPS = [
  { anchor: "first-anchor", title: "First title", body: "First body" },
  { anchor: "second-anchor", title: "Second title", body: "Second body" },
];

const renderTour = (overrides = {}) => {
  const handlers = {
    onBack: vi.fn(),
    onNext: vi.fn(),
    onDone: vi.fn(),
    onClose: vi.fn(),
    onDismiss: vi.fn(),
  };
  render(
    <>
      <button data-tour="first-anchor">first</button>
      <button data-tour="second-anchor">second</button>
      <GuideTourRenderer
        steps={STEPS}
        stepIndex={1}
        showBack
        isLastStep
        showDismiss
        {...handlers}
        {...overrides}
      />
    </>,
  );
  return handlers;
};

describe("GuideTourRenderer", () => {
  afterEach(() => {
    cleanup();
  });

  test("shows the step it is told to in a GuideTooltip", async () => {
    renderTour();

    expect(await screen.findByText("Second title")).toBeInTheDocument();
    expect(screen.getByText("Second body")).toBeInTheDocument();
    expect(screen.queryByText("First title")).not.toBeInTheDocument();
  });

  test("passes the step controls through to the tooltip", async () => {
    const handlers = renderTour();
    await screen.findByText("Second title");
    const user = userEvent.setup();

    await user.click(screen.getByRole("button", { name: "Done" }));
    await user.click(screen.getByRole("button", { name: "Back" }));
    await user.click(screen.getByRole("button", { name: "Close tour" }));
    await user.click(screen.getByRole("button", { name: "Don't show again" }));

    expect(handlers.onDone).toHaveBeenCalledTimes(1);
    expect(handlers.onBack).toHaveBeenCalledTimes(1);
    expect(handlers.onClose).toHaveBeenCalledTimes(1);
    expect(handlers.onDismiss).toHaveBeenCalledTimes(1);
    expect(handlers.onNext).not.toHaveBeenCalled();
  });

  test("passes a list body through to the tooltip", async () => {
    renderTour({
      steps: [
        STEPS[0],
        {
          ...STEPS[1],
          body: [
            { label: "One", text: " sentence." },
            { label: "Another", text: " sentence." },
          ],
        },
      ],
    });
    await screen.findByText("Second title");

    expect(
      screen.getAllByRole("listitem").map((item) => item.textContent),
    ).toEqual(["One sentence.", "Another sentence."]);
  });
});
