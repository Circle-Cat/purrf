import React from "react";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, it, expect, vi } from "vitest";
import "@testing-library/jest-dom";

import UploadPackageDialog from "@/pages/AdminTraining/components/UploadPackageDialog";

const zipFile = () =>
  new File(["zip-bytes"], "course.zip", { type: "application/zip" });

const pick = async (file) =>
  userEvent.upload(screen.getByLabelText(/scorm package/i), file);

describe("UploadPackageDialog", () => {
  it("says what replacing costs, with numbers, before the click", () => {
    render(
      <UploadPackageDialog
        course={{
          courseId: 5,
          state: "verified",
          packageVersion: "qPpo9zHD",
          packageUploadedAt: "2026-08-20T00:00:00Z",
          assignedCount: 124,
          unfinishedCount: 3,
        }}
        open
      />,
    );

    expect(
      screen.getByText(/this replaces package qPpo9zHD/i),
    ).toBeInTheDocument();
    expect(screen.getByText(/verification is cleared/i)).toBeInTheDocument();
    expect(
      screen.getByText(
        /3 learners in progress will restart from the beginning/i,
      ),
    ).toBeInTheDocument();
    expect(
      screen.getByText(/121 completed records are untouched/i),
    ).toBeInTheDocument();
    expect(
      screen.getByRole("button", { name: /replace package/i }),
    ).toBeInTheDocument();
  });

  it("counts heads for a replacement whose package we cannot read", () => {
    // A Captivate export carries no driver config, so packageVersion is
    // legitimately null. That is the package we understand least, and the
    // consequences of replacing it are exactly the same.
    render(
      <UploadPackageDialog
        course={{
          courseId: 5,
          state: "verified",
          packageVersion: null,
          packageUploadedAt: "2026-08-20T00:00:00Z",
          assignedCount: 61,
          unfinishedCount: 12,
        }}
        open
      />,
    );

    expect(
      screen.getByRole("heading", { name: /replace package/i }),
    ).toBeInTheDocument();
    expect(screen.getByText(/verification is cleared/i)).toBeInTheDocument();
    expect(
      screen.getByText(
        /12 learners in progress will restart from the beginning/i,
      ),
    ).toBeInTheDocument();
    expect(
      screen.getByText(/49 completed records are untouched/i),
    ).toBeInTheDocument();
  });

  it("names the package it replaces only when the package says", () => {
    render(
      <UploadPackageDialog
        course={{
          courseId: 5,
          state: "verified",
          packageVersion: null,
          packageUploadedAt: "2026-08-20T00:00:00Z",
          assignedCount: 61,
          unfinishedCount: 12,
        }}
        open
      />,
    );

    expect(
      screen.getByText(/this replaces the current package/i),
    ).toBeInTheDocument();
  });

  it("promises nothing about keeping the previous files", () => {
    // The old prefix is deleted right after the commit that moves the course
    // onto the new one.
    render(
      <UploadPackageDialog
        course={{
          courseId: 5,
          state: "verified",
          packageVersion: "qPpo9zHD",
          packageUploadedAt: "2026-08-20T00:00:00Z",
          assignedCount: 124,
          unfinishedCount: 3,
        }}
        open
      />,
    );

    expect(screen.queryByText(/24 hours/i)).not.toBeInTheDocument();
    expect(screen.queryByText(/previous files are kept/i)).not.toBeInTheDocument();
  });

  it("calls the first upload Upload, not Replace", () => {
    render(
      <UploadPackageDialog
        course={{
          courseId: 5,
          packageVersion: null,
          assignedCount: 0,
          unfinishedCount: 0,
        }}
        open
      />,
    );

    expect(
      screen.getByRole("button", { name: /^upload/i }),
    ).toBeInTheDocument();
  });

  it("disables submit until a package file is chosen", () => {
    render(
      <UploadPackageDialog
        course={{
          courseId: 5,
          packageVersion: null,
          assignedCount: 0,
          unfinishedCount: 0,
        }}
        open
        onConfirm={vi.fn()}
      />,
    );

    expect(screen.getByRole("button", { name: /^upload/i })).toBeDisabled();
  });

  it("uploads the chosen file and renders the health box from the response, then offers Done", async () => {
    const file = zipFile();
    const onConfirm = vi.fn().mockResolvedValue({
      completionConfigReadable: true,
      completesViaStoryline: true,
      completionPercentage: 100,
    });

    render(
      <UploadPackageDialog
        course={{
          courseId: 5,
          packageVersion: null,
          assignedCount: 0,
          unfinishedCount: 0,
        }}
        open
        onConfirm={onConfirm}
      />,
    );

    await pick(file);
    await userEvent.click(screen.getByRole("button", { name: /^upload/i }));

    expect(onConfirm).toHaveBeenCalledWith(file);
    expect(
      await screen.findByText(
        /finishing every rise lesson will not mark this course complete/i,
      ),
    ).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /^done$/i })).toBeInTheDocument();
  });

  it("shows a rejection message verbatim, not a paraphrase, and leaves Upload on screen", async () => {
    const file = zipFile();
    const rejection = new Error(
      "This is a SCORM 2004 package. Only SCORM 1.2 is supported. Ask whoever exported it to publish for SCORM 1.2 instead.",
    );
    const onConfirm = vi.fn().mockRejectedValue(rejection);

    render(
      <UploadPackageDialog
        course={{
          courseId: 5,
          packageVersion: null,
          assignedCount: 0,
          unfinishedCount: 0,
        }}
        open
        onConfirm={onConfirm}
      />,
    );

    await pick(file);
    await userEvent.click(screen.getByRole("button", { name: /^upload/i }));

    expect(
      await screen.findByText(/only scorm 1\.2 is supported/i),
    ).toBeInTheDocument();
    expect(screen.queryByText(/invalid package/i)).not.toBeInTheDocument();
    expect(
      screen.getByRole("button", { name: /^upload/i }),
    ).toBeInTheDocument();
  });
});
