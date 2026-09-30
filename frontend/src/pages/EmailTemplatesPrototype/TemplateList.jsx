import { Badge } from "@/components/ui/badge";
import { SERVICES } from "@/pages/EmailTemplatesPrototype/mockData";

/**
 * ModeBadge
 *
 * Manual (staff pick it in a compose box) or Automatic (sent on an event).
 *
 * @param {{mode: "manual"|"automatic"}} props
 * @returns {JSX.Element}
 */
export const ModeBadge = ({ mode }) => (
  <Badge
    variant="outline"
    className={
      mode === "manual"
        ? "border-sky-200 bg-sky-50 text-sky-700"
        : "border-violet-200 bg-violet-50 text-violet-700"
    }
  >
    {mode === "manual" ? "Manual" : "Automatic"}
  </Badge>
);

/**
 * TemplateList
 *
 * The filtered templates, grouped by service. Each row is a button that
 * selects the template; planned entries are greyed but still selectable.
 *
 * @param {{templates: object[], selectedKey: string|null,
 *   onSelect: Function}} props
 * @returns {JSX.Element}
 */
const TemplateList = ({ templates, selectedKey, onSelect }) => {
  if (!templates.length) {
    return (
      <p className="rounded-lg border border-dashed border-slate-300 bg-white p-6 text-center text-sm text-slate-500">
        No templates match.
      </p>
    );
  }

  return (
    <div className="space-y-4">
      {SERVICES.map((service) => {
        const rows = templates.filter((t) => t.service === service.key);
        if (!rows.length) return null;
        return (
          <section key={service.key} aria-label={`${service.label} templates`}>
            <h2 className="mb-1.5 text-xs font-semibold uppercase tracking-wide text-slate-500">
              {service.label} · {rows.length}
            </h2>
            <ul className="divide-y divide-slate-200 overflow-hidden rounded-lg border border-slate-200 bg-white">
              {rows.map((t) => (
                <li key={t.key}>
                  <button
                    type="button"
                    onClick={() => onSelect(t.key)}
                    aria-label={`Open template ${t.name}${t.planned ? " (planned)" : ""}`}
                    className={`block w-full px-3 py-2 text-left text-sm transition-colors ${
                      t.key === selectedKey ? "bg-sky-50" : "hover:bg-slate-50"
                    } ${t.planned ? "text-slate-400" : "text-slate-800"}`}
                  >
                    <div className="flex items-start justify-between gap-2">
                      <span className="font-medium">{t.name}</span>
                      <span className="flex shrink-0 gap-1">
                        {t.planned ? (
                          <Badge
                            variant="outline"
                            className="border-dashed border-slate-300 bg-slate-50 text-slate-500"
                          >
                            Planned
                          </Badge>
                        ) : (
                          <ModeBadge mode={t.mode} />
                        )}
                      </span>
                    </div>
                    <div className="truncate font-mono text-xs text-slate-500">
                      {t.key}
                    </div>
                  </button>
                </li>
              ))}
            </ul>
          </section>
        );
      })}
    </div>
  );
};

export default TemplateList;
