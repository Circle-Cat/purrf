import { describe, it, expect, vi } from "vitest";
import { render, screen, fireEvent } from "@testing-library/react";
import NotificationFilter from "@/pages/MentorshipManagement/components/email/NotificationFilter";
import {
  NOTIFICATION_STATES,
  stagesForList,
} from "@/pages/MentorshipManagement/components/email/emailLabels";

const trigger = () =>
  screen.getByRole("button", { name: "Notification filter" });
const open = () => fireEvent.keyDown(trigger(), { key: "Enter" });

describe("NotificationFilter", () => {
  it("reads Any notification until both halves are set", () => {
    const { rerender } = render(
      <NotificationFilter
        stages={stagesForList(false)}
        stage=""
        state=""
        onChange={() => {}}
      />,
    );
    expect(trigger()).toHaveTextContent("Any notification");
    rerender(
      <NotificationFilter
        stages={stagesForList(false)}
        stage="midterm_reminder"
        state="not_notified"
        onChange={() => {}}
      />,
    );
    expect(trigger()).toHaveTextContent("Mid-term reminder · Not notified");
  });

  it("picks a state inside a stage", async () => {
    const onChange = vi.fn();
    render(
      <NotificationFilter
        stages={stagesForList(false)}
        stage=""
        state=""
        onChange={onChange}
      />,
    );
    open();
    fireEvent.keyDown(
      await screen.findByRole("menuitem", { name: "Mid-term reminder" }),
      { key: "ArrowRight" },
    );
    fireEvent.click(await screen.findByRole("menuitem", { name: "Scheduled" }));
    expect(onChange).toHaveBeenCalledWith({
      stage: "midterm_reminder",
      state: "scheduled",
    });
  });

  it("Any notification clears both", async () => {
    const onChange = vi.fn();
    render(
      <NotificationFilter
        stages={stagesForList(false)}
        stage="admission"
        state="notified"
        onChange={onChange}
      />,
    );
    open();
    fireEvent.click(
      await screen.findByRole("menuitem", { name: "Any notification" }),
    );
    expect(onChange).toHaveBeenCalledWith({ stage: "", state: "" });
  });

  it("offers only the stages it is given", async () => {
    render(
      <NotificationFilter
        stages={stagesForList(true)}
        stage=""
        state=""
        onChange={() => {}}
      />,
    );
    open();
    await screen.findByRole("menuitem", { name: "New round invitation" });
    const names = screen
      .getAllByRole("menuitem")
      .map((item) => item.textContent);
    expect(names).toEqual([
      "Any notification",
      "New round invitation",
      "Admission & onboarding",
      "Onboarding reminder",
    ]);
  });

  it("lists every stage but the invitation for the registered", () => {
    expect(stagesForList(false).map((s) => s.value)).toEqual([
      "admission",
      "onboarding_reminder",
      "match_result",
      "first_contact_reminder",
      "mentor_check_in",
      "midterm_reminder",
      "final_followup",
      "feedback_invite",
    ]);
    expect(NOTIFICATION_STATES.map((s) => s.label)).toEqual([
      "Not notified",
      "Scheduled",
      "Notified",
    ]);
  });
});
