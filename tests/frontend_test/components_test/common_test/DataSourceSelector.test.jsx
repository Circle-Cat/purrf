import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import DataSourceSelector from "@/components/common/DataSourceSelector.jsx";

describe("DataSourceSelector", () => {
  let onConfirm, onCancel, user;

  beforeEach(() => {
    onConfirm = vi.fn();
    onCancel = vi.fn();
    user = userEvent.setup();
    render(<DataSourceSelector onConfirm={onConfirm} onCancel={onCancel} />);
  });

  it("renders with Chat active and shows its items", () => {
    // Sidebar sources visible
    expect(screen.getByRole("button", { name: /chat/i })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /jira/i })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /gerrit/i })).toBeInTheDocument();
    expect(
      screen.getByRole("button", { name: /calendar/i }),
    ).toBeInTheDocument();
    // Chat items visible by default
    expect(screen.getByLabelText("TGIF")).toBeInTheDocument();
    expect(screen.getByLabelText("Tech Question")).toBeInTheDocument();
    // "Select All" in main panel exists and is unchecked
    const mainSelectAll = screen.getByLabelText(/select all$/i);
    expect(mainSelectAll).not.toBeChecked();
  });

  it("toggles a single item checkbox", async () => {
    const tgif = screen.getByLabelText("TGIF");
    expect(tgif).not.toBeChecked();
    await user.click(tgif);
    expect(tgif).toBeChecked();
    await user.click(tgif);
    expect(tgif).not.toBeChecked();
  });

  it("main 'Select All' toggles all visible items for active source", async () => {
    const tgif = screen.getByLabelText("TGIF");
    const techQ = screen.getByLabelText("Tech Question");
    const mainSelectAll = screen.getByLabelText(/select all$/i);
    await user.click(mainSelectAll);
    expect(tgif).toBeChecked();
    expect(techQ).toBeChecked();
    await user.click(mainSelectAll);
    expect(tgif).not.toBeChecked();
    expect(techQ).not.toBeChecked();
  });

  it("switches sources via sidebar and shows the corresponding items", async () => {
    await user.click(screen.getByRole("button", { name: /jira/i }));
    expect(screen.getByLabelText("Project A")).toBeInTheDocument();
    expect(screen.getByLabelText("Project B")).toBeInTheDocument();
    // Chat items should be gone from the main list
    expect(screen.queryByLabelText("TGIF")).not.toBeInTheDocument();
  });

  it("sidebar checkbox selects/deselects all for that source", async () => {
    // Go to Gerrit
    await user.click(screen.getByRole("button", { name: /gerrit/i }));
    const gerritSidebarAll = screen.getByLabelText(/select all gerrit/i);
    const repo1 = screen.getByLabelText("Repo1");
    const repo2 = screen.getByLabelText("Repo2");
    await user.click(gerritSidebarAll);
    expect(repo1).toBeChecked();
    expect(repo2).toBeChecked();
    await user.click(gerritSidebarAll);
    expect(repo1).not.toBeChecked();
    expect(repo2).not.toBeChecked();
  });

  it("calls onConfirm with selected items map", async () => {
    // Select in Chat
    await user.click(screen.getByLabelText("TGIF"));
    // Switch to Calendar and select one
    await user.click(screen.getByRole("button", { name: /calendar/i }));
    await user.click(screen.getByLabelText("Meeting 1"));
    await user.click(screen.getByRole("button", { name: /^ok$/i }));
    expect(onConfirm).toHaveBeenCalledTimes(1);
    const payload = onConfirm.mock.calls[0][0];
    // Expected structure: { Chat: ["TGIF"], Calendar: ["Meeting 1"], ... }
    expect(payload.Chat).toEqual(["TGIF"]);
    expect(payload.Calendar).toEqual(["Meeting 1"]);
  });

  it("calls onCancel when Cancel is clicked", async () => {
    await user.click(screen.getByRole("button", { name: /cancel/i }));
    expect(onCancel).toHaveBeenCalledTimes(1);
  });
});
