import { render, screen, cleanup, within } from "@testing-library/react";
import { describe, it, expect, vi, afterEach } from "vitest";
import userEvent from "@testing-library/user-event";

import ContactEmailList from "@/pages/SignInSecurity/components/ContactEmailList";

import "@testing-library/jest-dom/vitest";

const makeEmail = (overrides = {}) => ({
  emailId: 1,
  email: "alice@gmail.com",
  otpConfirmed: true,
  isPrimary: false,
  ...overrides,
});

describe("ContactEmailList", () => {
  afterEach(cleanup);

  it("shows a loading placeholder when isLoading is true", () => {
    render(<ContactEmailList emails={[]} isLoading onVerify={vi.fn()} />);

    expect(screen.getByText("Loading…")).toBeInTheDocument();
  });

  it("shows an empty-state message when there are no emails", () => {
    render(
      <ContactEmailList emails={[]} isLoading={false} onVerify={vi.fn()} />,
    );

    expect(screen.getByText("No emails yet.")).toBeInTheDocument();
  });

  it("badges the primary and unverified addresses", () => {
    render(
      <ContactEmailList
        emails={[
          makeEmail({ emailId: 1, email: "a@x.com", isPrimary: true }),
          makeEmail({ emailId: 2, email: "b@x.com", otpConfirmed: false }),
        ]}
        isLoading={false}
        onVerify={vi.fn()}
      />,
    );

    const rows = screen.getAllByRole("listitem");
    expect(within(rows[0]).getByText("Primary contact")).toBeInTheDocument();
    expect(within(rows[0]).queryByText("Unverified")).not.toBeInTheDocument();
    expect(within(rows[1]).getByText("Unverified")).toBeInTheDocument();
  });

  it("offers Verify only on unverified addresses and reports the row", async () => {
    const onVerify = vi.fn();
    const user = userEvent.setup();
    const unverified = makeEmail({
      emailId: 2,
      email: "b@x.com",
      otpConfirmed: false,
    });
    render(
      <ContactEmailList
        emails={[makeEmail(), unverified]}
        isLoading={false}
        onVerify={onVerify}
      />,
    );

    const rows = screen.getAllByRole("listitem");
    expect(
      within(rows[0]).queryByRole("button", { name: "Verify" }),
    ).not.toBeInTheDocument();

    await user.click(within(rows[1]).getByRole("button", { name: "Verify" }));
    expect(onVerify).toHaveBeenCalledWith(unverified);
  });
});
