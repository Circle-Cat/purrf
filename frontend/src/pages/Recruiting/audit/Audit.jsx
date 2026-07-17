import { useCallback, useEffect, useMemo, useState } from "react";
import { Bar, BarChart, CartesianGrid, XAxis, YAxis } from "recharts";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Checkbox } from "@/components/ui/checkbox";
import { Label } from "@/components/ui/label";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import {
  ChartContainer,
  ChartLegend,
  ChartLegendContent,
  ChartTooltip,
  ChartTooltipContent,
} from "@/components/ui/chart";
import DateRangePicker from "@/components/common/DateRangePicker";
import { getAuditOverview } from "@/api/recruitingApi";
import { formatLocalYmd } from "@/utils/dateTime";
import { STAGE_COLORS } from "@/pages/Recruiting/audit/auditColors";
import { stageLabel } from "@/pages/Recruiting/board/stageFormat";

const THIRTY_DAYS_MS = 30 * 24 * 60 * 60 * 1000;

/** Stages in funnel order, then the terminal outcomes — the order bars
 * stack in, and the order the legend lists them. Employment and activity
 * postings render as separate sections: activity postings have no offer
 * step, and their `hired` stage is labeled "Admitted". */
const STAGE_ORDERS = {
  employment: [
    "recruiter_screening",
    "behavioral",
    "tech",
    "board_review",
    "offer",
    "hired",
    "rejected",
    "offer_declined",
    "blacklisted",
  ],
  activity: [
    "recruiter_screening",
    "behavioral",
    "tech",
    "board_review",
    "hired",
    "rejected",
    "blacklisted",
  ],
};

/**
 * Reshape `stageBreakdown` rows into one object per job with a key per
 * stage, the shape Recharts' `BarChart` expects for a stacked bar.
 *
 * @param {{jobId: number, jobTitle: string, stage: string, count: number}[]} rows
 * @returns {{jobTitle: string, [stage: string]: number|string}[]}
 */
function toStageChartData(rows) {
  const byJob = new Map();
  for (const row of rows) {
    if (!byJob.has(row.jobId)) {
      byJob.set(row.jobId, { jobTitle: row.jobTitle });
    }
    byJob.get(row.jobId)[row.stage] = row.count;
  }
  return [...byJob.values()];
}

const STAGE_CHART_CONFIGS = Object.fromEntries(
  Object.entries(STAGE_ORDERS).map(([kind, stages]) => [
    kind,
    Object.fromEntries(
      stages.map((stage) => [
        stage,
        { label: stageLabel(stage, kind), color: STAGE_COLORS[stage] },
      ]),
    ),
  ]),
);

/**
 * One posting kind's stage-breakdown chart and supporting job x stage
 * table. Employment and activity postings are rendered as separate
 * sections because their stage sets differ (activity has no offer step)
 * and their terminal-success labels differ (Hired vs Admitted).
 *
 * @param {{
 *   kind: "employment"|"activity",
 *   title: string,
 *   rows: {jobId: number, jobTitle: string, stage: string, count: number}[],
 * }} props
 */
const StageBreakdownSection = ({ kind, title, rows }) => {
  // Group stage rows by job so each job's name renders once, spanning its
  // stage rows, instead of repeating on every row.
  const rowsByJob = useMemo(() => {
    const map = new Map();
    for (const row of rows) {
      if (!map.has(row.jobId)) map.set(row.jobId, []);
      map.get(row.jobId).push(row);
    }
    return map;
  }, [rows]);

  return (
    <>
      <Card>
        <CardHeader>
          <CardTitle className="text-sm font-medium text-slate-600">
            Stage breakdown by job — {title}
          </CardTitle>
        </CardHeader>
        <CardContent>
          <ChartContainer
            config={STAGE_CHART_CONFIGS[kind]}
            role="img"
            aria-label={`Stage breakdown chart — ${title}`}
          >
            <BarChart data={toStageChartData(rows)}>
              <CartesianGrid vertical={false} />
              <XAxis dataKey="jobTitle" tickLine={false} axisLine={false} />
              <YAxis tickLine={false} axisLine={false} allowDecimals={false} />
              <ChartTooltip content={<ChartTooltipContent />} />
              <ChartLegend content={<ChartLegendContent />} />
              {STAGE_ORDERS[kind].map((stage) => (
                <Bar
                  key={stage}
                  dataKey={stage}
                  stackId="stage"
                  fill={STAGE_COLORS[stage]}
                  radius={0}
                />
              ))}
            </BarChart>
          </ChartContainer>
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle className="text-sm font-medium text-slate-600">
            Stage breakdown — {title}
          </CardTitle>
        </CardHeader>
        <CardContent>
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>Job</TableHead>
                <TableHead>Stage</TableHead>
                <TableHead>Count</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {[...rowsByJob.entries()].map(([jobId, jobRows]) =>
                jobRows.map((row, idx) => (
                  <TableRow key={`${jobId}-${row.stage}`}>
                    {idx === 0 && (
                      <TableCell rowSpan={jobRows.length}>
                        {row.jobTitle}
                      </TableCell>
                    )}
                    <TableCell>{stageLabel(row.stage, kind)}</TableCell>
                    <TableCell>{row.count}</TableCell>
                  </TableRow>
                )),
              )}
            </TableBody>
          </Table>
        </CardContent>
      </Card>
    </>
  );
};

