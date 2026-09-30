import { useState } from "react";
import { Badge } from "@/components/ui/badge";
import { ModeBadge } from "@/pages/EmailTemplatesPrototype/TemplateList";
import {
  PLACEHOLDER_INFO,
  SENDERS,
  SERVICES,
} from "@/pages/EmailTemplatesPrototype/mockData";
import {
  markersOf,
  placeholdersOf,
  previewBody,
} from "@/pages/EmailTemplatesPrototype/templateView";

const Unverified = () => (
  <span
    title="unverified"
    aria-label="unverified"
    className="ml-1 inline-flex h-4 w-4 cursor-help items-center justify-center rounded-full border border-amber-300 bg-amber-50 text-[10px] font-semibold text-amber-700"
  >
    ?
  </span>
);

const Row = ({ label, children }) => (
  <>
    <dt className="text-slate-500">{label}</dt>
    <dd className="text-slate-800">{children}</dd>
  </>
);

/**
 * TemplatePreview
 *
 * Everything about one template: what sends it, to whom, from which alias,
 * and a rendered preview. Manual previews keep their `{{...}}` placeholders
 * raw, shown as chips; automatic previews use invented sample event data.
 * Mounted fresh per template, so the variant resets on switching.
 *
 * @param {{template: object}} props
 * @returns {JSX.Element}
 */
const TemplatePreview = ({ template }) => {
  const [variantIndex, setVariantIndex] = useState(0);

  const service = SERVICES.find((s) => s.key === template.service);
  const sender = SENDERS[template.service];
  const manual = template.mode === "manual";
  const variant = template.variants[variantIndex];
  const placeholders = manual ? placeholdersOf(template) : [];
  const markers = manual ? markersOf(template) : [];

  return (
    <section
      aria-label="Template preview"
      className="space-y-4 rounded-lg border border-slate-200 bg-white p-4"
    >
      <header className="space-y-1">
        <div className="flex flex-wrap items-center gap-2">
          <h2 className="text-lg font-semibold text-slate-900">
            {template.name}
          </h2>
          {template.planned ? (
            <Badge
              variant="outline"
              className="border-dashed border-slate-300 bg-slate-50 text-slate-500"
            >
              Planned
            </Badge>
          ) : (
            <ModeBadge mode={template.mode} />
          )}
        </div>
        <code className="text-xs text-slate-500">{template.key}</code>
      </header>

      <dl className="grid grid-cols-[7rem_1fr] gap-x-3 gap-y-1.5 text-sm">
        <Row label="Service">{service.label}</Row>
        <Row label="Send mode">
          {manual
            ? "Manual — staff pick it in a compose box"
            : "Automatic — sent when an event happens"}
        </Row>
        {!manual && (
          <>
            <Row label="Trigger">
              {template.trigger}
              {template.unverified.trigger && <Unverified />}
            </Row>
            <Row label="Recipients">
              {template.recipients}
              {template.unverified.recipients && <Unverified />}
            </Row>
          </>
        )}
        <Row label="Sender">
          <code>{sender.address}</code>
          {sender.tbd && (
            <Badge
              variant="outline"
              className="ml-2 border-amber-200 bg-amber-50 text-amber-800"
            >
              alias TBD
            </Badge>
          )}
        </Row>
      </dl>

      {template.planned ? (
        <p className="rounded-md border border-dashed border-slate-300 bg-slate-50 p-4 text-sm text-slate-500">
          Planned — this email doesn&apos;t exist yet, so there is no copy to
          preview.
        </p>
      ) : (
        <>
          <div className="flex flex-wrap items-center gap-3">
            {template.variants.length > 1 && (
              <div
                role="group"
                aria-label="Variant"
                className="flex flex-wrap gap-1.5"
              >
                {template.variants.map((v, i) => (
                  <button
                    key={v.label}
                    type="button"
                    aria-pressed={i === variantIndex}
                    onClick={() => setVariantIndex(i)}
                    className={`rounded-full border px-3 py-1 text-xs transition-colors ${
                      i === variantIndex
                        ? "border-slate-900 bg-slate-900 text-white"
                        : "border-slate-300 bg-white text-slate-700 hover:bg-slate-100"
                    }`}
                  >
                    {v.label}
                  </button>
                ))}
              </div>
            )}
          </div>

          <article
            aria-label="Email preview"
            className="overflow-hidden rounded-lg border border-slate-300 shadow-sm"
          >
            <div className="space-y-0.5 border-b border-slate-200 bg-slate-50 px-4 py-2 text-xs text-slate-600">
              <div>
                From: <span className="text-slate-800">{sender.address}</span>
              </div>
              <div>
                Subject:{" "}
                <span
                  aria-label="Preview subject"
                  className="font-medium text-slate-900"
                >
                  {variant.subject}
                </span>
              </div>
            </div>
            <div
              aria-label="Preview body"
              className="px-4 py-3 text-sm text-slate-800 [&_a]:text-sky-700 [&_a]:underline [&_code.placeholder]:rounded [&_code.placeholder]:border [&_code.placeholder]:border-sky-200 [&_code.placeholder]:bg-sky-50 [&_code.placeholder]:px-1 [&_code.placeholder]:font-mono [&_code.placeholder]:text-[0.85em] [&_code.placeholder]:text-sky-800 [&_li]:my-0.5 [&_mark.marker]:rounded [&_mark.marker]:bg-yellow-200 [&_mark.marker]:px-0.5 [&_p]:my-2 [&_ul]:list-disc [&_ul]:pl-5"
              dangerouslySetInnerHTML={{
                __html: previewBody(variant.body),
              }}
            />
          </article>
          {!manual && (
            <p className="text-xs text-slate-500">
              Rendered from invented sample event data.
            </p>
          )}

          {manual && (
            <div className="space-y-2 text-sm">
              <h3 className="font-medium text-slate-900">Placeholders</h3>
              <ul aria-label="Placeholders" className="space-y-1">
                {placeholders.map((p) => (
                  <li key={p}>
                    <code className="rounded border border-sky-200 bg-sky-50 px-1 font-mono text-[0.85em] text-sky-800">{`{{${p}}}`}</code>{" "}
                    <span className="text-slate-600">
                      auto-filled when sent: {PLACEHOLDER_INFO[p]}
                    </span>
                  </li>
                ))}
                {markers.map((m) => (
                  <li key={m}>
                    <mark className="rounded bg-yellow-200 px-0.5">{m}</mark>{" "}
                    <span className="text-slate-600">
                      free text the sender fills in before sending
                    </span>
                  </li>
                ))}
              </ul>
            </div>
          )}
        </>
      )}
    </section>
  );
};

export default TemplatePreview;
