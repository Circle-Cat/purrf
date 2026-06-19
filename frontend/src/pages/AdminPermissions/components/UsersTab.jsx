import { useUserAdmin } from "@/pages/AdminPermissions/hooks/useUserAdmin";
import UserList from "@/pages/AdminPermissions/components/UserList";
import UserDetailPanel from "@/pages/AdminPermissions/components/UserDetailPanel";
import { Dialog, DialogContent } from "@/components/ui/dialog";

/**
 * Users tab: full-width user table with search, sort, and filter controls.
 * Selecting a user via the pencil icon opens a Dialog containing the per-user
 * permission controls.
 *
 * @param {Object} props
 * @param {string[]} props.catalog - Grantable permission names.
 */
const UsersTab = ({ catalog }) => {
  const {
    users,
    total,
    loading,
    search,
    setSearch,
    offset,
    limit,
    nextPage,
    prevPage,
    selectedUser,
    selectUser,
    makeSuperAdmin,
    revokeSuperAdminFor,
    sortBy,
    order,
    toggleSort,
    isSuperAdmin,
    setIsSuperAdmin,
    userType,
    setUserType,
  } = useUserAdmin();

  return (
    <div className="admin-users-tab flex flex-col gap-4">
      <UserList
        users={users}
        total={total}
        loading={loading}
        search={search}
        onSearchChange={setSearch}
        offset={offset}
        limit={limit}
        onPrev={prevPage}
        onNext={nextPage}
        onSelect={selectUser}
        sortBy={sortBy}
        order={order}
        onToggleSort={toggleSort}
        isSuperAdmin={isSuperAdmin}
        onSuperAdminFilterChange={setIsSuperAdmin}
        userType={userType}
        onUserTypeChange={setUserType}
      />

      <Dialog
        open={!!selectedUser}
        onOpenChange={(open) => {
          if (!open) selectUser(null);
        }}
      >
        <DialogContent className="sm:max-w-2xl overflow-y-auto max-h-[90vh]">
          {selectedUser && (
            <UserDetailPanel
              selectedUser={selectedUser}
              catalog={catalog}
              onMakeSuperAdmin={makeSuperAdmin}
              onRevokeSuperAdmin={revokeSuperAdminFor}
            />
          )}
        </DialogContent>
      </Dialog>
    </div>
  );
};

export default UsersTab;
