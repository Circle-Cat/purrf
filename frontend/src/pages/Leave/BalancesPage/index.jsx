import { useState } from "react";

import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import AdjustBalanceDialog from "@/pages/Leave/BalancesPage/components/AdjustBalanceDialog";
import { Badge } from "@/components/ui/badge";
import {
  PROFILE_PROBLEMS,
  byProblem,
  negativeByLevel,
} from "@/pages/Leave/BalancesPage/problems";
import { useLeaveBalances } from "@/pages/Leave/hooks/useLeaveBalances";

/** Each way of being left out, and what it takes to fix it. */
const EXCLUSION_GROUPS = [
  {
    key: "unresolved",
    label: "No purrf account",
    fix: "The address in Azure matches no account here.",
  },
  {
    key: "noHireDate",
    label: "No hire date in Azure",
    fix: "Nothing to accrue from until it is filled in.",
  },
  {
    key: "notInternal",
    label: "Not marked internal",
    fix: "The account exists but is not an internal employee.",
  },
  {
    key: "unreadable",
    label: "Unreadable profile",
    fix: "The cached profile could not be parsed. This is a bug.",
  },
  { key: "left", label: "Left", fix: "Accrual has stopped, which is correct." },
];

/**
 * LeaveBalancesPage
 *
 * Every balance the accrual engine maintains, and everybody it is missing.
 *
 * The list is the engine's own population rather than a query of its own, so a
 * name that is on this page is a name the weekly run pays. That matters more
 * than it sounds: the failure this page exists to catch is somebody quietly
 * accruing nothing, and an overview built separately could show them as fine.
 *
 * The exclusion groups are kept apart because each needs a different fix, and
 * the total is shown against the number of directory profiles considered so
 * that a reader does not have to add the lists up and hope they match.
 *
 * Correcting a balance is done from a row, so the person is already chosen.
 *
 * @returns {JSX.Element}
 */
