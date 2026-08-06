import { useMemo, useState } from "react";
import { AlertOctagon, AlertTriangle, CheckCircle2 } from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import CalendarAdmin from "@/pages/LeavePrototype/CalendarAdmin";
import {
  COMPANY_HOLIDAYS,
  CONVERSION_HOURS,
  DATA_ISSUE_LABELS,
  LEVEL_POLICY,
  ORG_BALANCES,
  STATUTORY_HOLIDAYS,
} from "@/pages/LeavePrototype/mockData";
import { today } from "@/pages/LeavePrototype/leaveCalc";

/**
 * The yearly policy numbers.
 *
 * Both caps are nullable on purpose: nobody has settled on a figure, and an
 * empty box means no limit rather than zero. Storing them per year and region
 * rather than as constants is deliberate too — when they do change, it will be
 * because a year's policy changed.
 *
 * @param {object} props
 * @param {object} props.policy
 * @param {(policy: object) => void} props.onChange
 * @returns {JSX.Element}
 */
const PolicyAdmin = ({ policy, onChange }) => {
  const set = (key, value) => onChange({ ...policy, [key]: value });

  return (
    <div className="space-y-4">
      <Card className="p-5 space-y-4">
        <div>
          <h3 className="text-sm font-semibold text-slate-900">
            Annual entitlement
          </h3>
          <p className="text-xs text-slate-500 mt-0.5">
            Hours per year. Level leave depends only on the level; the
            conversion entitlement depends only on the region, so everyone gets
            it — including levels with no level leave of their own.
          </p>
        </div>

        <div className="grid grid-cols-2 sm:grid-cols-5 gap-4">
          {["L1", "L2", "L3", "L4"].map((level) => (
            <div key={level} className="space-y-1.5">
              <Label htmlFor={`policy-${level}`}>{level}</Label>
              <Input
                id={`policy-${level}`}
                type="number"
                step="8"
                value={policy.levels[level]}
                onChange={(e) =>
                  onChange({
                    ...policy,
                    levels: {
                      ...policy.levels,
                      [level]: Number(e.target.value),
                    },
                  })
                }
              />
            </div>
          ))}
          <div className="space-y-1.5">
            <Label htmlFor="policy-conversion">Conversion</Label>
            <Input
              id="policy-conversion"
              type="number"
              step="8"
              value={policy.conversionHours}
              onChange={(e) => set("conversionHours", Number(e.target.value))}
            />
          </div>
        </div>
      </Card>

      <Card className="p-5 space-y-4">
        <div>
          <h3 className="text-sm font-semibold text-slate-900">Limits</h3>
          <p className="text-xs text-slate-500 mt-0.5">
            Leave either box empty for no limit, which is where both start.
          </p>
        </div>

        <div className="grid sm:grid-cols-2 gap-4">
          <div className="space-y-1.5">
            <Label htmlFor="policy-carryover">Carry-over cap</Label>
            <Input
              id="policy-carryover"
              type="number"
              placeholder="No limit"
              value={policy.carryoverCap ?? ""}
              onChange={(e) =>
                set(
                  "carryoverCap",
                  e.target.value === "" ? null : Number(e.target.value),
                )
              }
            />
            <p className="text-xs text-slate-400">
              Balance carries between years untouched while this is empty.
            </p>
          </div>
          <div className="space-y-1.5">
            <Label htmlFor="policy-overdraft">Overdraft cap</Label>
            <Input
              id="policy-overdraft"
              type="number"
              placeholder="No limit"
              value={policy.overdraftCap ?? ""}
              onChange={(e) =>
                set(
                  "overdraftCap",
                  e.target.value === "" ? null : Number(e.target.value),
                )
              }
            />
            <p className="text-xs text-slate-400">
              Requests past the balance are flagged, not blocked, until this has
              a number in it.
            </p>
          </div>
        </div>
      </Card>
    </div>
  );
};

