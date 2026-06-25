import { useState } from "react";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";

/** A titled bullet list; renders nothing when empty. */
function Section({ title, rows }) {
  if (!rows || rows.length === 0) return null;
  return (
    <div>
      <div className="font-medium">{title}</div>
      <ul className="list-disc pl-5">
        {rows.map((r, i) => (
          <li key={i}>{r}</li>
        ))}
      </ul>
    </div>
  );
}

/**
 * Read-only summary of the confirmed resume data plus a collapsible, copyable
 * JSON block. onReset returns to the upload step.
 *
 * @param {{ data: object, onReset: () => void }} props
 */
export default function ParsedResultView({ data, onReset }) {
  const [copied, setCopied] = useState(false);
  const json = JSON.stringify(data, null, 2);
  const u = data?.user ?? {};
  const fullName = `${u.firstName ?? ""} ${u.lastName ?? ""}`.trim();

  const copy = async () => {
    try {
      await navigator.clipboard?.writeText(json);
      setCopied(true);
    } catch {
      setCopied(false);
    }
  };

  return (
    <div className="mx-auto flex max-w-2xl flex-col gap-6">
      <Card>
        <CardHeader>
          <CardTitle>{fullName || "（无姓名）"}</CardTitle>
        </CardHeader>
        <CardContent className="flex flex-col gap-2 text-sm">
          {u.phone && <div>电话：{u.phone}</div>}
          {u.linkedinLink && <div>LinkedIn：{u.linkedinLink}</div>}
          {u.timezoneSuggestion && <div>时区：{u.timezoneSuggestion}</div>}
          <Section
            title="教育经历"
            rows={(data?.education ?? []).map((e) =>
              [e.school, e.degree, e.fieldOfStudy].filter(Boolean).join(" · "),
            )}
          />
          <Section
            title="工作经历"
            rows={(data?.workHistory ?? []).map((w) =>
              [w.title, w.companyOrOrganization].filter(Boolean).join(" @ "),
            )}
          />
          {data?.unmapped?.summary && <div>摘要：{data.unmapped.summary}</div>}
        </CardContent>
      </Card>

      <Card>
        <CardHeader className="flex flex-row items-center justify-between">
          <CardTitle>JSON</CardTitle>
          <Button type="button" variant="outline" size="sm" onClick={copy}>
            {copied ? "已复制" : "复制"}
          </Button>
        </CardHeader>
        <CardContent>
          <pre
            data-testid="result-json"
            className="max-h-80 overflow-auto rounded-md bg-muted p-3 text-xs"
          >
            {json}
          </pre>
        </CardContent>
      </Card>

      <div className="flex justify-end">
        <Button type="button" variant="outline" onClick={onReset}>
          重新上传
        </Button>
      </div>
    </div>
  );
}
