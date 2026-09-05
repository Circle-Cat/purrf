import React from "react";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, it, expect, vi } from "vitest";
import "@testing-library/jest-dom";

import PublishDialog from "@/pages/AdminTraining/components/PublishDialog";

describe("PublishDialog", () => {
  it("states all three consequences before publishing", () => {
    render(
      <PublishDialog
        course={{
          courseId: 9,
          packageVersion: "qPpo9zHD",
          unfinishedCount: 3,
          assignedCount: 48,
          liveState: "live",
          staged: { packageVersion: "RaOvlxxJ" },
        }}
        open
        onConfirm={vi.fn()}
        onOpenChange={vi.fn()}
      />,
    );

    expect(
      screen.getByText(/3 learners in progress will restart/),
    ).toBeInTheDocument();
    expect(
      screen.getByText(/45 completed records are untouched/),
    ).toBeInTheDocument();
    expect(
      screen.getByText(/see it stop loading until they reload/),
    ).toBeInTheDocument();
    expect(
      screen.getByText(/qPpo9zHD is deleted and cannot be brought back/),
    ).toBeInTheDocument();
  });

  it("says the staged package replaces the live one, named by version", () => {
    render(
      <PublishDialog
        course={{
          courseId: 9,
          packageVersion: "qPpo9zHD",
          unfinishedCount: 3,
          assignedCount: 48,
          liveState: "live",
          staged: { packageVersion: "RaOvlxxJ" },
        }}
        open
        onConfirm={vi.fn()}
        onOpenChange={vi.fn()}
      />,
    );

    expect(
      screen.getByText("RaOvlxxJ replaces qPpo9zHD for everyone on this course."),
    ).toBeInTheDocument();
  });

  it("says the staged package becomes the course's package when nothing is live yet, and drops the mid-session line", () => {
    render(
      <PublishDialog
        course={{
          courseId: 9,
          packageVersion: null,
          unfinishedCount: 0,
          assignedCount: 0,
          liveState: "no_package",
          staged: { packageVersion: "RaOvlxxJ" },
        }}
        open
        onConfirm={vi.fn()}
        onOpenChange={vi.fn()}
      />,
    );

    expect(
      screen.getByText("RaOvlxxJ becomes the package this course serves."),
    ).toBeInTheDocument();
    expect(
      screen.queryByText(/see it stop loading until they reload/),
    ).not.toBeInTheDocument();
  });

  it("names the staged package without a version when it has none", () => {
    render(
      <PublishDialog
        course={{
          courseId: 9,
          packageVersion: "qPpo9zHD",
          unfinishedCount: 0,
          assignedCount: 0,
          liveState: "live",
          staged: { packageVersion: null },
        }}
        open
        onConfirm={vi.fn()}
        onOpenChange={vi.fn()}
      />,
    );

    expect(
      screen.getByText(
        "the staged package replaces qPpo9zHD for everyone on this course.",
      ),
    ).toBeInTheDocument();
  });

  it("names the outgoing package without a version when it has none", () => {
    render(
      <PublishDialog
        course={{
          courseId: 9,
          packageVersion: null,
          unfinishedCount: 0,
          assignedCount: 0,
          liveState: "live",
          staged: { packageVersion: "RaOvlxxJ" },
        }}
        open
        onConfirm={vi.fn()}
        onOpenChange={vi.fn()}
      />,
    );

    expect(
      screen.getByText(
        "RaOvlxxJ replaces the current package for everyone on this course.",
      ),
    ).toBeInTheDocument();
    expect(
      screen.getByText(
        "the current package is deleted and cannot be brought back.",
      ),
    ).toBeInTheDocument();
  });

  it("confirms and closes through onConfirm, not a local mutation", async () => {
    const onConfirm = vi.fn().mockResolvedValue({});
    render(
      <PublishDialog
        course={{
          courseId: 9,
          packageVersion: "qPpo9zHD",
          unfinishedCount: 3,
          assignedCount: 48,
          liveState: "live",
          staged: { packageVersion: "RaOvlxxJ" },
        }}
        open
        onConfirm={onConfirm}
        onOpenChange={vi.fn()}
      />,
    );

    await userEvent.click(
      screen.getByRole("button", { name: /publish package/i }),
    );

    expect(onConfirm).toHaveBeenCalledTimes(1);
  });

  it("closes without confirming on Cancel", async () => {
    const onOpenChange = vi.fn();
    const onConfirm = vi.fn();
    render(
      <PublishDialog
        course={{
          courseId: 9,
          packageVersion: "qPpo9zHD",
          unfinishedCount: 3,
          assignedCount: 48,
          liveState: "live",
          staged: { packageVersion: "RaOvlxxJ" },
        }}
        open
        onConfirm={onConfirm}
        onOpenChange={onOpenChange}
      />,
    );

    await userEvent.click(screen.getByRole("button", { name: /cancel/i }));

    expect(onOpenChange).toHaveBeenCalledWith(false);
    expect(onConfirm).not.toHaveBeenCalled();
  });
});
