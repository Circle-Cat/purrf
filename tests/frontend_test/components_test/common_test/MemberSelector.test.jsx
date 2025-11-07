import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";

vi.mock("@/api/dashboardApi", () => ({
  getLdapsAndDisplayNames: vi.fn(),
}));

vi.mock("@/constants/Groups", () => ({
  Group: {
    Employees: "Employees",
    Interns: "Interns",
    Volunteers: "Volunteers",
  },
}));

vi.mock("@/constants/LdapStatus", () => ({
  LdapStatus: {
    Active: "Active",
    Terminated: "Terminated",
    All: "All",
  },
}));

const importSelectorOnce = async () => {
  try {
    return await import("@/components/common/MemberSelector.jsx");
  } catch {
    return await import("@/components/common/MemberSelector");
  }
};

const freshImport = async () => {
  vi.resetModules();
  return await importSelectorOnce();
};

const warmImport = async () => {
  return await importSelectorOnce();
};

const renderOpen = (Cmp, props = {}) => render(<Cmp open {...props} />);

const { getLdapsAndDisplayNames } = await import("@/api/dashboardApi");

// ---- Test payloads ----
const activePayload = {
  Employees: { Active: { alice: "Alice A", bob: "Bob B" } },
  Interns: { Active: { ivy: "Ivy I" } },
  Volunteers: { Active: { victor: "Victor V" } },
};

const allPayload = {
  Employees: {
    Active: { alice: "Alice A", bob: "Bob B" },
    Terminated: { tony: "Tony T" },
  },
  Interns: { Active: { ivy: "Ivy I" } },
  Volunteers: {
    Active: { victor: "Victor V" },
    Terminated: { tina: "Tina T" },
  },
};

const getDefault = (mod) => {
  if (!mod || !mod.default) {
    const keys = mod ? Object.keys(mod) : [];
    throw new Error(
      `MemberSelector default export not found. Module keys: [${keys.join(", ")}]`,
    );
  }
  return mod.default;
};

