import { Card, CardHeader, CardTitle, CardContent } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Plus } from "lucide-react";
import AllRoundsTable from "@/pages/MentorshipManagement/components/AllRoundsTable";

/**
 * Card containing the rounds management table and create button.
 *
 * @param {{
 *   rounds: Object[],
 *   totals: { totalCompletedRounds: number, totalParticipants: number, totalMeetings: number },
 *   isLoading: boolean,
 *   openCreate: () => void,
 *   openEdit: (round: Object) => void,
 * }} props
 */
export default function RoundsManagementCard({
  rounds,
  totals,
  isLoading,
  openCreate,
  openEdit,
}) {
  return (
    <Card className="border-gray-200 shadow-sm">
      <CardHeader className="flex flex-row items-center justify-between">
        <CardTitle>Mentorship Round Management</CardTitle>
        <Button onClick={openCreate}>
          <Plus className="h-4 w-4 mr-2" />
          Create New Round
        </Button>
      </CardHeader>
      <CardContent>
        {isLoading ? (
          <div className="py-10 text-center text-gray-500">
            Loading rounds...
          </div>
        ) : rounds.length > 0 ? (
          <AllRoundsTable rounds={rounds} totals={totals} onEdit={openEdit} />
        ) : (
          <div className="text-center py-8 text-gray-500">No rounds found.</div>
        )}
      </CardContent>
    </Card>
  );
}
