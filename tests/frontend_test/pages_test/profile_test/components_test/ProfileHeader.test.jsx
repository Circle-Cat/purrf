import { describe, it, expect, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import ProfileHeader from "@/pages/Profile/components/ProfileHeader";

vi.mock("@/utils/dateTime", () => ({
  formatTimezoneLabel: (tz) => `TZ:${tz}`,
}));

describe("ProfileHeader", () => {
  it("renders the full name with the preferred name and last name", () => {
    render(
      <ProfileHeader
        info={{ firstName: "John", preferredName: "Johnny", lastName: "Doe" }}
        onEditClick={vi.fn()}
      />,
    );
    expect(screen.getByRole("heading")).toHaveTextContent("John (Johnny) Doe");
  });

  it("omits the preferred name when not provided", () => {
    render(
      <ProfileHeader
        info={{ firstName: "John", lastName: "Doe" }}
        onEditClick={vi.fn()}
      />,
    );
    const heading = screen.getByRole("heading");
    expect(heading).toHaveTextContent("John Doe");
    expect(heading).not.toHaveTextContent("(");
  });

  it("renders the formatted timezone when one is provided", () => {
    render(
      <ProfileHeader
        info={{
          firstName: "John",
          lastName: "Doe",
          timezone: "America/New_York",
        }}
        onEditClick={vi.fn()}
      />,
    );
    expect(screen.getByText("TZ:America/New_York")).toBeInTheDocument();
  });

  it("does not render a timezone when none is provided", () => {
    render(
      <ProfileHeader
        info={{ firstName: "John", lastName: "Doe" }}
        onEditClick={vi.fn()}
      />,
    );
    expect(screen.queryByText(/^TZ:/)).not.toBeInTheDocument();
  });

  it("calls onEditClick when the Edit Profile button is clicked", async () => {
    const onEditClick = vi.fn();
    const user = userEvent.setup();
    render(
      <ProfileHeader
        info={{ firstName: "John", lastName: "Doe" }}
        onEditClick={onEditClick}
      />,
    );
    await user.click(screen.getByRole("button", { name: "Edit Profile" }));
    expect(onEditClick).toHaveBeenCalledTimes(1);
  });
});