describe("MemberSelector (modal wrapper) rendering and interactions", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("loads Active members on open and renders groups/members", async () => {
    const mod = await freshImport();
    const MemberSelector = getDefault(mod);

    getLdapsAndDisplayNames.mockResolvedValueOnce({ data: activePayload });

    renderOpen(MemberSelector, {
      onConfirm: vi.fn(),
      onCancel: vi.fn(),
      onSelectedChange: vi.fn(),
    });

    expect(screen.getByRole("status")).toHaveTextContent(/loading members/i);
    await screen.findByRole("checkbox", { name: /Alice A/i });

    expect(
      screen.getByRole("checkbox", { name: /Employees \(0\/2\)/i }),
    ).toBeInTheDocument();
    expect(
      screen.getByRole("checkbox", { name: /Interns \(0\/1\)/i }),
    ).toBeInTheDocument();
    expect(
      screen.getByRole("checkbox", { name: /Volunteers \(0\/1\)/i }),
    ).toBeInTheDocument();

    expect(getLdapsAndDisplayNames).toHaveBeenCalledTimes(1);
    expect(getLdapsAndDisplayNames).toHaveBeenCalledWith({
      status: "Active",
      groups: ["Employees", "Interns", "Volunteers"],
    });
  });

  it("Include Terminated toggle triggers All fetch and shows terminated chips", async () => {
    const mod = await freshImport();
    const MemberSelector = getDefault(mod);

    getLdapsAndDisplayNames
      .mockResolvedValueOnce({ data: activePayload }) // Active
      .mockResolvedValueOnce({ data: allPayload }); // All

    renderOpen(MemberSelector);
    await screen.findByRole("checkbox", { name: /Alice A/i });

    const includeTerminated = screen.getByRole("checkbox", {
      name: /include terminated/i,
    });
    await userEvent.click(includeTerminated);

    await screen.findByRole("checkbox", { name: /Tony T \(terminated\)/i });
    await screen.findByRole("checkbox", { name: /Tina T \(terminated\)/i });

    expect(getLdapsAndDisplayNames).toHaveBeenCalledTimes(2);
    expect(getLdapsAndDisplayNames).toHaveBeenNthCalledWith(2, {
      status: "All",
      groups: ["Employees", "Interns", "Volunteers"],
    });
  });

  it("search filters members by ldap or full name", async () => {
    const mod = await freshImport();
    const MemberSelector = getDefault(mod);

    getLdapsAndDisplayNames.mockResolvedValueOnce({ data: activePayload });

    renderOpen(MemberSelector);
    await screen.findByRole("checkbox", { name: /Alice A/i });

    const input = screen.getByPlaceholderText(/search by ldap or full name/i);

    await userEvent.clear(input);
    await userEvent.type(input, "bob");
    expect(
      screen.getByRole("checkbox", { name: /Bob B/i }),
    ).toBeInTheDocument();
    expect(
      screen.queryByRole("checkbox", { name: /Alice A/i }),
    ).not.toBeInTheDocument();

    await userEvent.clear(input);
    await userEvent.type(input, "ivy");
    expect(
      screen.getByRole("checkbox", { name: /Ivy I/i }),
    ).toBeInTheDocument();
    expect(
      screen.queryByRole("checkbox", { name: /Bob B/i }),
    ).not.toBeInTheDocument();
  });

  it("group select toggles all in the group and updates footer count + onSelectedChange", async () => {
    const mod = await freshImport();
    const MemberSelector = getDefault(mod);

    getLdapsAndDisplayNames.mockResolvedValueOnce({ data: activePayload });
    const onSelectedChange = vi.fn();

    renderOpen(MemberSelector, { onSelectedChange });

    await screen.findByRole("checkbox", { name: /Alice A/i });

    const employeesGroup = screen.getByRole("checkbox", {
      name: /Employees \(0\/2\)/i,
    });
    await userEvent.click(employeesGroup);

    expect(screen.getByText(/2 selected/i)).toBeInTheDocument();

    await waitFor(() => {
      const lastCall = onSelectedChange.mock.calls.at(-1);
      const [ids, members] = lastCall;
      expect(new Set(ids)).toEqual(new Set(["alice", "bob"]));
      expect(new Set(members.map((m) => m.id))).toEqual(
        new Set(["alice", "bob"]),
      );
    });

    await userEvent.click(employeesGroup);
    expect(screen.getByText(/0 selected/i)).toBeInTheDocument();
  });

  it("member toggle works and confirm returns selected ids", async () => {
    const mod = await freshImport();
    const MemberSelector = getDefault(mod);

    getLdapsAndDisplayNames.mockResolvedValueOnce({ data: activePayload });

    const onConfirm = vi.fn();
    renderOpen(MemberSelector, { onConfirm });

    await screen.findByRole("checkbox", { name: /Alice A/i });
    await userEvent.click(screen.getByRole("checkbox", { name: /Alice A/i }));
    await userEvent.click(screen.getByRole("checkbox", { name: /Ivy I/i }));

    expect(screen.getByText(/2 selected/i)).toBeInTheDocument();
    await userEvent.click(screen.getByRole("button", { name: /^ok$/i }));

    const [ids] = onConfirm.mock.calls[0];
    expect(new Set(ids)).toEqual(new Set(["alice", "ivy"]));
  });

  it("module-level cache prevents duplicate Active fetch on remount with same groups", async () => {
    // First render in a fresh module world
    const mod1 = await freshImport();
    const MemberSelector1 = getDefault(mod1);

    getLdapsAndDisplayNames.mockResolvedValueOnce({ data: activePayload });

    const { unmount } = renderOpen(MemberSelector1);
    await screen.findByRole("checkbox", { name: /Alice A/i });
    unmount();

    // Import the same module again WITHOUT reset => reuse internal _memberCache
    const mod2 = await warmImport();
    const MemberSelector2 = getDefault(mod2);

    renderOpen(MemberSelector2);
    await screen.findByRole("checkbox", { name: /Alice A/i });

    expect(getLdapsAndDisplayNames).toHaveBeenCalledTimes(1);
  });

  it("Show 'checked' when all members in the group are selected", async () => {
    const mod = await freshImport();
    const MemberSelector = getDefault(mod);

    getLdapsAndDisplayNames.mockResolvedValueOnce({ data: activePayload });

    //Initial render
    renderOpen(MemberSelector);
    await screen.findByRole("checkbox", { name: /Alice A/i });
    await screen.findByRole("checkbox", { name: /Bob B/i });

    // Mock to select all members
    await userEvent.click(screen.getByRole("checkbox", { name: /Alice A/i }));
    await userEvent.click(screen.getByRole("checkbox", { name: /Bob B/i }));

    // Check the selection state of the group Employees
    const employeesGroup = screen.getByRole("checkbox", {
      name: /Employees \(2\/2\)/i,
    });

    // Ensure the state(the pre-grouping symbol) is changed
    const state = employeesGroup.getAttribute("aria-checked");
    expect(state).toBe("true");
  });

  it("Show 'unchecked' when no members in the group are selected", async () => {
    const mod = await freshImport();
    const MemberSelector = getDefault(mod);

    getLdapsAndDisplayNames.mockResolvedValueOnce({ data: activePayload });

    // Initial render
    renderOpen(MemberSelector);
    await screen.findByRole("checkbox", { name: /Employees \(0\/2\)/i });

    // Check the selection state of the group Employees
    const employeesGroup = screen.getByRole("checkbox", {
      name: /Employees \(0\/2\)/i,
    });

    // Ensure the state(the pre-grouping symbol) is not changed
    const state = employeesGroup.getAttribute("aria-checked");
    expect(state).toBe("false");
  });

  it("Keep the group symbol unchanged when only some members are selected", async () => {
    const mod = await freshImport();
    const MemberSelector = getDefault(mod);

    getLdapsAndDisplayNames.mockResolvedValueOnce({ data: activePayload });

    // Initial render
    renderOpen(MemberSelector);
    await screen.findByRole("checkbox", { name: /Alice A/i });

    // Select a member
    await userEvent.click(screen.getByRole("checkbox", { name: /Alice A/i }));

    // Check the selection state of the group Employees
    const employeesGroup = screen.getByRole("checkbox", {
      name: /Employees \(1\/2\)/i,
    });

    // Ensure the state(the pre-grouping symbol) is not changed
    const state = employeesGroup.getAttribute("aria-checked");
    expect(state).toBe("mixed");
  });
});

