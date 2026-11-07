import { describe, test, expect, afterEach, vi } from "vitest";
import { render, screen, cleanup } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import "@testing-library/jest-dom/vitest";

import GuideTooltip from "@/guides/GuideTooltip";

const renderTooltip = (overrides = {}) => {
  const handlers = {
    onBack: vi.fn(),
    onNext: vi.fn(),
    onDone: vi.fn(),
    onClose: vi.fn(),
    onDismiss: vi.fn(),
  };
  render(
    <GuideTooltip
      title="Your account menu"
      body="Click your avatar."
      showBack={false}
      isLastStep={false}
      showDismiss
      containerProps={{ role: "alertdialog", "aria-modal": true }}
      {...handlers}
      {...overrides}
    />,
  );
  return handlers;
};

describe("GuideTooltip", () => {
  afterEach(() => {
    cleanup();
  });

  test("renders the title, body and the tour library's dialog role", () => {
    renderTooltip();

    expect(
      screen.getByRole("alertdialog", { name: "Your account menu" }),
    ).toBeInTheDocument();
    expect(screen.getByText("Click your avatar.")).toBeInTheDocument();
  });

  test("shows a list body as one item per sentence", () => {
    renderTooltip({ body: ["First sentence.", "Second sentence."] });

    const items = screen.getAllByRole("listitem");
    expect(items.map((item) => item.textContent)).toEqual([
      "First sentence.",
      "Second sentence.",
    ]);
  });

  test("offers Next but not Back or Done on the first step", async () => {
    const handlers = renderTooltip();

    expect(screen.queryByRole("button", { name: "Back" })).toBeNull();
    expect(screen.queryByRole("button", { name: "Done" })).toBeNull();
    await userEvent.click(screen.getByRole("button", { name: "Next" }));

    expect(handlers.onNext).toHaveBeenCalledTimes(1);
    expect(handlers.onDone).not.toHaveBeenCalled();
  });

  test("offers Back and Done on the last step", async () => {
    const handlers = renderTooltip({ showBack: true, isLastStep: true });

    expect(screen.queryByRole("button", { name: "Next" })).toBeNull();
    await userEvent.click(screen.getByRole("button", { name: "Back" }));
    await userEvent.click(screen.getByRole("button", { name: "Done" }));

    expect(handlers.onBack).toHaveBeenCalledTimes(1);
    expect(handlers.onDone).toHaveBeenCalledTimes(1);
    expect(handlers.onNext).not.toHaveBeenCalled();
  });

  test("marks the forward button as the one to focus", () => {
    renderTooltip();

    expect(screen.getByRole("button", { name: "Next" })).toHaveAttribute(
      "data-action",
      "primary",
    );
  });

  test("the close button calls onClose", async () => {
    const handlers = renderTooltip();

    await userEvent.click(screen.getByRole("button", { name: "Close tour" }));

    expect(handlers.onClose).toHaveBeenCalledTimes(1);
    expect(handlers.onDismiss).not.toHaveBeenCalled();
  });

  test("Don't show again calls onDismiss", async () => {
    const handlers = renderTooltip();

    await userEvent.click(
      screen.getByRole("button", { name: "Don't show again" }),
    );

    expect(handlers.onDismiss).toHaveBeenCalledTimes(1);
    expect(handlers.onClose).not.toHaveBeenCalled();
  });

  test("hides Don't show again when told to", () => {
    renderTooltip({ showDismiss: false });

    expect(
      screen.queryByRole("button", { name: "Don't show again" }),
    ).toBeNull();
  });
});
