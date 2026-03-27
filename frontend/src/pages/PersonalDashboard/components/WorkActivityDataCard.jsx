import { useState, useMemo } from "react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import DateRangePicker from "@/components/common/DateRangePicker";
import {
  CheckCircle2,
  GitMerge,
  Code,
  Clock,
  MessageSquare,
} from "lucide-react";

/**
 * Displays the current user's work activity metrics for a selected date range.
 *
 * Shows Jira tickets, merged CLs, lines of code, meeting hours, and chat messages.
 * The date range is controlled locally; data is only re-fetched when the user
 * clicks the Search button.
 *
 * @param {{
 *   initialData: {
 *     startDate: string,
 *     endDate: string,
 *     summary: {
 *       jiraTickets: number,
 *       mergedCLs: number,
 *       mergedLOC: number,
 *       meetingHours: number,
 *       chatMessages: number,
 *     }
 *   },
 *   onSearch: (range: { startDate: string, endDate: string }) => void,
 *   isLoading: boolean
 * }} props
 */
export function WorkActivityDataCard({ initialData, onSearch, isLoading }) {
  const [dateRange, setDateRange] = useState({
    startDate: initialData?.startDate || "",
    endDate: initialData?.endDate || "",
  });

  const handleSearch = () => {
    onSearch?.(dateRange);
  };

  const metricsConfig = useMemo(
    () => [
      {
        key: "jiraTickets",
        label: "Jira Tickets (Done)",
        icon: CheckCircle2,
        value: initialData?.summary?.jiraTickets ?? 0,
      },
      {
        key: "mergedCLs",
        label: "Merged CLs",
        icon: GitMerge,
        value: initialData?.summary?.mergedCLs ?? 0,
      },
      {
        key: "mergedLOC",
        label: "Merged LOC",
        icon: Code,
        value: initialData?.summary?.mergedLOC?.toLocaleString?.() ?? 0,
      },
      {
        key: "meetingHours",
        label: "Meeting Hours",
        icon: Clock,
        value: initialData?.summary?.meetingHours ?? 0,
      },
      {
        key: "chatMessages",
        label: "Chat Messages Sent",
        icon: MessageSquare,
        value: initialData?.summary?.chatMessages ?? 0,
      },
    ],
    [initialData],
  );

  return (
    <Card className="mt-6">
      <CardHeader>
        <div className="flex items-center justify-between">
          <CardTitle>Work Activity Data</CardTitle>
          <div className="flex items-center gap-2">
            <DateRangePicker
              defaultStartDate={dateRange.startDate}
              defaultEndDate={dateRange.endDate}
              onChange={setDateRange}
            />
            <Button
              variant="outline"
              size="sm"
              onClick={handleSearch}
              disabled={isLoading}
            >
              Search
            </Button>
          </div>
        </div>
      </CardHeader>

      <CardContent>
        {isLoading ? (
          <div className="py-10 text-center text-gray-500">
            Loading activity data...
          </div>
        ) : (
          <div className="grid grid-cols-2 md:grid-cols-3 gap-6">
            {metricsConfig.map((item) => {
              const Icon = item.icon;

              return (
                <div key={item.key} className="flex items-center gap-3">
                  <div className="p-2 rounded-lg bg-[#F4F1FF] text-[#6035F3]">
                    <Icon className="w-5 h-5" />
                  </div>
                  <div>
                    <div className="text-sm text-gray-500">{item.label}</div>
                    <div className="text-2xl font-semibold text-gray-900">
                      {item.value}
                    </div>
                  </div>
                </div>
              );
            })}
          </div>
        )}
      </CardContent>
    </Card>
  );
}