describe("MemberSelector (modal wrapper) close behaviors", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("calls onConfirm and closes when OK is clicked", async () => {
    const mod = await freshImport();
    const MemberSelector = getDefault(mod);

    getLdapsAndDisplayNames.mockResolvedValueOnce({ data: activePayload });

    const onClose = vi.fn();
    const onConfirm = vi.fn();

    renderOpen(MemberSelector, { onClose, onConfirm });

    await screen.findByRole("checkbox", { name: /Alice A/i });
    await userEvent.click(screen.getByRole("checkbox", { name: /Alice A/i }));
    await userEvent.click(screen.getByRole("button", { name: /^ok$/i }));

    expect(onConfirm).toHaveBeenCalled();
    expect(onClose).toHaveBeenCalled();
  });

  it("clicking backdrop calls onClose", async () => {
    const mod = await freshImport();
    const MemberSelector = getDefault(mod);

    getLdapsAndDisplayNames.mockResolvedValueOnce({ data: activePayload });

    const onClose = vi.fn();

    renderOpen(MemberSelector, { onClose });

    await screen.findByRole("checkbox", { name: /Alice A/i });

    const backdrop = screen.getByRole("presentation"); // ds-modal-backdrop
    await userEvent.click(backdrop);

    expect(onClose).toHaveBeenCalledTimes(1);
  });
});
