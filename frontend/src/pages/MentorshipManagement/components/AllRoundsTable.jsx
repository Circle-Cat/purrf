import { Pencil, Users } from "lucide-react";
import { Button } from "@/components/ui/button";
import Table from "@/components/common/Table";

/**
 * Displays all mentorship rounds in a table with summary stats.
 *
 * Columns: Round Name, Participants, Required Meetings, Mentor Rating,
 *          Mentee Rating, Average Meetings Per Pair, Action
 * Footer:  Total Completed Rounds | Total Participants | Total Meetings
 *
 * @param {{
 *   rounds: Object[], mentorship round objects with pair stats
 *   totals: { totalCompletedRounds: number, totalParticipants: number, totalMeetings: number },
 *   onEdit: (round: Object) => void, round to edit
 *   canEdit: boolean, whether to show the per-row edit action (MENTORSHIP_ROUND_WRITE)
 * }} props
 */

const formatRating = (val) => (val != null ? Number(val).toFixed(2) : "—");

const getAvgMeetings = (totalCompletedMeetings, activePairs) => {
  if (!activePairs) return "—";
  return ((totalCompletedMeetings ?? 0) / activePairs).toFixed(1);
};

const BASE_COLUMNS = [
  { header: "Round Name", accessor: "name" },
  { header: "Participants", accessor: "participants" },
  { header: "Required Meetings", accessor: "requiredMeetings" },
  { header: "Mentor Rating", accessor: "mentorRating" },
  { header: "Mentee Rating", accessor: "menteeRating" },
  { header: "Average Meetings Per Pair", accessor: "avgMeetings" },
];

const ACTION_COLUMN = { header: "Action", accessor: "action" };

export default function AllRoundsTable({ rounds, totals, onEdit, canEdit = true }) {
  const columns = canEdit ? [...BASE_COLUMNS, ACTION_COLUMN] : BASE_COLUMNS;

  const data = rounds.map((round) => ({
    name: round.name,
    participants: (
      <div className="flex items-center gap-2">
        <Users className="h-4 w-4 text-gray-500" />
        {round.matchedParticipants ?? "—"}
      </div>
    ),
    requiredMeetings:
      round.requiredMeetings != null ? `${round.requiredMeetings} times` : "—",
    mentorRating: formatRating(round.mentorAverageScore),
    menteeRating: formatRating(round.menteeAverageScore),
    avgMeetings: getAvgMeetings(
      round.totalCompletedMeetings,
      round.activePairs,
    ),
    ...(canEdit && {
      action: (
        <Button
          variant="ghost"
          size="sm"
          onClick={() => onEdit(round)}
          aria-label="Edit round"
          className="h-8 w-8 p-0"
        >
          <Pencil className="h-4 w-4" />
        </Button>
      ),
    }),
  }));

  return (
    <div>
      <Table columns={columns} data={data} />
      <div className="flex gap-6 px-4 py-3 bg-gray-50 border-t border-gray-200 text-sm font-bold text-gray-700">
        <span>Total Completed Rounds: {totals?.totalCompletedRounds ?? 0}</span>
        <span>Total Participants: {totals?.totalParticipants ?? 0}</span>
        <span>Total Meetings: {totals?.totalMeetings ?? 0}</span>
      </div>
    </div>
  );
}
