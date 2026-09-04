import { vi, describe, it, expect, beforeEach } from "vitest";
import request from "@/utils/request";
import { uploadPackage } from "@/api/trainingApi";
import { API_ENDPOINTS } from "@/constants/ApiEndpoints";

vi.mock("@/utils/request", () => {
  return {
    default: {
      get: vi.fn(),
      post: vi.fn(),
      patch: vi.fn(),
    },
  };
});

/** The axios upload-progress config uploadPackage handed to the request. */
const sentProgressHandler = () =>
  request.post.mock.calls[0][2].onUploadProgress;

describe("uploadPackage", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    request.post.mockResolvedValue({ data: {} });
  });

  it("posts the file to the course's package endpoint", async () => {
    const file = new File(["zip"], "course.zip");

    await uploadPackage(5, file);

    const [url, body] = request.post.mock.calls[0];
    expect(url).toBe(API_ENDPOINTS.TRAINING_COURSE_PACKAGE(5));
    expect(body.get("file")).toBe(file);
  });

  it("reports how much of the archive has reached the server, as a percentage", async () => {
    const reached = [];

    await uploadPackage(5, new File(["zip"], "course.zip"), (percent) =>
      reached.push(percent),
    );
    sentProgressHandler()({ loaded: 4_000_000, total: 16_000_000 });
    sentProgressHandler()({ loaded: 16_000_000, total: 16_000_000 });

    expect(reached).toEqual([25, 100]);
  });

  it("rounds to a whole percent", async () => {
    const reached = [];

    await uploadPackage(5, new File(["zip"], "course.zip"), (percent) =>
      reached.push(percent),
    );
    sentProgressHandler()({ loaded: 1, total: 3 });

    expect(reached).toEqual([33]);
  });

  it("reports nothing when the browser cannot say how big the upload is", async () => {
    // No Content-Length means no total to divide by. Staying silent lets the
    // caller fall back to an indeterminate wait rather than draw a bar off a
    // number nobody knows.
    const onProgress = vi.fn();

    await uploadPackage(5, new File(["zip"], "course.zip"), onProgress);
    sentProgressHandler()({ loaded: 4_000_000, total: undefined });

    expect(onProgress).not.toHaveBeenCalled();
  });

  it("does not break mid-upload when the caller wants no progress at all", async () => {
    await uploadPackage(5, new File(["zip"], "course.zip"));

    // Whether a handler is installed at all is the implementation's choice;
    // one that is installed and then calls a callback nobody passed would
    // throw partway through a 16 MB upload.
    expect(() =>
      sentProgressHandler()?.({ loaded: 1, total: 2 }),
    ).not.toThrow();
  });
});
