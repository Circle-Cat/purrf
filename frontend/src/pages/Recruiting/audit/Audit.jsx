import { useCallback, useEffect, useMemo, useState } from "react";
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
import DateRangePicker from "@/components/common/DateRangePicker";
import { getAuditOverview } from "@/api/recruitingApi";
import { formatLocalYmd } from "@/utils/dateTime";

/**
 * Sentence-case a snake_case stage/status value for display, e.g.
 * "recruiter_screening" -> "Recruiter screening".
 */
const humanize = (value) => {
  const spaced = value.split("_").join(" ");
  return spaced.charAt(0).toUpperCase() + spaced.slice(1);
};

const THIRTY_DAYS_MS = 30 * 24 * 60 * 60 * 1000;

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

  const filteredStageBreakdown = useMemo(
    () =>
      (overview?.stageBreakdown ?? []).filter((row) =>
        (selectedJobIds ?? []).includes(row.jobId),
      ),
    [overview, selectedJobIds],
  );

  // Group stage rows by job so each job's name renders once, spanning its
  // stage rows, instead of repeating on every row.
  const stageRowsByJob = useMemo(() => {
    const map = new Map();
    for (const row of filteredStageBreakdown) {
      if (!map.has(row.jobId)) map.set(row.jobId, []);
      map.get(row.jobId).push(row);
    }
    return map;
  }, [filteredStageBreakdown]);

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

      {/* Charts render here — added by Task 4 (stage breakdown) and Task 5 (daily trend). */}

      <Card>
        <CardHeader>
          <CardTitle className="text-sm font-medium text-slate-600">
            Stage breakdown
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
              {[...stageRowsByJob.entries()].map(([jobId, rows]) =>
                rows.map((row, idx) => (
                  <TableRow key={`${jobId}-${row.stage}`}>
                    {idx === 0 && (
                      <TableCell rowSpan={rows.length}>
                        {row.jobTitle}
                      </TableCell>
                    )}
                    <TableCell>{humanize(row.stage)}</TableCell>
                    <TableCell>{row.count}</TableCell>
                  </TableRow>
                )),
              )}
            </TableBody>
          </Table>
        </CardContent>
      </Card>
    </div>
  );
};

export default Audit;
