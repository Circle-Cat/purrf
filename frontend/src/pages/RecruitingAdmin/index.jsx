import { useAuth } from "@/context/auth";
import { PERMISSIONS } from "@/constants/Permissions";
import { Card, CardHeader, CardTitle, CardContent } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Plus } from "lucide-react";
import { useRecruitingAdmin } from "@/pages/RecruitingAdmin/hooks/useRecruitingAdmin";
import JobModal from "@/pages/RecruitingAdmin/components/JobModal";

/**
 * Status badge variant mapping for a posting's lifecycle state.
 *
 * @type {Record<string, "default"|"secondary"|"outline"|"destructive">}
 */
const STATUS_VARIANT = {
  draft: "secondary",
  published: "default",
  closed: "outline",
};

/**
 * RecruitingAdmin
 *
 * Admin page for managing mentor and mentee job postings. Entry is gated on
 * `RECRUITING_JOB_READ`; write actions (create, publish, close, save) are
 * additionally gated on `RECRUITING_JOB_WRITE`.
 *
 * The page fetches published postings from the API on mount and merges any
 * draft postings created during the session so that admins can publish them
 * without leaving the page (the backend returns published postings only).
 *
 * Route: /recruiting-admin
 *
 * @returns {JSX.Element}
 */
const RecruitingAdmin = () => {
  const { permissions } = useAuth();
  const canRead = permissions.includes(PERMISSIONS.RECRUITING_JOB_READ);
  const canWrite = permissions.includes(PERMISSIONS.RECRUITING_JOB_WRITE);

  const {
    postings,
    isLoading,
    jobModalState,
    openCreate,
    openEdit,
    closeModal,
    saveJob,
    handlePublish,
    handleClose,
  } = useRecruitingAdmin(canRead);

  if (!canRead) {
    return (
      <div className="recruiting-admin p-6 text-center text-muted-foreground">
        You do not have permission to view job postings.
      </div>
    );
  }

  return (
    <div className="recruiting-admin">
      <Card className="border-gray-200 shadow-sm">
        <CardHeader className="flex flex-row items-center justify-between">
          <CardTitle>Recruiting Admin</CardTitle>
          {canWrite && (
            <Button onClick={openCreate}>
              <Plus className="h-4 w-4 mr-2" />
              Create posting
            </Button>
          )}
        </CardHeader>

        <CardContent>
          {isLoading ? (
            <div className="py-10 text-center text-gray-500">
              Loading postings…
            </div>
          ) : postings.length === 0 ? (
            <div className="text-center py-8 text-gray-500">
              No postings found.
            </div>
          ) : (
            <div className="space-y-3">
              {postings.map((posting) => (
                <PostingRow
                  key={posting.id}
                  posting={posting}
                  canWrite={canWrite}
                  onEdit={() => openEdit(posting)}
                  onPublish={() => handlePublish(posting.id)}
                  onClose={() => handleClose(posting.id)}
                />
              ))}
            </div>
          )}
        </CardContent>
      </Card>

      <JobModal
        open={jobModalState.open}
        job={jobModalState.job}
        onClose={closeModal}
        onSave={saveJob}
        readOnly={!canWrite}
      />
    </div>
  );
};

/**
 * A single row in the postings list, showing metadata and contextual actions.
 *
 * @param {Object}   props
 * @param {Object}   props.posting        - The job posting to display.
 * @param {boolean}  props.canWrite       - Whether write actions are enabled.
 * @param {Function} props.onEdit         - Open the posting in the edit modal.
 * @param {Function} props.onPublish      - Publish a draft posting.
 * @param {Function} props.onClose        - Close a published posting.
 */
function PostingRow({ posting, canWrite, onEdit, onPublish, onClose }) {
  const statusLabel =
    posting.status.charAt(0).toUpperCase() + posting.status.slice(1);

  return (
    <div className="flex items-center justify-between rounded-lg border px-4 py-3 gap-4">
      <div className="flex items-center gap-3 min-w-0">
        <span className="font-medium truncate">{posting.title}</span>
        <span className="text-sm text-muted-foreground capitalize shrink-0">
          {posting.mentorshipRole}
        </span>
        <Badge variant={STATUS_VARIANT[posting.status] ?? "outline"}>
          {statusLabel}
        </Badge>
      </div>

      {canWrite && (
        <div className="flex items-center gap-2 shrink-0">
          <Button variant="ghost" size="sm" onClick={onEdit}>
            Edit
          </Button>

          {posting.status === "draft" && (
            <Button size="sm" onClick={onPublish}>
              Publish
            </Button>
          )}

          {posting.status === "published" && (
            <Button variant="outline" size="sm" onClick={onClose}>
              Close posting
            </Button>
          )}
        </div>
      )}
    </div>
  );
}

export default RecruitingAdmin;
