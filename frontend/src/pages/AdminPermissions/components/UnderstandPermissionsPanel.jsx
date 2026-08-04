import {
  Sheet,
  SheetContent,
  SheetDescription,
  SheetHeader,
  SheetTitle,
  SheetTrigger,
} from "@/components/ui/sheet";

const GROUP_LABELS = {
  system: "System",
  internal_activity: "Internal Activity",
  directory: "Directory",
  dashboard: "Dashboard",
  mentorship: "Mentorship",
  recruiting: "Recruiting",
  permission: "Permission Administration",
  super_admin: "Super Admin",
};

/**
 * Fallback heading for a permission namespace prefix with no entry in
 * GROUP_LABELS, e.g. "totally_new" -> "Totally New".
 *
 * @param {string} prefix
 * @returns {string}
 */
const titleCase = (prefix) =>
  prefix
    .split("_")
    .map((word) => word.charAt(0).toUpperCase() + word.slice(1))
    .join(" ");

/**
 * Groups a flat permission catalog by the first dot-segment of each name
 * (e.g. "recruiting.job.write" groups under "recruiting"), preserving each
 * group's catalog order. An unrecognized prefix falls back to a title-cased
 * version of itself so a future permission namespace doesn't need a
 * frontend change to appear here.
 *
 * @param {{name: string, description: string}[]} catalog
 * @returns {{label: string, entries: {name: string, description: string}[]}[]}
 */
const groupByNamespace = (catalog) => {
  const groups = new Map();
  for (const entry of catalog) {
    const prefix = entry.name.split(".")[0];
    if (!groups.has(prefix)) groups.set(prefix, []);
    groups.get(prefix).push(entry);
  }
  return Array.from(groups.entries()).map(([prefix, entries]) => ({
    label: GROUP_LABELS[prefix] ?? titleCase(prefix),
    entries,
  }));
};

/**
 * Non-modal reference panel explaining every grantable permission, grouped
 * by resource namespace. Triggered by a handle fixed to the right edge of
 * the viewport; stays open alongside the checklist/dropdown so an admin can
 * cross-reference descriptions while granting or searching.
 *
 * @param {Object} props
 * @param {{name: string, description: string}[]} props.catalog
 */
const UnderstandPermissionsPanel = ({ catalog }) => {
  const groups = groupByNamespace(catalog);

  return (
    <Sheet modal={false}>
      <SheetTrigger asChild>
        <button
          type="button"
          className="fixed right-0 top-1/2 z-40 -translate-y-1/2 rounded-l-md border bg-background px-2 py-3 text-sm font-medium shadow-sm [writing-mode:vertical-rl]"
        >
          Understand permissions
        </button>
      </SheetTrigger>
      <SheetContent className="overflow-y-auto sm:max-w-md">
        <SheetHeader>
          <SheetTitle>Understand permissions</SheetTitle>
          <SheetDescription>
            What each grantable permission actually lets someone do.
          </SheetDescription>
        </SheetHeader>
        <div className="flex flex-col gap-5 px-4 pb-4">
          {groups.map((group) => (
            <div key={group.label} className="flex flex-col gap-2">
              <h3 className="text-sm font-semibold text-foreground">
                {group.label}
              </h3>
              <ul className="flex flex-col gap-2">
                {group.entries.map((entry) => (
                  <li key={entry.name} className="flex flex-col gap-0.5">
                    <span className="font-mono text-xs text-foreground">
                      {entry.name}
                    </span>
                    <span className="text-sm text-muted-foreground">
                      {entry.description}
                    </span>
                  </li>
                ))}
              </ul>
            </div>
          ))}
        </div>
      </SheetContent>
    </Sheet>
  );
};

export default UnderstandPermissionsPanel;
