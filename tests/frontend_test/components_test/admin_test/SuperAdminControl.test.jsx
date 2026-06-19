import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, fireEvent } from "@testing-library/react";
import SuperAdminControl from "@/pages/AdminPermissions/components/SuperAdminControl";

const base = {
  targetIsSuperAdmin: false,
  callerIsSuperAdmin: false,
  callerCanRevoke: false,
  isSelf: false,
  busy: false,
  onGrant: vi.fn(),
  onRevoke: vi.fn(),
};

describe("SuperAdminControl", () => {
  beforeEach(() => vi.clearAllMocks());

  it("hides the Make button when caller is not a super-admin", () => {
    render(<SuperAdminControl {...base} />);
    expect(
      screen.queryByRole("button", { name: /make super-admin/i }),
    ).toBeNull();
  });

  it("shows Make super-admin when caller is a super-admin and target is not", () => {
    render(<SuperAdminControl {...base} callerIsSuperAdmin />);
    fireEvent.click(screen.getByRole("button", { name: /make super-admin/i }));
    expect(base.onGrant).toHaveBeenCalled();
  });

  it("shows Revoke when target is super-admin and caller can revoke", () => {
    render(<SuperAdminControl {...base} targetIsSuperAdmin callerCanRevoke />);
    expect(
      screen.getByRole("button", { name: /revoke super-admin/i }),
    ).not.toBeDisabled();
    fireEvent.click(
      screen.getByRole("button", { name: /revoke super-admin/i }),
    );
    expect(base.onRevoke).toHaveBeenCalled();
  });

  it("disables Revoke when acting on yourself", () => {
    render(
      <SuperAdminControl {...base} targetIsSuperAdmin callerCanRevoke isSelf />,
    );
    expect(
      screen.getByRole("button", { name: /revoke super-admin/i }),
    ).toBeDisabled();
  });

  it("hides Revoke when caller lacks the revoke permission", () => {
    render(<SuperAdminControl {...base} targetIsSuperAdmin />);
    expect(
      screen.queryByRole("button", { name: /revoke super-admin/i }),
    ).toBeNull();
  });
});
