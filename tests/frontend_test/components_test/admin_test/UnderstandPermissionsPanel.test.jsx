import { describe, it, expect, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import UnderstandPermissionsPanel from "@/pages/AdminPermissions/components/UnderstandPermissionsPanel";

const catalog = [
  {
    name: "dashboard.activity_summary.read",
    description: "View the activity summary dashboard.",
  },
  {
    name: "recruiting.job.read",
    description: "View recruiting job postings.",
  },
  {
    name: "recruiting.job.write",
    description: "Create or edit recruiting job postings.",
  },
  {
    name: "totally_new.thing.read",
    description: "A future permission namespace.",
  },
];

describe("UnderstandPermissionsPanel", () => {
  it("renders a trigger and opens the panel with grouped entries", async () => {
    const user = userEvent.setup();
    render(<UnderstandPermissionsPanel catalog={catalog} />);

    await user.click(
      screen.getByRole("button", { name: "Understand permissions" }),
    );

    expect(
      screen.getByRole("heading", { name: "Dashboard" }),
    ).toBeInTheDocument();
    expect(
      screen.getByRole("heading", { name: "Recruiting" }),
    ).toBeInTheDocument();
    expect(screen.getByText("recruiting.job.read")).toBeInTheDocument();
    expect(
      screen.getByText("View recruiting job postings."),
    ).toBeInTheDocument();
  });

  it("falls back to a title-cased heading for an unrecognized namespace", async () => {
    const user = userEvent.setup();
    render(<UnderstandPermissionsPanel catalog={catalog} />);

    await user.click(
      screen.getByRole("button", { name: "Understand permissions" }),
    );

    expect(
      screen.getByRole("heading", { name: "Totally New" }),
    ).toBeInTheDocument();
  });

  it("does not block interaction with content outside the panel (non-modal)", async () => {
    const user = userEvent.setup();
    const onOutsideClick = vi.fn();
    render(
      <>
        <button onClick={onOutsideClick}>Outside button</button>
        <UnderstandPermissionsPanel catalog={catalog} />
      </>,
    );

    await user.click(
      screen.getByRole("button", { name: "Understand permissions" }),
    );
    await user.click(screen.getByRole("button", { name: "Outside button" }));

    expect(onOutsideClick).toHaveBeenCalledTimes(1);
  });
});
