import { useMemo, useState } from "react";
import { AlertOctagon, AlertTriangle, CheckCircle2, Gift } from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
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
import AdjustDialog from "@/pages/LeavePrototype/AdjustDialog";
import {
  COMPANY_HOLIDAYS,
  DATA_ISSUE_LABELS,
  INTL_COMPANY_HOLIDAYS,
  ORG_BALANCES,
  REGIONS,
} from "@/pages/LeavePrototype/mockData";

/**
 * The data-health panel.
 *
 * "No manager" is separated from the other field problems because those people
 * cannot submit anything at all, including sick leave — a queue of blocked
 * colleagues rather than a tidiness report.
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
    <div className="space-y-3">
      <p className="text-sm text-slate-500">
        Employment data is read from Azure and never stored here, so anything
        missing there shows up as a problem here.
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
                  <ul className="mt-2 flex flex-wrap gap-1.5">
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
 * Everything behind the single new permission, in three places: the yearly
 * setup, everyone's balance, and the list of records Azure could not resolve.
 *
 * Adjusting a balance is not a section of its own — it opens from the person's
 * row, which is where you were when you decided to.
 *
 * @param {object} props
 * @param {Array<object>} props.adjustments - manual rows written this session
 * @param {(row: object) => void} props.onAdjust
 * @returns {JSX.Element}
 */
const AdminView = ({ adjustments, onAdjust }) => {
  const [adjusting, setAdjusting] = useState(null);
  const [dialogOpen, setDialogOpen] = useState(false);

  // Per region, because a region is created the day someone is hired into it
  // and needs its own calendars and figures from that moment. Level
  // entitlement is global and lives in code, so it is not here.
  const [region, setRegion] = useState("CN");
  const [calendars, setCalendars] = useState({
    CN: COMPANY_HOLIDAYS,
    INTL: INTL_COMPANY_HOLIDAYS,
  });
  const [settings, setSettings] = useState({
    CN: { ...REGIONS.CN },
    INTL: { ...REGIONS.INTL },
  });
  const [allowanceUsed, setAllowanceUsed] = useState({});

  /** One dialog writes rows for one person or a whole region. */
  const writeRows = (rows, countsAgainstAllowance) => {
    rows.forEach(onAdjust);
    if (countsAgainstAllowance) {
      setAllowanceUsed((prev) => {
        const next = { ...prev };
        for (const r of rows) {
          next[r.personId] = (next[r.personId] ?? 0) + r.hours;
        }
        return next;
      });
    }
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

      <AdjustDialog
        open={dialogOpen}
        onOpenChange={(next) => {
          setDialogOpen(next);
          if (!next) setAdjusting(null);
        }}
        person={adjusting}
        people={balances}
        balanceOf={(id) => balances.find((p) => p.id === id)?.balance ?? 0}
        allowanceUsedBy={(id) => allowanceUsed[id] ?? 0}
        allowanceFor={(r) => settings[r]?.holidayGrantAllowance ?? 0}
        onSubmit={writeRows}
      />

      <Tabs defaultValue="year">
        <TabsList>
          <TabsTrigger value="year">Yearly setup</TabsTrigger>
          <TabsTrigger value="balances">Balances</TabsTrigger>
          <TabsTrigger value="health">Data health</TabsTrigger>
        </TabsList>

        <TabsContent value="year" className="mt-4">
          <CalendarAdmin
            region={region}
            onRegionChange={setRegion}
            settings={settings[region]}
            onSettingsChange={(next) =>
              setSettings((prev) => ({ ...prev, [region]: next }))
            }
            company={calendars[region]}
            onCompanyChange={(rows) =>
              setCalendars((prev) => ({ ...prev, [region]: rows }))
            }
          />
        </TabsContent>

        <TabsContent value="balances" className="mt-4 space-y-4">
          <div className="flex justify-end">
            <Button
              size="sm"
              onClick={() => {
                setAdjusting(null);
                setDialogOpen(true);
              }}
            >
              <Gift size={15} />
              Grant holiday allowance
            </Button>
          </div>

          <Card className="p-0 overflow-x-auto">
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Name</TableHead>
                  <TableHead>Region</TableHead>
                  <TableHead>Level</TableHead>
                  <TableHead>Manager</TableHead>
                  <TableHead className="text-right">Balance</TableHead>
                  <TableHead className="text-right">Pending</TableHead>
                  <TableHead className="text-right">Available</TableHead>
                  <TableHead />
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
                      {REGIONS[p.region]?.label ?? p.region}
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
                    <TableCell className="text-right">
                      <Button
                        variant="ghost"
                        size="sm"
                        onClick={() => {
                          setAdjusting(p);
                          setDialogOpen(true);
                        }}
                      >
                        Adjust
                      </Button>
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
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
                          "adjustment"
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
            </Card>
          )}
        </TabsContent>

        <TabsContent value="health" className="mt-4">
          <DataHealth people={ORG_BALANCES} />
        </TabsContent>
      </Tabs>
    </div>
  );
};

export default AdminView;
