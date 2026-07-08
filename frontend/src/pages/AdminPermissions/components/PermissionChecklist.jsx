import { useEffect, useMemo, useState } from "react";
import { Checkbox } from "@/components/ui/checkbox";
import { Button } from "@/components/ui/button";

/**
 * Checkbox-per-permission editor. Local checked state is seeded from `active`
 * and reset whenever `active` changes (e.g. after a save refetch or switching
 * users). Save is enabled only when the checked set differs from `active`.
 *
 * @param {Object} props
 * @param {{name: string, description: string}[]} props.catalog - Grantable permissions with descriptions.
 * @param {string[]} props.active - The user's currently-active permissions.
 * @param {(checked: string[]) => void} props.onSave
 * @param {boolean} props.saving
 */
const PermissionChecklist = ({ catalog, active, onSave, saving }) => {
  const [checked, setChecked] = useState(() => new Set(active));

  useEffect(() => {
    setChecked(new Set(active));
  }, [active]);

  const hasDiff = useMemo(() => {
    if (checked.size !== active.length) return true;
    return active.some((p) => !checked.has(p));
  }, [checked, active]);

  const toggle = (name) =>
    setChecked((prev) => {
      const next = new Set(prev);
      if (next.has(name)) next.delete(name);
      else next.add(name);
      return next;
    });

  return (
    <div className="admin-permission-checklist">
      <ul className="grid grid-cols-2 gap-2 mb-4 list-none p-0">
        {catalog.map(({ name }) => (
          <li key={name}>
            <label className="flex items-center gap-2 text-sm cursor-pointer">
              <Checkbox
                checked={checked.has(name)}
                onCheckedChange={() => toggle(name)}
                aria-label={name}
              />
              <span>{name}</span>
            </label>
          </li>
        ))}
      </ul>
      <Button
        onClick={() => onSave(Array.from(checked))}
        disabled={!hasDiff || saving}
      >
        Save
      </Button>
    </div>
  );
};

export default PermissionChecklist;
