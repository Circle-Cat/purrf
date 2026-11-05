import { describe, it, expect } from "vitest";

import {
  PROFILE_PROBLEMS,
  byProblem,
  negativeByLevel,
} from "@/pages/Leave/BalancesPage/problems";

const person = (overrides = {}) => ({
  userId: 10,
  ldap: "ann",
  name: "Ann Employee",
  level: "L3",
  annualHours: 80,
  balanceHours: "72.00",
  problems: [],
  ...overrides,
});

describe("PROFILE_PROBLEMS", () => {
  it("leaves out the gap that already excludes somebody", () => {
    // Somebody with no hire date is excluded from the run, so they never
    // appear on a row here and the exclusion list already names them. Listing
    // it in both places would report them twice.
    expect(PROFILE_PROBLEMS.map((problem) => problem.key)).toEqual([
      "missing_manager",
      "unparseable_job_title",
    ]);
  });

  it("says what each gap costs the person, not just that it exists", () => {
    for (const problem of PROFILE_PROBLEMS) {
      expect(problem.consequence.length).toBeGreaterThan(0);
    }
  });
});

describe("byProblem", () => {
  it("gathers everybody carrying one gap", () => {
    const grouped = byProblem([
      person({ ldap: "ann", problems: ["missing_manager"] }),
      person({ ldap: "bob", problems: ["missing_manager"] }),
      person({ ldap: "carol", problems: [] }),
    ]);

    expect(grouped.missing_manager.map((row) => row.ldap)).toEqual([
      "ann",
      "bob",
    ]);
    expect(grouped.unparseable_job_title).toBeUndefined();
  });

  it("puts somebody with two gaps in both", () => {
    const grouped = byProblem([
      person({ problems: ["missing_manager", "unparseable_job_title"] }),
    ]);

    expect(grouped.missing_manager).toHaveLength(1);
    expect(grouped.unparseable_job_title).toHaveLength(1);
  });

  it("copes with a row carrying no problems field at all", () => {
    const { problems: _dropped, ...withoutField } = person();

    expect(byProblem([withoutField])).toEqual({});
  });
});

describe("negativeByLevel", () => {
  it("splits the red by level rather than listing it together", () => {
    // An L1 has no entitlement and may still take paid leave, so sitting in
    // the red is their expected state. In one list they would bury everybody
    // whose negative balance is a surprise.
    const groups = negativeByLevel([
      person({ ldap: "ann", level: "L1", balanceHours: "-24.00" }),
      person({ ldap: "bob", level: "L3", balanceHours: "-8.00" }),
      person({ ldap: "carol", level: "L1", balanceHours: "-16.00" }),
      person({ ldap: "dave", level: "L3", balanceHours: "40.00" }),
    ]);

    expect(groups).toHaveLength(2);
    expect(groups[0].level).toBe("L1");
    expect(groups[0].people.map((row) => row.ldap)).toEqual(["ann", "carol"]);
    expect(groups[1].level).toBe("L3");
    expect(groups[1].people.map((row) => row.ldap)).toEqual(["bob"]);
  });

  it("leaves out a balance of exactly zero", () => {
    expect(negativeByLevel([person({ balanceHours: "0.00" })])).toEqual([]);
  });

  it("gives somebody with no level a group of their own", () => {
    const groups = negativeByLevel([
      person({ level: null, balanceHours: "-8.00" }),
    ]);

    expect(groups[0].level).toBe("No level");
  });
});
