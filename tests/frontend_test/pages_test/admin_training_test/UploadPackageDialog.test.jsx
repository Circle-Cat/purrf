import React from "react";
import { act, render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, it, expect, vi } from "vitest";
import "@testing-library/jest-dom";

import UploadPackageDialog from "@/pages/AdminTraining/components/UploadPackageDialog";

const zipFile = () =>
  new File(["zip-bytes"], "course.zip", { type: "application/zip" });

const pick = async (file) =>
  userEvent.upload(screen.getByLabelText(/scorm package/i), file);

describe("UploadPackageDialog", () => {
  it("says the upload changes nothing for learners", () => {
    // Uploading only stages a package now -- a live course keeps serving
    // its current package until a deliberate publish, so the copy must not
    // claim anyone is disrupted by the upload itself.
    render(
      <UploadPackageDialog
        course={{
          courseId: 5,
          packageVersion: "qPpo9zHD",
          liveState: "live",
          assignedCount: 124,
          unfinishedCount: 3,
        }}
        open
      />,
    );

    expect(
      screen.getByText(/Learners keep seeing qPpo9zHD until you publish it/),
    ).toBeInTheDocument();
    expect(screen.queryByText(/will restart/)).not.toBeInTheDocument();
  });

  it("names the outgoing package only when the package says", () => {
    // A Captivate export carries no driver config, so packageVersion is
    // legitimately null. Name the thing without a version rather than leave
    // a gap in the sentence.
    render(
      <UploadPackageDialog
        course={{
          courseId: 5,
          packageVersion: null,
          liveState: "live",
          assignedCount: 61,
          unfinishedCount: 12,
        }}
        open
      />,
    );

    expect(
      screen.getByText(
        /Learners keep seeing the current package until you publish it/,
      ),
    ).toBeInTheDocument();
  });

  it("says nothing is served yet when the course has no live package", () => {
    render(
      <UploadPackageDialog
        course={{
          courseId: 5,
          packageVersion: null,
          liveState: "no_package",
          assignedCount: 0,
          unfinishedCount: 0,
        }}
        open
      />,
    );

    expect(
      screen.getByText(
        "This course has no package yet. Nothing is served until you publish.",
      ),
    ).toBeInTheDocument();
    expect(screen.queryByText(/will restart/)).not.toBeInTheDocument();
  });

  it("still calls it Replace when the course is live", () => {
    // The row action is still labelled Replace; only what the dialog says
    // about the consequences changed.
    render(
      <UploadPackageDialog
        course={{
          courseId: 5,
          packageVersion: "qPpo9zHD",
          liveState: "live",
          assignedCount: 124,
          unfinishedCount: 3,
        }}
        open
      />,
    );

    expect(
      screen.getByRole("heading", { name: /replace package/i }),
    ).toBeInTheDocument();
    expect(
      screen.getByRole("button", { name: /replace package/i }),
    ).toBeInTheDocument();
  });

  it("promises nothing about keeping the previous files", () => {
    // The old prefix is deleted right after the commit that moves the course
    // onto the new one.
    render(
      <UploadPackageDialog
        course={{
          courseId: 5,
          packageVersion: "qPpo9zHD",
          liveState: "live",
          assignedCount: 124,
          unfinishedCount: 3,
        }}
        open
      />,
    );

    expect(screen.queryByText(/24 hours/i)).not.toBeInTheDocument();
    expect(
      screen.queryByText(/previous files are kept/i),
    ).not.toBeInTheDocument();
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

    expect(onConfirm).toHaveBeenCalledWith(file, expect.any(Function));
    expect(
      await screen.findByText(
        /finishing every rise lesson will not mark this course complete/i,
      ),
    ).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /^done$/i })).toBeInTheDocument();
  });

  it("shows how far the bytes have got while they are still going", async () => {
    const file = zipFile();
    let report;
    // Never settles: the dialog stays in the state it holds mid-transfer.
    const onConfirm = vi.fn((_file, onProgress) => {
      report = onProgress;
      return new Promise(() => {});
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
    act(() => report(42));

    expect(screen.getByRole("progressbar")).toHaveAttribute(
      "aria-valuenow",
      "42",
    );
    expect(screen.getByText("42%")).toBeInTheDocument();
  });

  it("stops counting and says it is checking once the last byte is sent", async () => {
    // The server still has to unzip the archive and store every file in it,
    // and that stretch is not measured by anything. A bar sitting at 100%
    // would claim it were.
    const file = zipFile();
    let report;
    const onConfirm = vi.fn((_file, onProgress) => {
      report = onProgress;
      return new Promise(() => {});
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
    act(() => report(100));

    expect(screen.getByText(/checking package\.\.\./i)).toBeInTheDocument();
    expect(screen.queryByRole("progressbar")).not.toBeInTheDocument();
    expect(screen.queryByText(/100%/)).not.toBeInTheDocument();
  });

  it("shows no bar when the browser cannot tell how big the upload is", async () => {
    // Without a Content-Length there is no total to divide by, so the API
    // layer reports nothing and a determinate bar would be a fabrication.
    const file = zipFile();
    const onConfirm = vi.fn(() => new Promise(() => {}));

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

    expect(screen.queryByRole("progressbar")).not.toBeInTheDocument();
    expect(
      screen.getByRole("button", { name: /uploading\.\.\./i }),
    ).toBeInTheDocument();
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
