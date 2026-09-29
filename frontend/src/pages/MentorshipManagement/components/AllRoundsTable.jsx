import { Link } from "react-router-dom";
import { Eye, Pencil, Users } from "lucide-react";
import { Button } from "@/components/ui/button";
import Table from "@/components/common/Table";
import { ROUTE_PATHS } from "@/constants/RoutePaths";

/**
 * Displays all mentorship rounds in a table with summary stats.
 *
 * Columns: Round Name, Participants, Required Meetings, Mentor Rating,
 *          Mentee Rating, Average Meetings Per Pair, Feedback (read only),
 *          Action
 * Footer:  Total Completed Rounds | Total Participants | Total Meetings
 *
 * @param {{
 *   rounds: Object[], mentorship round objects with pair stats
 *   totals: { totalCompletedRounds: number, totalParticipants: number, totalMeetings: number },
 *   onEdit: (round: Object) => void, round to edit
 *   canEdit: boolean, whether the user may edit rounds (MENTORSHIP_ADMIN_WRITE); controls icon (pencil or eye)
 *   canReadFeedback: boolean, whether to show the Feedback column (MENTORSHIP_ADMIN_READ)
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

const FEEDBACK_COLUMN = { header: "Feedback", accessor: "feedback" };
const ACTION_COLUMN = { header: "Action", accessor: "action" };

/**
 * "x of y sent", linking to the round's feedback page; a dash when nobody
 * owes feedback for the round.
 */
const FeedbackCell = ({ round }) => {
  if (!round.feedbackOwed) return "—";
  return (
    <Link
      to={ROUTE_PATHS.MENTORSHIP_ROUND_FEEDBACK(round.id)}
      aria-label={`Feedback for ${round.name}`}
      className="text-blue-700 underline-offset-2 hover:underline"
    >
      {round.feedbackSent ?? 0} of {round.feedbackOwed} sent
    </Link>
  );
};

export default function AllRoundsTable({
  rounds,
  totals,
  onEdit,
  canEdit = true,
  canReadFeedback = false,
}) {
  const columns = [
    ...BASE_COLUMNS,
    ...(canReadFeedback ? [FEEDBACK_COLUMN] : []),
    ACTION_COLUMN,
  ];

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
    feedback: <FeedbackCell round={round} />,
    action: (
      <Button
        variant="ghost"
        size="sm"
        onClick={() => onEdit(round)}
        aria-label={canEdit ? "Edit round" : "View round"}
        className="h-8 w-8 p-0"
      >
        {canEdit ? <Pencil className="h-4 w-4" /> : <Eye className="h-4 w-4" />}
      </Button>
    ),
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
