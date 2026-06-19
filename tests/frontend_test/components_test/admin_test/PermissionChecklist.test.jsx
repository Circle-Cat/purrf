import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, fireEvent } from "@testing-library/react";
import PermissionChecklist from "@/pages/AdminPermissions/components/PermissionChecklist";

const catalog = [
  "mentorship.round.read",
  "mentorship.round.write",
  "permission.manage",
];

describe("PermissionChecklist", () => {
  beforeEach(() => vi.clearAllMocks());

  it("pre-checks the active permissions", () => {
    render(
      <PermissionChecklist
        catalog={catalog}
        active={["mentorship.round.read"]}
        onSave={vi.fn()}
        saving={false}
      />,
    );
    expect(
      screen.getByRole("checkbox", { name: "mentorship.round.read" }),
    ).toBeChecked();
    expect(
      screen.getByRole("checkbox", { name: "permission.manage" }),
    ).not.toBeChecked();
  });

  it("disables Save until there is a diff", () => {
    render(
      <PermissionChecklist
        catalog={catalog}
        active={["mentorship.round.read"]}
        onSave={vi.fn()}
        saving={false}
      />,
    );
    const save = screen.getByRole("button", { name: /save/i });
    expect(save).toBeDisabled();
    fireEvent.click(
      screen.getByRole("checkbox", { name: "permission.manage" }),
    );
    expect(save).toBeEnabled();
  });

  it("calls onSave with the checked list", () => {
    const onSave = vi.fn();
    render(
      <PermissionChecklist
        catalog={catalog}
        active={["mentorship.round.read"]}
        onSave={onSave}
        saving={false}
      />,
    );
    fireEvent.click(
      screen.getByRole("checkbox", { name: "permission.manage" }),
    );
    fireEvent.click(screen.getByRole("button", { name: /save/i }));
    expect(onSave).toHaveBeenCalledWith(
      expect.arrayContaining(["mentorship.round.read", "permission.manage"]),
    );
  });

  it("disables Save when saving is true", () => {
    render(
      <PermissionChecklist
        catalog={catalog}
        active={["mentorship.round.read"]}
        onSave={vi.fn()}
        saving={true}
      />,
    );
    fireEvent.click(
      screen.getByRole("checkbox", { name: "permission.manage" }),
    );
    const save = screen.getByRole("button", { name: /save/i });
    expect(save).toBeDisabled();
  });
});