/**
 * Cross-posting recruiting audit page: open-positions KPI, a date-range +
 * job multi-select filter bar, a per-job stage-breakdown chart, a daily
 * application-trend chart, and a supporting job x stage table.
 *
 * Gated by `RECRUITING_AUDIT_READ` at the route level (see App.jsx) — this
 * component assumes the caller already holds that permission.
 */
const Audit = () => {
  const today = new Date();
  const defaultStart = formatLocalYmd(
    new Date(today.getTime() - THIRTY_DAYS_MS),
  );
  const defaultEnd = formatLocalYmd(today);

  const [startDate, setStartDate] = useState(defaultStart);
  const [endDate, setEndDate] = useState(defaultEnd);
  const [selectedJobIds, setSelectedJobIds] = useState(null); // null until jobs load
  const [overview, setOverview] = useState(null);

  const fetchOverview = useCallback(async (jobIds, start, end) => {
    const { data } = await getAuditOverview({
      startDate: start,
      endDate: end,
      jobIds: jobIds ?? [],
    });
    setOverview(data);
    if (jobIds === null) {
      // First load: default the selector to only currently-published jobs.
      setSelectedJobIds(
        data.jobs.filter((j) => j.status === "published").map((j) => j.id),
      );
    }
  }, []);

  useEffect(() => {
    fetchOverview(null, defaultStart, defaultEnd);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const handleDateChange = ({ startDate: s, endDate: e }) => {
    setStartDate(s);
    setEndDate(e);
    if (selectedJobIds !== null) fetchOverview(selectedJobIds, s, e);
  };

  const toggleJob = (jobId, checked) => {
    const next = checked
      ? [...(selectedJobIds ?? []), jobId]
      : (selectedJobIds ?? []).filter((id) => id !== jobId);
    setSelectedJobIds(next);
    fetchOverview(next, startDate, endDate);
  };

  // Selected jobs' stage rows, split by posting kind — employment and
  // activity render as separate sections (see StageBreakdownSection).
  const stageBreakdownByKind = useMemo(() => {
    const kindByJobId = new Map(
      (overview?.jobs ?? []).map((job) => [job.id, job.kind]),
    );
    const split = { employment: [], activity: [] };
    for (const row of overview?.stageBreakdown ?? []) {
      if (!(selectedJobIds ?? []).includes(row.jobId)) continue;
      split[kindByJobId.get(row.jobId)]?.push(row);
    }
    return split;
  }, [overview, selectedJobIds]);

  if (!overview || selectedJobIds === null) {
    return <div className="p-6 text-sm text-slate-500">Loading…</div>;
  }

  return (
    <div className="flex flex-col gap-6 p-6">
      <h1 className="text-xl font-semibold text-slate-900">Recruiting Audit</h1>

      <Card>
        <CardHeader>
          <CardTitle className="text-sm font-medium text-slate-600">
            Open positions: {overview.openPositionsCount}
          </CardTitle>
        </CardHeader>
      </Card>

      <div className="flex flex-wrap items-start gap-6">
        <DateRangePicker
          defaultStartDate={defaultStart}
          defaultEndDate={defaultEnd}
          onChange={handleDateChange}
        />
        <div className="flex flex-wrap gap-3">
          {overview.jobs.map((job) => (
            <Label key={job.id} className="flex items-center gap-2 text-sm">
              <Checkbox
                checked={selectedJobIds.includes(job.id)}
                onCheckedChange={(checked) => toggleJob(job.id, !!checked)}
                aria-label={job.title}
              />
              {job.title}
            </Label>
          ))}
        </div>
      </div>

      <StageBreakdownSection
        kind="employment"
        title="Employment"
        rows={stageBreakdownByKind.employment}
      />

      <StageBreakdownSection
        kind="activity"
        title="Activity"
        rows={stageBreakdownByKind.activity}
      />

      {/* Task 5 (daily trend) renders here. */}
    </div>
  );
};

export default Audit;
