import { describe, expect, it } from "vitest";
import { addressNote, serviceOf } from "@/pages/Inbox/inboxDisplay";

describe("addressNote", () => {
  it("names the address a service's mail was sent to", () => {
    expect(addressNote("mentorship", "mentorship@circlecat.org")).toEqual({
      before: "Mail sent to ",
      address: "mentorship@circlecat.org",
      after: ".",
    });
  });

  it("says Unsorted holds mail sent straight to the mailbox", () => {
    expect(addressNote("unsorted", "purrf@circlecat.org")).toEqual({
      before: "Mail sent straight to ",
      address: "purrf@circlecat.org",
      after: ", not to any service address.",
    });
  });

  it("is null without an address", () => {
    expect(addressNote("recruiting", null)).toBeNull();
    expect(addressNote("recruiting", undefined)).toBeNull();
    expect(addressNote("unsorted", "")).toBeNull();
  });
});

describe("serviceOf", () => {
  it("labels the inquiries service Contact", () => {
    expect(serviceOf("inquiries").label).toBe("Contact");
  });
});
