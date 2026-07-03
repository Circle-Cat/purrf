import { describe, it, expect, vi } from "vitest";
import { render, screen, fireEvent } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import PipelineConfigEditor from "@/pages/Recruiting/postings/PipelineConfigEditor";

const POOL = [{ userId: 7, name: "Ann", email: "ann@x.com" }];
const OWNERS = [
  { userId: 42, name: "Bo", email: "bo@x.com" },
  { userId: 43, name: "Cy", email: "cy@x.com" },
];

const renderEditor = (value, onChange) =>
  render(
    <PipelineConfigEditor
      value={value}
      onChange={onChange}
      interviewPool={POOL}
      jobOwners={OWNERS}
    />,
  );

describe("PipelineConfigEditor", () => {
  it("adds a stage in canonical order when its checkbox is ticked", async () => {
    const user = userEvent.setup();
    const onChange = vi.fn();
    renderEditor({ stages: [] }, onChange);
    await user.click(screen.getByRole("checkbox", { name: "Behavioral" }));
    expect(onChange).toHaveBeenCalledWith({
      stages: [{ stage: "behavioral", rounds: 1, referralSkippable: false }],
    });
  });

  it("edits rounds for an included stage", async () => {
    const onChange = vi.fn();
    renderEditor(
      { stages: [{ stage: "tech", rounds: 1, referralSkippable: false }] },
      onChange,
    );
    fireEvent.change(screen.getByLabelText("tech rounds"), {
      target: { value: "3" },
    });
    expect(onChange).toHaveBeenCalledWith({
      stages: [{ stage: "tech", rounds: 3, referralSkippable: false }],
    });
  });

  it("clamps rounds to >= 1 when user enters 0 or negative", () => {
    const onChange = vi.fn();
    renderEditor(
      { stages: [{ stage: "tech", rounds: 1, referralSkippable: false }] },
      onChange,
    );
    fireEvent.change(screen.getByLabelText("tech rounds"), {
      target: { value: "0" },
    });
    expect(onChange).toHaveBeenCalledWith({
      stages: [{ stage: "tech", rounds: 1, referralSkippable: false }],
    });
  });

  it("shows defaultAssignee only for screening/behavioral and sets it from the pool", async () => {
    const user = userEvent.setup();
    const onChange = vi.fn();
    renderEditor(
      {
        stages: [
          { stage: "recruiter_screening", rounds: 1, referralSkippable: false },
          { stage: "tech", rounds: 1, referralSkippable: false },
        ],
      },
      onChange,
    );
    expect(
      screen.getByRole("combobox", { name: "recruiter_screening assignee" }),
    ).toBeInTheDocument();
    expect(
      screen.queryByRole("combobox", { name: "tech assignee" }),
    ).not.toBeInTheDocument();
    await user.click(
      screen.getByRole("combobox", { name: "recruiter_screening assignee" }),
    );
    await user.click(screen.getByRole("option", { name: /Ann/ }));
    expect(onChange).toHaveBeenCalledWith({
      stages: [
        {
          stage: "recruiter_screening",
          rounds: 1,
          referralSkippable: false,
          defaultAssigneeId: 7,
        },
        { stage: "tech", rounds: 1, referralSkippable: false },
      ],
    });
  });

  it("renders existing owners as chips and adds another from the pool", async () => {
    const user = userEvent.setup();
    const onChange = vi.fn();
    renderEditor({ ownerIds: [42], stages: [] }, onChange);
    expect(screen.getByText("Bo")).toBeInTheDocument();
    await user.click(screen.getByRole("combobox", { name: "Add owner" }));
    await user.click(screen.getByRole("option", { name: /Cy/ }));
    expect(onChange).toHaveBeenCalledWith(
      expect.objectContaining({ ownerIds: [42, 43] }),
    );
  });

  it("falls back to legacy ownerId and removes an owner via chip x", async () => {
    const user = userEvent.setup();
    const onChange = vi.fn();
    renderEditor({ ownerId: 42, stages: [] }, onChange);
    expect(screen.getByText("Bo")).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "Remove owner Bo" }));
    expect(onChange).toHaveBeenCalledWith(
      expect.objectContaining({ ownerIds: [] }),
    );
  });

  it("does not offer an already-selected owner in the add-owner pool", async () => {
    const user = userEvent.setup();
    const onChange = vi.fn();
    renderEditor({ ownerIds: [42, 43], stages: [] }, onChange);
    await user.click(screen.getByRole("combobox", { name: "Add owner" }));
    expect(
      screen.queryByRole("option", { name: /Bo/ }),
    ).not.toBeInTheDocument();
    expect(
      screen.queryByRole("option", { name: /Cy/ }),
    ).not.toBeInTheDocument();
  });
});
