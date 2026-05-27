import RoundsManagementCard from "@/pages/MentorshipManagement/components/RoundsManagementCard";
import { useMentorshipManagement } from "@/pages/MentorshipManagement/hooks/useMentorshipManagement";

/**
 * MentorshipManagement
 *
 * Admin page for managing mentorship rounds.
 * Route: /mentorship-management (MENTORSHIP_ADMIN role only)
 *
 * @returns {JSX.Element}
 */
const MentorshipManagement = () => {
  const { sortedRounds, totals, isLoading, openCreate, openEdit } =
    useMentorshipManagement();

  return (
    <div className="mentorship-management">
      <RoundsManagementCard
        rounds={sortedRounds}
        totals={totals}
        isLoading={isLoading}
        openCreate={openCreate}
        openEdit={openEdit}
      />
    </div>
  );
};

export default MentorshipManagement;
