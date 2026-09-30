import { useState } from "react";
import { Badge } from "@/components/ui/badge";
import { Input } from "@/components/ui/input";
import TemplateList from "@/pages/EmailTemplatesPrototype/TemplateList";
import TemplatePreview from "@/pages/EmailTemplatesPrototype/TemplatePreview";
import { SERVICES, TEMPLATES } from "@/pages/EmailTemplatesPrototype/mockData";
import { matchesSearch } from "@/pages/EmailTemplatesPrototype/templateView";

const selectClass =
  "h-9 rounded-md border border-slate-300 bg-white px-2 text-sm text-slate-700";

/**
 * EmailTemplatesPrototype
 *
 * A read-only catalog of every email Purrf sends from content written in
 * code: the manual templates staff pick in a compose box, and the automatic
 * notification emails sent when an event happens. For system admins only.
 *
 * @returns {JSX.Element}
 */
const EmailTemplatesPrototype = () => {
  const [service, setService] = useState("all");
  const [mode, setMode] = useState("all");
  const [term, setTerm] = useState("");
  const [selectedKey, setSelectedKey] = useState(TEMPLATES[0].key);

  const built = TEMPLATES.filter((t) => !t.planned);
  const planned = TEMPLATES.length - built.length;
  const visible = TEMPLATES.filter(
    (t) =>
      (service === "all" || t.service === service) &&
      (mode === "all" || t.mode === mode) &&
      matchesSearch(t, term),
  );
  const selected = TEMPLATES.find((t) => t.key === selectedKey) ?? null;

  return (
    <div className="min-h-full bg-slate-50">
      <main className="mx-auto max-w-6xl space-y-4 p-4 sm:p-6">
        <header className="space-y-1">
          <div className="flex flex-wrap items-center gap-2">
            <h1 className="text-xl font-semibold text-slate-900">
              Email templates
            </h1>
            <Badge
              variant="outline"
              className="border-slate-300 bg-white text-slate-700"
            >
              {built.length} templates
            </Badge>
            <Badge
              variant="outline"
              className="border-dashed border-slate-300 bg-slate-50 text-slate-500"
            >
              {planned} planned
            </Badge>
          </div>
          <p className="text-sm text-slate-600">
            Every email the system sends from content written in code.
            Read-only.
          </p>
          <p className="text-xs text-slate-500">
            Visible to <code>ops.alert</code>
          </p>
        </header>

        <div className="flex flex-wrap items-center gap-2">
          <Input
            type="search"
            aria-label="Search templates"
            placeholder="Search name, key or subject"
            value={term}
            onChange={(e) => setTerm(e.target.value)}
            className="w-full border-slate-300 bg-white sm:w-72"
          />
          <select
            aria-label="Service"
            value={service}
            onChange={(e) => setService(e.target.value)}
            className={selectClass}
          >
            <option value="all">All services</option>
            {SERVICES.map((s) => (
              <option key={s.key} value={s.key}>
                {s.label}
              </option>
            ))}
          </select>
          <select
            aria-label="Send mode"
            value={mode}
            onChange={(e) => setMode(e.target.value)}
            className={selectClass}
          >
            <option value="all">Manual and automatic</option>
            <option value="manual">Manual</option>
            <option value="automatic">Automatic</option>
          </select>
          <span aria-live="polite" className="text-xs text-slate-500">
            Showing {visible.length}
          </span>
        </div>

        <div className="grid gap-4 lg:grid-cols-[minmax(0,2fr)_minmax(0,3fr)]">
          <TemplateList
            templates={visible}
            selectedKey={selectedKey}
            onSelect={setSelectedKey}
          />
          {selected && (
            <TemplatePreview key={selected.key} template={selected} />
          )}
        </div>

        <footer className="border-t border-slate-200 pt-3 text-xs text-slate-500">
          Not listed: Auth0 sign-in codes and email verification — configured in
          the Auth0 dashboard, not in Purrf code.
        </footer>
      </main>
    </div>
  );
};

export default EmailTemplatesPrototype;
