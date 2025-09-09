import { describe, it, expect, beforeEach, vi } from "vitest";
import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import MemberSelector from "@/components/common/MemberSelector.jsx";
import { Group } from "@/constants/Groups";

const MEMBERS = [
  {
    id: "1",
    ldap: "ali",
    fullName: "Alice",
    group: Group.Employees,
    terminated: false,
  },
  {
    id: "2",
    ldap: "char",
    fullName: "Charlie",
    group: Group.Employees,
    terminated: true,
  },
  {
    id: "3",
    ldap: "intern1",
    fullName: "Ivy Intern",
    group: Group.Interns,
    terminated: false,
  },
  {
    id: "4",
    ldap: "vol1",
    fullName: "Vera Volunteer",
    group: Group.Volunteers,
    terminated: false,
  },
];

function renderMS(props = {}) {
  const onConfirm = vi.fn();
  const onCancel = vi.fn();
  render(
    <MemberSelector
      members={MEMBERS}
      onConfirm={onConfirm}
      onCancel={onCancel}
      {...props}
    />,
  );
  return { onConfirm, onCancel };
}

describe("MemberSelector", () => {
  beforeEach(() => vi.clearAllMocks());

  it("renders groups and member rows; shows initial selected count = 0", () => {
    renderMS();

    expect(
      screen.getByRole("button", { name: /Employees \(/i }),
    ).toBeInTheDocument();
    expect(
      screen.getByRole("button", { name: /Interns \(/i }),
    ).toBeInTheDocument();
    expect(
      screen.getByRole("button", { name: /Volunteers \(/i }),
    ).toBeInTheDocument();

    // Non-terminated employee visible; terminated hidden by default
    expect(screen.getByRole("button", { name: /Alice/i })).toBeInTheDocument();
    expect(
      screen.queryByRole("button", { name: /Charlie/i }),
    ).not.toBeInTheDocument();

    expect(screen.getByText(/0 selected/i)).toBeInTheDocument();
  });

  it("shows Full Name first (bold) and LDAP next (lighter) inline", () => {
    renderMS();

    const row = screen.getByRole("button", { name: /Alice/i });

    const nameEl = within(row).getByText("Alice");
    const ldapEl = within(row).getByText("ali");

    const isNameBeforeLdap =
      (nameEl.compareDocumentPosition(ldapEl) &
        Node.DOCUMENT_POSITION_FOLLOWING) !==
      0;
    expect(isNameBeforeLdap).toBe(true);
    expect(nameEl.className).toContain("ms-label-main");
    expect(ldapEl.className).toContain("ms-sub");
  });

  it("supports member toggle selection and updates selected count", async () => {
    const user = userEvent.setup();
    renderMS();

    await user.click(screen.getByRole("button", { name: /Alice/i }));
    expect(screen.getByText(/1 selected/i)).toBeInTheDocument();

    await user.click(screen.getByRole("button", { name: /Alice/i }));
    expect(screen.getByText(/0 selected/i)).toBeInTheDocument();
  });

  it("group click selects/deselects all visible members in that group", async () => {
    const user = userEvent.setup();
    renderMS();

    const employeesBtn = screen.getByRole("button", { name: /Employees \(/i });

    await user.click(employeesBtn);
    expect(screen.getByText(/1 selected/i)).toBeInTheDocument(); // only Yanpei visible

    await user.click(employeesBtn);
    expect(screen.getByText(/0 selected/i)).toBeInTheDocument();
  });

  it("Include Terminated Members toggles visibility and affects group select-all", async () => {
    const user = userEvent.setup();
    renderMS();

    const includeTerminated = screen.getByLabelText(
      /Include Terminated Members/i,
    );
    await user.click(includeTerminated);

    // Now terminated employee appears
    expect(
      screen.getByRole("button", { name: /Charlie/i }),
    ).toBeInTheDocument();

    const employeesBtn = screen.getByRole("button", { name: /Employees \(/i });
    await user.click(employeesBtn);
    expect(screen.getByText(/2 selected/i)).toBeInTheDocument();

    await user.click(employeesBtn);
    expect(screen.getByText(/0 selected/i)).toBeInTheDocument();
  });

  it("search filters by LDAP or full name and shows 'No matches' for empty groups", async () => {
    const user = userEvent.setup();
    renderMS();

    const search = screen.getByPlaceholderText(/Search by LDAP or full name/i);
    await user.type(search, "Ivy");

    expect(
      screen.getByRole("button", { name: /Ivy Intern/i }),
    ).toBeInTheDocument();

    const employeesSectionButton = screen.getByRole("button", {
      name: /Employees \(/i,
    });
    const volunteersSectionButton = screen.getByRole("button", {
      name: /Volunteers \(/i,
    });

    const employeesSection = employeesSectionButton.closest(".ms-section");
    const volunteersSection = volunteersSectionButton.closest(".ms-section");

    expect(employeesSection).toBeTruthy();
    expect(volunteersSection).toBeTruthy();

    expect(
      within(employeesSection).getByText(/No matches/i),
    ).toBeInTheDocument();
    expect(
      within(volunteersSection).getByText(/No matches/i),
    ).toBeInTheDocument();
  });

  it("returns selected IDs on OK", async () => {
    const user = userEvent.setup();
    const { onConfirm } = renderMS();

    await user.click(screen.getByRole("button", { name: /Ivy Intern/i })); // id "3"
    expect(screen.getByText(/1 selected/i)).toBeInTheDocument();

    await user.click(screen.getByRole("button", { name: /^OK$/i }));
    expect(onConfirm).toHaveBeenCalledTimes(1);
    const arg = onConfirm.mock.calls[0][0];
    expect(new Set(arg)).toEqual(new Set(["3"]));
  });

  it("computes indeterminate when some but not all members of a group are selected", async () => {
    const user = userEvent.setup();
    renderMS();

    const includeTerminated = screen.getByLabelText(
      /Include Terminated Members/i,
    );
    await user.click(includeTerminated);

    await user.click(screen.getByRole("button", { name: /Alice/i }));

    const employeesBtn = screen.getByRole("button", { name: /Employees \(/i });
    const checkEl = employeesBtn.querySelector(".ms-check");
    expect(checkEl).toBeTruthy();
    expect(checkEl.className).toContain("ms-check-mixed");
  });
});
