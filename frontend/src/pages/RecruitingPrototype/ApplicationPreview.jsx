import { useState } from "react";
import { Label } from "@/components/ui/label";
import { Separator } from "@/components/ui/separator";
import { Badge } from "@/components/ui/badge";
import JsonSchemaForm from "./vendor/JsonSchemaForm";
import { PROFILE_FIELDS } from "./mockData";

/**
 * Renders a required(*) or optional marker after a field label.
 *
 * @param {{ level: "required" | "optional" | "off" }} props
 * @returns {JSX.Element | null}
 */
function ReqMark({ level }) {
  if (level === "required") return <span className="text-red-500"> *</span>;
  if (level === "optional") {
    return (
      <span className="text-muted-foreground text-xs font-normal">
        {" "}
        (optional)
      </span>
    );
  }
  return null;
}

/** Disabled-input styling shared by the preview's read-only fields. */
const PREVIEW_INPUT =
  "w-full rounded-md border border-input bg-background px-3 py-2 text-sm text-muted-foreground";

/**
 * ApplicationPreview
 *
 * A read-only "candidate's view" of an entire posting's application form —
 * Personal + Profile (only the sections that aren't "off", each marked
 * optional/required) + the Details questions. Used as the Preview tab of the
 * Create Posting screen so admins see the whole posting effect, not just the
 * custom questions.
 *
 * @component
 * @param {Object} props
 * @param {string} props.title - The posting title.
 * @param {Record<string,"off"|"optional"|"required">} props.profileReq - Per-section requirement levels.
 * @param {Object} props.schema - The Details JSON Schema being built.
 * @returns {JSX.Element}
 */
const ApplicationPreview = ({ title, profileReq, schema }) => {
  const [answers, setAnswers] = useState({});
  const shownProfile = PROFILE_FIELDS.filter(
    (f) => profileReq[f.key] !== "off",
  );
  const hasDetails =
    schema?.properties && Object.keys(schema.properties).length > 0;

  return (
    <div className="rounded-xl border bg-muted/20 p-5 space-y-6">
      <div className="flex items-center gap-2">
        <Badge variant="secondary">Candidate&apos;s view</Badge>
        <span className="text-sm text-muted-foreground truncate">
          {title || "Untitled posting"}
        </span>
      </div>

      {/* Personal */}
      <section className="space-y-3">
        <h4 className="text-xs font-semibold uppercase tracking-wide text-muted-foreground">
          Personal
        </h4>
        <div className="grid grid-cols-2 gap-3">
          <div className="space-y-1">
            <Label className="text-sm">
              First name
              <ReqMark level="required" />
            </Label>
            <input disabled placeholder="Jane" className={PREVIEW_INPUT} />
          </div>
          <div className="space-y-1">
            <Label className="text-sm">
              Last name
              <ReqMark level="required" />
            </Label>
            <input disabled placeholder="Smith" className={PREVIEW_INPUT} />
          </div>
          <div className="space-y-1">
            <Label className="text-sm">
              Email
              <ReqMark level="required" />
            </Label>
            <input
              disabled
              placeholder="jane@example.com"
              className={PREVIEW_INPUT}
            />
          </div>
          <div className="space-y-1">
            <Label className="text-sm">
              Phone
              <ReqMark level="optional" />
            </Label>
            <input
              disabled
              placeholder="+1 (555) 000-0000"
              className={PREVIEW_INPUT}
            />
          </div>
        </div>
      </section>

      {/* Profile — only sections that are not "off" */}
      {shownProfile.length > 0 && (
        <section className="space-y-3">
          <Separator />
          <h4 className="text-xs font-semibold uppercase tracking-wide text-muted-foreground">
            Profile
          </h4>
          <div className="space-y-3">
            {shownProfile.map((f) => (
              <div key={f.key} className="space-y-1">
                <Label className="text-sm">
                  {f.label}
                  <ReqMark level={profileReq[f.key]} />
                </Label>
                {f.key === "summary" ? (
                  <textarea
                    disabled
                    rows={2}
                    placeholder="A short intro about your background…"
                    className={`${PREVIEW_INPUT} resize-none`}
                  />
                ) : f.key === "resume" ? (
                  <input
                    disabled
                    placeholder="https://drive.google.com/…"
                    className={PREVIEW_INPUT}
                  />
                ) : (
                  <input
                    disabled
                    placeholder={
                      f.key === "education"
                        ? "School · Degree · Years"
                        : "Company · Title · Years"
                    }
                    className={PREVIEW_INPUT}
                  />
                )}
              </div>
            ))}
          </div>
        </section>
      )}

      {/* Details — the custom questions being built */}
      <section className="space-y-3">
        <Separator />
        <h4 className="text-xs font-semibold uppercase tracking-wide text-muted-foreground">
          Details
        </h4>
        {hasDetails ? (
          <JsonSchemaForm
            schema={schema}
            value={answers}
            onChange={setAnswers}
          />
        ) : (
          <p className="text-sm text-muted-foreground italic">
            No custom questions yet — add some in the Edit tab.
          </p>
        )}
      </section>
    </div>
  );
};

export default ApplicationPreview;
