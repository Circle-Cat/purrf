import { describe, it, expect, vi, beforeEach } from "vitest";
import axios from "axios";

vi.mock("axios", () => ({
  default: {
    create: vi.fn(() => ({
      interceptors: {
        response: { use: vi.fn() },
        request: { use: vi.fn() },
      },
    })),
  },
}));

describe("request Axios instance", () => {
  let request;

  beforeEach(async () => {
    vi.resetModules();
    request = (await import("../../../frontend/src/utils/request.js")).default;
  });

  it("should create axios instance with 10s timeout", () => {
    expect(axios.create).toHaveBeenCalledWith({
      baseURL: "/api",
      timeout: 10000,
      withCredentials: true,
    });
  });

  it("should return response.data", () => {
    const mockData = { foo: "bar" };
    const successHandler = request.interceptors.response.use.mock.calls[0][0];
    const result = successHandler({ data: mockData });

    expect(result).toEqual(mockData);
  });

  it("should log detailed error in DEV mode", () => {
    import.meta.env.DEV = true;
    vi.spyOn(console, "error").mockImplementation(() => {});
    const errorHandler = request.interceptors.response.use.mock.calls[0][1];
    const mockError = {
      response: { status: 404, data: { message: "Not Found" } },
      config: { url: "/test" },
      message: "Request failed",
    };

    return errorHandler(mockError).catch(() => {
      expect(console.error).toHaveBeenCalledWith(
        "API Error:",
        expect.objectContaining({
          status: 404,
          url: "/test",
          message: "Not Found",
          fullError: mockError,
        }),
      );
    });
  });

  it("should log only API Error in production", () => {
    import.meta.env.DEV = false;
    vi.spyOn(console, "error").mockImplementation(() => {});
    const errorHandler = request.interceptors.response.use.mock.calls[0][1];
    const mockError = {
      response: { status: 404, data: { message: "Not Found" } },
      config: { url: "/test" },
      message: "Request failed",
    };

    return errorHandler(mockError).catch(() => {
      expect(console.error).toHaveBeenCalledWith(
        "API Error:",
        expect.objectContaining({
          status: 404,
          url: "/test",
          message: "Not Found",
        }),
      );
    });
  });

  it("should handle errors without response object gracefully", () => {
    import.meta.env.DEV = false;
    vi.spyOn(console, "error").mockImplementation(() => {});
    const errorHandler = request.interceptors.response.use.mock.calls[0][1];
    const mockError = {
      message: "Network Error",
      config: { url: "/test" },
    };

    return errorHandler(mockError).catch(() => {
      expect(console.error).toHaveBeenCalledWith(
        "API Error:",
        expect.objectContaining({
          status: "Unknown status",
          url: "/test",
          message: "Network Error",
        }),
      );
    });
  });

  it("should use error.message when response data has no message field", () => {
    import.meta.env.DEV = true;
    vi.spyOn(console, "error").mockImplementation(() => {});
    const errorHandler = request.interceptors.response.use.mock.calls[0][1];
    const mockError = {
      response: { status: 500, data: {} },
      config: { url: "/test" },
      message: "Request failed with status code 500",
    };

    return errorHandler(mockError).catch(() => {
      expect(console.error).toHaveBeenCalledWith(
        "API Error:",
        expect.objectContaining({
          status: 500,
          url: "/test",
          message: "Request failed with status code 500",
        }),
      );
    });
  });
});