/**
 * The data-health panel.
 *
 * "No manager" is deliberately separated from the other field problems: those
 * people cannot submit any request at all, including sick leave, so the list
 * is a queue of blocked colleagues rather than a tidiness report.
 *
 * @param {{people: Array<object>}} props
 * @returns {JSX.Element}
 */
const DataHealth = ({ people }) => {
  const grouped = useMemo(() => {
    const out = { no_manager: [], unparsable_title: [], missing_hire_date: [] };
    for (const p of people) {
      if (p.dataIssue) out[p.dataIssue].push(p);
    }
    return out;
  }, [people]);

  const total = Object.values(grouped).reduce((n, list) => n + list.length, 0);

  if (total === 0) {
    return (
      <Card className="p-10 text-center">
        <CheckCircle2 size={28} className="mx-auto text-emerald-500" />
        <p className="text-sm text-slate-600 mt-3">
          Every employee record resolved cleanly.
        </p>
      </Card>
    );
  }

  return (
    <div className="space-y-4">
      <p className="text-sm text-slate-500">
        Employment data is read from Azure and never stored here, so anything
        missing there shows up as a problem here. This list is the fix-it queue
        for HR and IT.
      </p>

      {Object.entries(grouped)
        .filter(([, list]) => list.length > 0)
        .sort(
          ([a], [b]) =>
            (DATA_ISSUE_LABELS[b].severity === "critical") -
            (DATA_ISSUE_LABELS[a].severity === "critical"),
        )
        .map(([key, list]) => {
          const meta = DATA_ISSUE_LABELS[key];
          const critical = meta.severity === "critical";
          const Icon = critical ? AlertOctagon : AlertTriangle;
          return (
            <Card
              key={key}
              className={`p-4 border-l-4 ${
                critical ? "border-l-rose-500" : "border-l-amber-400"
              }`}
            >
              <div className="flex items-start gap-2.5">
                <Icon
                  size={16}
                  className={`mt-0.5 shrink-0 ${
                    critical ? "text-rose-500" : "text-amber-500"
                  }`}
                />
                <div className="min-w-0 flex-1">
                  <div className="flex items-center gap-2">
                    <h3 className="text-sm font-semibold text-slate-900">
                      {meta.title}
                    </h3>
                    <Badge
                      variant="outline"
                      className={`text-xs ${
                        critical
                          ? "bg-rose-50 text-rose-700 border-rose-200"
                          : "bg-amber-50 text-amber-800 border-amber-200"
                      }`}
                    >
                      {list.length}
                    </Badge>
                  </div>
                  <p className="text-xs text-slate-500 mt-0.5">{meta.blurb}</p>
                  <ul className="mt-2.5 flex flex-wrap gap-1.5">
                    {list.map((p) => (
                      <li
                        key={p.id}
                        className="text-xs bg-slate-100 text-slate-700 rounded px-2 py-1"
                      >
                        {p.name}
                      </li>
                    ))}
                  </ul>
                </div>
              </div>
            </Card>
          );
        })}
    </div>
  );
};

/**
 * AdminView
 *
 * Everything gated behind the single new permission. Three jobs: see where the
 * data is broken, see everyone's balance, and correct a balance by hand when
 * something needs correcting.
 *
 * @param {object} props
 * @param {Array<object>} props.adjustments - manual rows written this session
 * @param {(row: object) => void} props.onAdjust
 * @returns {JSX.Element}
 */
