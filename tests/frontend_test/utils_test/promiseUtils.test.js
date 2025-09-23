import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import handleMultiplePromises from "@/utils/promiseUtils";

describe("handleMultiplePromises", () => {
  let consoleErrorSpy;
  let consoleWarnSpy;

  beforeEach(() => {
    consoleErrorSpy = vi.spyOn(console, "error").mockImplementation(() => {});
    consoleWarnSpy = vi.spyOn(console, "warn").mockImplementation(() => {});
  });

  afterEach(() => {
    consoleErrorSpy.mockRestore();
    consoleWarnSpy.mockRestore();
  });

  it("should return a flattened array of successful results when all promises resolve", async () => {
    const promises = [
      Promise.resolve([1, 2]),
      Promise.resolve([3]),
      Promise.resolve([4, 5, 6]),
    ];
    const providerNames = ["P1", "P2", "P3"];
    const result = await handleMultiplePromises(promises, providerNames);

    expect(result).toEqual([1, 2, 3, 4, 5, 6]);
    expect(consoleErrorSpy).not.toHaveBeenCalled();
    expect(consoleWarnSpy).not.toHaveBeenCalled();
  });

  it("should return an empty array when all promises reject", async () => {
    const promises = [Promise.reject("Error 1"), Promise.reject("Error 2")];
    const providerNames = ["P1", "P2"];
    const result = await handleMultiplePromises(promises, providerNames);

    expect(result).toEqual([]);
    expect(consoleErrorSpy).toHaveBeenCalledTimes(2);
    expect(consoleErrorSpy).toHaveBeenCalledWith(
      " Failed to fetch data for P1:",
      "Error 1",
    );
    expect(consoleErrorSpy).toHaveBeenCalledWith(
      " Failed to fetch data for P2:",
      "Error 2",
    );
    expect(consoleWarnSpy).toHaveBeenCalledTimes(1);
    expect(consoleWarnSpy).toHaveBeenCalledWith(" Failed providers: P1, P2");
  });

  it("should return a flattened array of successful results and log failures for mixed promises", async () => {
    const promises = [
      Promise.resolve([10]),
      Promise.reject("Error A"),
      Promise.resolve([20, 30]),
      Promise.reject("Error B"),
    ];
    const providerNames = ["ServiceX", "ServiceY", "ServiceZ", "ServiceW"];
    const result = await handleMultiplePromises(promises, providerNames);

    expect(result).toEqual([10, 20, 30]);
    expect(consoleErrorSpy).toHaveBeenCalledTimes(2);
    expect(consoleErrorSpy).toHaveBeenCalledWith(
      " Failed to fetch data for ServiceY:",
      "Error A",
    );
    expect(consoleErrorSpy).toHaveBeenCalledWith(
      " Failed to fetch data for ServiceW:",
      "Error B",
    );
    expect(consoleWarnSpy).toHaveBeenCalledTimes(1);
    expect(consoleWarnSpy).toHaveBeenCalledWith(
      " Failed providers: ServiceY, ServiceW",
    );
  });

  it("should handle an empty array of promises gracefully", async () => {
    const promises = [];
    const providerNames = [];
    const result = await handleMultiplePromises(promises, providerNames);

    expect(result).toEqual([]);
    expect(consoleErrorSpy).not.toHaveBeenCalled();
    expect(consoleWarnSpy).not.toHaveBeenCalled();
  });

  it("should use default provider names when `providerNames` is not provided or is shorter than promises", async () => {
    const promises = [
      Promise.resolve("data1"),
      Promise.reject("Error X"),
      Promise.resolve("data2"),
    ];
    const providerNames = ["NamedProvider"];
    const result = await handleMultiplePromises(promises, providerNames);

    expect(result).toEqual(["data1", "data2"]);
    expect(consoleErrorSpy).toHaveBeenCalledTimes(1);
    expect(consoleErrorSpy).toHaveBeenCalledWith(
      " Failed to fetch data for Provider #1:",
      "Error X",
    );
    expect(consoleWarnSpy).toHaveBeenCalledTimes(1);
    expect(consoleWarnSpy).toHaveBeenCalledWith(
      " Failed providers: Provider #1",
    );
  });

  it("should include logContext in error and warning messages", async () => {
    const promises = [Promise.reject("API Error")];
    const providerNames = ["MyService"];
    const logContext = "[Chat API]";
    const result = await handleMultiplePromises(
      promises,
      providerNames,
      logContext,
    );

    expect(result).toEqual([]);
    expect(consoleErrorSpy).toHaveBeenCalledTimes(1);
    expect(consoleErrorSpy).toHaveBeenCalledWith(
      "[Chat API] Failed to fetch data for MyService:",
      "API Error",
    );
    expect(consoleWarnSpy).toHaveBeenCalledTimes(1);
    expect(consoleWarnSpy).toHaveBeenCalledWith(
      "[Chat API] Failed providers: MyService",
    );
  });

  it("should use an empty logContext by default if not provided", async () => {
    const promises = [Promise.reject("Default Error")];
    const providerNames = ["DefaultService"];
    const result = await handleMultiplePromises(promises, providerNames);

    expect(result).toEqual([]);
    expect(consoleErrorSpy).toHaveBeenCalledTimes(1);
    expect(consoleErrorSpy).toHaveBeenCalledWith(
      " Failed to fetch data for DefaultService:",
      "Default Error",
    );
    expect(consoleWarnSpy).toHaveBeenCalledTimes(1);
    expect(consoleWarnSpy).toHaveBeenCalledWith(
      " Failed providers: DefaultService",
    );
  });
});
