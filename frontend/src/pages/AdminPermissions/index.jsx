import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { usePermissionCatalog } from "@/pages/AdminPermissions/hooks/usePermissionCatalog";
import UsersTab from "@/pages/AdminPermissions/components/UsersTab";
import PermissionHoldersTab from "@/pages/AdminPermissions/components/PermissionHoldersTab";
import AuditTab from "@/pages/AdminPermissions/components/AuditTab";

/**
 * Permission administration page. Gated on permission.manage (route + sidebar).
 * Three tabs over a shared permission catalog.
 *
 * Route: /admin/users
 */
const AdminPermissions = () => {
  const { catalog } = usePermissionCatalog();

  return (
    <div className="p-5 box-border">
      <Tabs defaultValue="users">
        <TabsList className="mb-5 gap-1">
          <TabsTrigger
            value="users"
            className="px-4 data-[state=active]:bg-background data-[state=active]:shadow-sm data-[state=active]:font-medium"
          >
            Users
          </TabsTrigger>
          <TabsTrigger
            value="holders"
            className="px-4 data-[state=active]:bg-background data-[state=active]:shadow-sm data-[state=active]:font-medium"
          >
            Permission Holders
          </TabsTrigger>
          <TabsTrigger
            value="audit"
            className="px-4 data-[state=active]:bg-background data-[state=active]:shadow-sm data-[state=active]:font-medium"
          >
            Audit Log
          </TabsTrigger>
        </TabsList>
        <TabsContent value="users">
          <UsersTab catalog={catalog} />
        </TabsContent>
        <TabsContent value="holders">
          <PermissionHoldersTab catalog={catalog} />
        </TabsContent>
        <TabsContent value="audit">
          <AuditTab catalog={catalog} />
        </TabsContent>
      </Tabs>
    </div>
  );
};

export default AdminPermissions;