const LeaveBalancesPage = () => {
  const {
    people,
    excluded,
    profileCount,
    isLoading,
    loadError,
    isSaving,
    saveError,
    lastResult,
    clearResult,
    load,
    adjust,
  } = useLeaveBalances();

  const [adjusting, setAdjusting] = useState(null);

  // Grouped for reading, not recomputed: every figure and flag below is one
  // the server sent on the row it belongs to.
  const problemGroups = byProblem(people);
  const negativeGroups = negativeByLevel(people);

  const closeDialog = () => {
    setAdjusting(null);
    clearResult();
  };

  return (
    <div className="space-y-5">
      {isLoading && <p className="text-sm text-muted-foreground">Loading…</p>}

      {!isLoading && loadError && (
        <div className="flex flex-col items-start gap-3">
          <p className="text-sm text-muted-foreground">
            Couldn't load the balances.
          </p>
          <Button onClick={load}>Retry</Button>
        </div>
      )}

      {!isLoading && !loadError && (
        <>
          <Card className="border-gray-200 shadow-sm">
            <CardHeader>
              <CardTitle className="text-lg font-semibold">
                {`Accruing: ${people.length} of ${profileCount} directory profiles`}
              </CardTitle>
            </CardHeader>
            <CardContent>
              {people.length === 0 ? (
                <p className="text-sm text-muted-foreground">
                  Nobody is accruing. If that is unexpected, the nightly sync
                  may not have run.
                </p>
              ) : (
                <ul className="divide-y divide-gray-100">
                  {people.map((person) => (
                    <li
                      key={person.userId}
                      className="flex flex-wrap items-center justify-between gap-3 py-2"
                    >
                      <div className="min-w-0">
                        <p className="m-0 text-sm font-medium">
                          {person.name || "Unknown name"}
                          <span className="font-normal text-muted-foreground">
                            {` (${person.ldap})`}
                          </span>
                        </p>
                        <p className="m-0 text-sm text-muted-foreground">
                          {`${person.level ?? "No level"} · ${person.annualHours} h a year`}
                        </p>
                        {(person.problems ?? []).length > 0 && (
                          <div className="mt-1 flex flex-wrap gap-1">
                            {person.problems.map((problem) => (
                              <Badge key={problem} variant="outline">
                                {PROFILE_PROBLEMS.find(
                                  (known) => known.key === problem,
                                )?.label ?? problem}
                              </Badge>
                            ))}
                          </div>
                        )}
                      </div>
                      <div className="flex items-center gap-3">
                        <span
                          className={`text-base font-semibold tabular-nums ${
                            Number(person.balanceHours) < 0
                              ? "text-rose-600"
                              : ""
                          }`}
                        >
                          {`${person.balanceHours} h`}
                        </span>
                        <Button
                          variant="outline"
                          onClick={() => setAdjusting(person)}
                        >
                          Correct
                        </Button>
                      </div>
                    </li>
                  ))}
                </ul>
              )}
            </CardContent>
          </Card>

          {/* Paid every week and broken anyway. Nothing about the run itself
              mentions these people, which is why they get their own section
              rather than a line in the exclusion lists. */}
          {PROFILE_PROBLEMS.map(({ key, label, consequence }) =>
            (problemGroups[key] ?? []).length === 0 ? null : (
              <Card key={key} className="border-gray-200 shadow-sm">
                <CardHeader>
                  <CardTitle className="text-lg font-semibold">
                    {`${label} — ${problemGroups[key].length}`}
                  </CardTitle>
                </CardHeader>
                <CardContent className="space-y-2">
                  <p className="m-0 text-sm text-muted-foreground">
                    {consequence}
                  </p>
                  <p className="m-0 text-sm">
                    {problemGroups[key]
                      .map((person) => person.name || person.ldap)
                      .join(", ")}
                  </p>
                </CardContent>
              </Card>
            ),
          )}

          {/* Split by level, never one list. An L1 has no entitlement and may
              still take paid leave, so sitting in the red is their expected
              state -- together they would bury everybody whose negative
              balance is a surprise. */}
          {negativeGroups.length > 0 && (
            <Card className="border-gray-200 shadow-sm">
              <CardHeader>
                <CardTitle className="text-lg font-semibold">
                  Below zero
                </CardTitle>
              </CardHeader>
              <CardContent className="space-y-3">
                {negativeGroups.map(({ level, people: group }) => (
                  <div key={level}>
                    <p className="m-0 text-sm font-medium">
                      {`${level} — ${group.length}`}
                      {level === "L1" && (
                        <span className="font-normal text-muted-foreground">
                          {" · expected: no annual entitlement"}
                        </span>
                      )}
                    </p>
                    <p className="m-0 text-sm text-muted-foreground tabular-nums">
                      {group
                        .map(
                          (person) =>
                            `${person.name || person.ldap} ${person.balanceHours} h`,
                        )
                        .join(" · ")}
                    </p>
                  </div>
                ))}
              </CardContent>
            </Card>
          )}

          {EXCLUSION_GROUPS.map(({ key, label, fix }) =>
            (excluded[key] ?? []).length === 0 ? null : (
              <Card key={key} className="border-gray-200 shadow-sm">
                <CardHeader>
                  <CardTitle className="text-lg font-semibold">
                    {`${label} — ${excluded[key].length}`}
                  </CardTitle>
                </CardHeader>
                <CardContent className="space-y-2">
                  <p className="m-0 text-sm text-muted-foreground">{fix}</p>
                  <p className="m-0 text-sm">{excluded[key].join(", ")}</p>
                </CardContent>
              </Card>
            ),
          )}
        </>
      )}

      <AdjustBalanceDialog
        person={adjusting}
        isSaving={isSaving}
        saveError={saveError}
        result={lastResult}
        onClose={closeDialog}
        onSubmit={adjust}
      />
    </div>
  );
};

export default LeaveBalancesPage;
