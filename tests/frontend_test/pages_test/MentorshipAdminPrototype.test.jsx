import { describe, it, expect } from "vitest";
import { render, screen, fireEvent, within } from "@testing-library/react";
import MentorshipAdminPrototype from "@/pages/MentorshipAdminPrototype";

/** The permission chips are their own labelled group; card buttons are not. */
const chip = (name) =>
  within(screen.getByRole("group", { name: "Permissions" })).getByRole(
    "button",
    { name },
  );

describe("MentorshipAdminPrototype smoke", () => {
  it("renders the console and walks the flows that carry the design", () => {
    render(<MentorshipAdminPrototype />);

    expect(screen.getByText("Pending approvals")).toBeInTheDocument();
    expect(screen.getByText(/2 waiting/)).toBeInTheDocument();

    // The four states of "meetings last round" are four different answers, and
    // only one of them is the number zero.
    expect(screen.getAllByText("First time").length).toBeGreaterThan(0);
    expect(screen.getByText("Not matched")).toBeInTheDocument();

    // Bob carries two mentees: two rows here, one on the person axis.
    fireEvent.click(screen.getByRole("button", { name: "Pairs" }));
    expect(screen.getAllByText("Liu, Bob")).toHaveLength(2);
    expect(screen.getByText("Mentee reminder")).toBeInTheDocument();

    fireEvent.click(screen.getByRole("button", { name: "Participants" }));
    fireEvent.click(screen.getByRole("button", { name: "Wang, Cara" }));
    expect(screen.getByText("Notes")).toBeInTheDocument();
    expect(screen.getByText("Participation history")).toBeInTheDocument();

    // Feedback always names whose opinion it is.
    expect(screen.getByText(/Wang, Cara's feedback about/)).toBeInTheDocument();

    fireEvent.click(screen.getByRole("button", { name: /With Liu, Bob/ }));
    expect(screen.getByText("Meeting log")).toBeInTheDocument();
    expect(screen.getByText("Notes about this pair")).toBeInTheDocument();
  });

  it("drops whole blocks rather than greying them out when a grant is missing", () => {
    render(<MentorshipAdminPrototype />);

    fireEvent.click(chip("Approve"));
    expect(screen.queryByText("Pending approvals")).not.toBeInTheDocument();

    fireEvent.click(chip("Feedback"));
    fireEvent.click(screen.getByRole("button", { name: "Wang, Cara" }));
    expect(screen.queryByText(/feedback about/)).not.toBeInTheDocument();
  });

  it("raises a request instead of writing the note directly", () => {
    render(<MentorshipAdminPrototype />);

    fireEvent.click(screen.getByRole("button", { name: "Wu, Dana" }));
    fireEvent.click(screen.getByRole("button", { name: "Raise a change" }));
    fireEvent.change(screen.getByRole("textbox"), {
      target: { value: "No reply on either channel." },
    });
    fireEvent.click(screen.getByRole("button", { name: "Send for approval" }));

    // The status has not moved — only a pending request exists.
    expect(screen.getAllByText("signed_up").length).toBeGreaterThan(0);
    fireEvent.click(screen.getByRole("button", { name: "← Participants" }));
    expect(screen.getByText(/3 waiting/)).toBeInTheDocument();
  });
});