const AdminView = ({ adjustments, onAdjust }) => {
  const [personId, setPersonId] = useState("");
  const [entryType, setEntryType] = useState("manual_adjustment");
  const [hours, setHours] = useState("");
  const [note, setNote] = useState("");

  // The calendar and policy are edited here but not shared with the employee
  // view: the calculator reads its holidays at module load, and threading a
  // live calendar through it would be a refactor that buys this prototype
  // nothing. Editing here shows the admin screen doing its job; it does not
  // reprice Dana's balance on the other tab.
  const [company, setCompany] = useState(COMPANY_HOLIDAYS);
  const [statutory, setStatutory] = useState(STATUTORY_HOLIDAYS);
  const [policy, setPolicy] = useState({
    levels: { ...LEVEL_POLICY },
    conversionHours: CONVERSION_HOURS,
    carryoverCap: null,
    overdraftCap: null,
  });

  /** Opening balance is a one-off per person, so block a second one. */
  const alreadyHasOpening = (id) =>
    adjustments.some(
      (a) => a.personId === Number(id) && a.entryType === "opening_balance",
    );

  const parsedHours = Number(hours);
  const hoursValid = hours !== "" && !Number.isNaN(parsedHours);
  const duplicateOpening =
    entryType === "opening_balance" && personId && alreadyHasOpening(personId);
  const canSubmit =
    personId && hoursValid && note.trim().length > 0 && !duplicateOpening;

  const submit = () => {
    if (!canSubmit) return;
    const person = ORG_BALANCES.find((p) => p.id === Number(personId));
    onAdjust({
      id: Date.now(),
      personId: Number(personId),
      personName: person.name,
      entryType,
      hours: parsedHours,
      note: note.trim(),
      effectiveDate: today(),
    });
    setHours("");
    setNote("");
  };

  /** Session adjustments folded into the seeded balances. */
  const balances = ORG_BALANCES.map((p) => ({
    ...p,
    balance:
      p.balance +
      adjustments
        .filter((a) => a.personId === p.id)
        .reduce((s, a) => s + a.hours, 0),
  }));

  return (
    <div className="p-6 space-y-4 max-w-5xl">
      <header>
        <h1 className="text-xl font-semibold text-slate-900">Administration</h1>
        <p className="text-sm text-slate-500 mt-0.5">
          Requires the leave administrator permission.
        </p>
      </header>

      <Tabs defaultValue="calendar">
        <TabsList>
          <TabsTrigger value="calendar">Calendar</TabsTrigger>
          <TabsTrigger value="policy">Policy</TabsTrigger>
          <TabsTrigger value="health">Data health</TabsTrigger>
          <TabsTrigger value="balances">Balances</TabsTrigger>
          <TabsTrigger value="adjust">Adjust a balance</TabsTrigger>
        </TabsList>

        <TabsContent value="calendar" className="mt-4">
          <CalendarAdmin
            company={company}
            statutory={statutory}
            conversionHours={policy.conversionHours}
            onCompanyChange={setCompany}
            onStatutoryChange={setStatutory}
          />
        </TabsContent>

        <TabsContent value="policy" className="mt-4">
          <PolicyAdmin policy={policy} onChange={setPolicy} />
        </TabsContent>

        <TabsContent value="health" className="mt-4">
          <DataHealth people={ORG_BALANCES} />
        </TabsContent>

        <TabsContent value="balances" className="mt-4">
          <Card className="p-0 overflow-x-auto">
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Name</TableHead>
                  <TableHead>Level</TableHead>
                  <TableHead>Manager</TableHead>
                  <TableHead className="text-right">Balance</TableHead>
                  <TableHead className="text-right">Reserved</TableHead>
                  <TableHead className="text-right">Available</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {balances.map((p) => (
                  <TableRow key={p.id}>
                    <TableCell className="font-medium">
                      <div className="flex items-center gap-2">
                        {p.name}
                        {p.dataIssue === "no_manager" && (
                          <Badge
                            variant="outline"
                            className="text-xs bg-rose-50 text-rose-700 border-rose-200"
                          >
                            Blocked
                          </Badge>
                        )}
                      </div>
                    </TableCell>
                    <TableCell className="text-slate-500">
                      {p.level ?? "—"}
                    </TableCell>
                    <TableCell className="text-slate-500">
                      {p.manager}
                    </TableCell>
                    <TableCell className="text-right tabular-nums">
                      {p.balance.toFixed(2)}h
                    </TableCell>
                    <TableCell className="text-right tabular-nums text-slate-500">
                      {p.pending ? `${p.pending.toFixed(2)}h` : "—"}
                    </TableCell>
                    <TableCell
                      className={`text-right tabular-nums font-medium ${
                        p.balance - p.pending < 0 ? "text-rose-600" : ""
                      }`}
                    >
                      {(p.balance - p.pending).toFixed(2)}h
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          </Card>
        </TabsContent>

        <TabsContent value="adjust" className="mt-4 space-y-4">
          <Card className="p-5 space-y-4">
            <div className="grid sm:grid-cols-3 gap-4">
              <div className="space-y-1.5">
                <Label htmlFor="adjust-person">Person</Label>
                <Select value={personId} onValueChange={setPersonId}>
                  <SelectTrigger id="adjust-person">
                    <SelectValue placeholder="Pick someone" />
                  </SelectTrigger>
                  <SelectContent>
                    {ORG_BALANCES.map((p) => (
                      <SelectItem key={p.id} value={String(p.id)}>
                        {p.name}
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </div>

              <div className="space-y-1.5">
                <Label htmlFor="adjust-type">Entry type</Label>
                <Select value={entryType} onValueChange={setEntryType}>
                  <SelectTrigger id="adjust-type">
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="manual_adjustment">
                      Manual adjustment
                    </SelectItem>
                    <SelectItem value="opening_balance">
                      Opening balance (migration)
                    </SelectItem>
                  </SelectContent>
                </Select>
              </div>

              <div className="space-y-1.5">
                <Label htmlFor="adjust-hours">Hours</Label>
                <Input
                  id="adjust-hours"
                  type="number"
                  step="0.25"
                  value={hours}
                  placeholder="e.g. -4 or 12.5"
                  onChange={(e) => setHours(e.target.value)}
                />
              </div>
            </div>

            <div className="space-y-1.5">
              <Label htmlFor="adjust-note">Note (required)</Label>
              <Textarea
                id="adjust-note"
                rows={2}
                value={note}
                placeholder="Why this correction exists. Stored with your name against the row."
                onChange={(e) => setNote(e.target.value)}
              />
            </div>

            {entryType === "opening_balance" && (
              <div className="rounded-lg bg-slate-50 border border-slate-200 p-3 text-sm text-slate-600">
                Opening balance carries everything a person had before the
                system went live. One row per person, entered once — the accrual
                engine ignores it when working out what is still owed, so it
                will not eat into their weekly accrual.
              </div>
            )}

            {duplicateOpening && (
              <div className="rounded-lg bg-rose-50 border border-rose-200 p-3 text-sm text-rose-800">
                This person already has an opening balance. Correct it with a
                manual adjustment instead.
              </div>
            )}

            <Button onClick={submit} disabled={!canSubmit}>
              Write ledger entry
            </Button>
          </Card>

          {adjustments.length > 0 && (
            <Card className="p-5">
              <h2 className="text-sm font-semibold text-slate-900 mb-3">
                Written this session
              </h2>
              <ul className="divide-y divide-slate-100">
                {adjustments.map((a) => (
                  <li key={a.id} className="py-2.5 text-sm">
                    <div className="flex items-center justify-between gap-4">
                      <span className="text-slate-900">
                        {a.personName}
                        <span className="text-slate-400 ml-2 text-xs">
                          {a.entryType === "opening_balance"
                            ? "opening balance"
                            : "manual adjustment"}
                        </span>
                      </span>
                      <span
                        className={`tabular-nums font-medium ${
                          a.hours < 0 ? "text-rose-600" : "text-emerald-700"
                        }`}
                      >
                        {a.hours > 0 ? "+" : ""}
                        {a.hours}h
                      </span>
                    </div>
                    <p className="text-xs text-slate-500 mt-0.5">{a.note}</p>
                  </li>
                ))}
              </ul>
              <p className="text-xs text-slate-400 mt-3 pt-3 border-t border-slate-100">
                Ledger rows are only ever added, never edited or deleted. A
                mistake is corrected by writing the opposite row.
              </p>
            </Card>
          )}
        </TabsContent>
      </Tabs>
    </div>
  );
};

export default AdminView;
