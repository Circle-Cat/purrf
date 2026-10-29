import { describe, it, expect } from "vitest";
import { participantLink } from "@/pages/MentorshipManagement/utils/participantLink";

describe("participantLink", () => {
  it("names the round, and the pair and the request under review when given", () => {
    expect(participantLink(3104, 7)).toEqual({
      pathname: "/mentorship-management/participants/3104",
      search: "?round=7",
    });
    expect(participantLink(3104, 7, 80)).toEqual({
      pathname: "/mentorship-management/participants/3104",
      search: "?round=7&pair=80",
    });
    expect(participantLink(3104, 7, null, 41)).toEqual({
      pathname: "/mentorship-management/participants/3104",
      search: "?round=7&review=41",
    });
  });
});
