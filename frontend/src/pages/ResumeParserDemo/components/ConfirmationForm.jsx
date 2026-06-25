import { useState } from "react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Checkbox } from "@/components/ui/checkbox";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import TimezoneSelector from "@/components/common/TimezoneSelector";
import { DEGREE_OPTIONS } from "../constants";

let keySeq = 0;
/** Add a stable local key for React list rendering. */
const withKey = (obj) => ({ _key: `row-${keySeq++}`, ...obj });
/** Drop the local _key field before emitting. */
const stripKey = ({ _key, ...rest }) => rest;

/** Label + control wrapper. @param {{label:string,id:string,children:any}} p */
function Field({ label, id, children }) {
  return (
    <div>
      <Label htmlFor={id} className="mb-1 block">
        {label}
      </Label>
      {children}
    </div>
  );
}

/**
 * Editable, pre-filled resume confirmation form. Seeds local state from the
 * parsed result; on submit emits the same ParsedResume shape with local _key
 * fields stripped and empty optional strings normalized to undefined.
 *
 * @param {{ initial: object, onConfirm: (data: object) => void }} props
 */
export default function ConfirmationForm({ initial, onConfirm }) {
  const [user, setUser] = useState({
    firstName: initial?.user?.firstName ?? "",
    lastName: initial?.user?.lastName ?? "",
    phone: initial?.user?.phone ?? "",
    linkedinLink: initial?.user?.linkedinLink ?? "",
    timezoneSuggestion: initial?.user?.timezoneSuggestion ?? "",
  });
  const [education, setEducation] = useState(
    (initial?.education ?? []).map((e) =>
      withKey({
        school: e.school ?? "",
        degree: e.degree ?? "",
        fieldOfStudy: e.fieldOfStudy ?? "",
        startDate: e.startDate ?? "",
        endDate: e.endDate ?? "",
      }),
    ),
  );
  const [workHistory, setWorkHistory] = useState(
    (initial?.workHistory ?? []).map((w) =>
      withKey({
        title: w.title ?? "",
        companyOrOrganization: w.companyOrOrganization ?? "",
        startDate: w.startDate ?? "",
        endDate: w.endDate ?? "",
        isCurrentJob: Boolean(w.isCurrentJob),
      }),
    ),
  );
  const [summary, setSummary] = useState(initial?.unmapped?.summary ?? "");

  const isEmpty =
    !user.firstName &&
    !user.lastName &&
    education.length === 0 &&
    workHistory.length === 0;

  const setUserField = (k) => (e) =>
    setUser((u) => ({ ...u, [k]: e.target.value }));

  const updateRow = (setter) => (key, field, value) =>
    setter((rows) =>
      rows.map((r) => (r._key === key ? { ...r, [field]: value } : r)),
    );
  const addRow = (setter, blank) => () =>
    setter((rows) => [...rows, withKey(blank)]);
  const removeRow = (setter) => (key) =>
    setter((rows) => rows.filter((r) => r._key !== key));

  const updateEdu = updateRow(setEducation);
  const updateWork = updateRow(setWorkHistory);

  const handleSubmit = (e) => {
    e.preventDefault();
    onConfirm({
      user: {
        firstName: user.firstName,
        lastName: user.lastName,
        phone: user.phone || undefined,
        linkedinLink: user.linkedinLink || undefined,
        timezoneSuggestion: user.timezoneSuggestion || undefined,
      },
      education: education.map(stripKey),
      workHistory: workHistory.map(stripKey),
      unmapped: { summary: summary || undefined },
    });
  };

  return (
    <form
      onSubmit={handleSubmit}
      className="mx-auto flex max-w-2xl flex-col gap-6"
    >
      {isEmpty && (
        <p className="rounded-md bg-muted p-3 text-sm text-muted-foreground">
          没能从这个 PDF 解析出内容，请手动填写。
        </p>
      )}

      <Card>
        <CardHeader>
          <CardTitle>基本信息</CardTitle>
        </CardHeader>
        <CardContent className="grid grid-cols-1 gap-4 sm:grid-cols-2">
          <Field label="名 (First name)" id="firstName">
            <Input
              id="firstName"
              value={user.firstName}
              onChange={setUserField("firstName")}
            />
          </Field>
          <Field label="姓 (Last name)" id="lastName">
            <Input
              id="lastName"
              value={user.lastName}
              onChange={setUserField("lastName")}
            />
          </Field>
          <Field label="电话" id="phone">
            <Input
              id="phone"
              value={user.phone}
              onChange={setUserField("phone")}
            />
          </Field>
          <Field label="LinkedIn" id="linkedinLink">
            <Input
              id="linkedinLink"
              value={user.linkedinLink}
              onChange={setUserField("linkedinLink")}
            />
          </Field>
          <div className="sm:col-span-2">
            <Label className="mb-1 block">时区</Label>
            <TimezoneSelector
              value={user.timezoneSuggestion}
              onChange={(opt) =>
                setUser((u) => ({
                  ...u,
                  timezoneSuggestion: opt?.value ?? "",
                }))
              }
            />
          </div>
        </CardContent>
      </Card>

      <Card>
        <CardHeader className="flex flex-row items-center justify-between">
          <CardTitle>教育经历</CardTitle>
          <Button
            type="button"
            variant="outline"
            size="sm"
            onClick={addRow(setEducation, {
              school: "",
              degree: "",
              fieldOfStudy: "",
              startDate: "",
              endDate: "",
            })}
          >
            添加教育
          </Button>
        </CardHeader>
        <CardContent className="flex flex-col gap-4">
          {education.length === 0 && (
            <p className="text-sm text-muted-foreground">暂无</p>
          )}
          {education.map((row) => (
            <div
              key={row._key}
              className="grid grid-cols-1 gap-3 rounded-md border p-3 sm:grid-cols-2"
            >
              <Field label="学校" id={`school-${row._key}`}>
                <Input
                  id={`school-${row._key}`}
                  value={row.school}
                  onChange={(e) =>
                    updateEdu(row._key, "school", e.target.value)
                  }
                />
              </Field>
              <div>
                <Label htmlFor={`degree-${row._key}`} className="mb-1 block">
                  学位
                </Label>
                <select
                  id={`degree-${row._key}`}
                  value={row.degree}
                  onChange={(e) =>
                    updateEdu(row._key, "degree", e.target.value)
                  }
                  className="h-9 w-full rounded-md border border-input bg-transparent px-3 text-sm"
                >
                  <option value="">（未指定）</option>
                  {DEGREE_OPTIONS.map((d) => (
                    <option key={d} value={d}>
                      {d}
                    </option>
                  ))}
                </select>
              </div>
              <Field label="专业" id={`field-${row._key}`}>
                <Input
                  id={`field-${row._key}`}
                  value={row.fieldOfStudy}
                  onChange={(e) =>
                    updateEdu(row._key, "fieldOfStudy", e.target.value)
                  }
                />
              </Field>
              <div className="grid grid-cols-2 gap-2">
                <Field label="开始" id={`edu-start-${row._key}`}>
                  <Input
                    id={`edu-start-${row._key}`}
                    value={row.startDate}
                    placeholder="YYYY-MM-DD"
                    onChange={(e) =>
                      updateEdu(row._key, "startDate", e.target.value)
                    }
                  />
                </Field>
                <Field label="结束" id={`edu-end-${row._key}`}>
                  <Input
                    id={`edu-end-${row._key}`}
                    value={row.endDate}
                    placeholder="YYYY-MM-DD"
                    onChange={(e) =>
                      updateEdu(row._key, "endDate", e.target.value)
                    }
                  />
                </Field>
              </div>
              <div className="sm:col-span-2">
                <Button
                  type="button"
                  variant="ghost"
                  size="sm"
                  onClick={() => removeRow(setEducation)(row._key)}
                >
                  删除
                </Button>
              </div>
            </div>
          ))}
        </CardContent>
      </Card>

      <Card>
        <CardHeader className="flex flex-row items-center justify-between">
          <CardTitle>工作经历</CardTitle>
          <Button
            type="button"
            variant="outline"
            size="sm"
            onClick={addRow(setWorkHistory, {
              title: "",
              companyOrOrganization: "",
              startDate: "",
              endDate: "",
              isCurrentJob: false,
            })}
          >
            添加工作
          </Button>
        </CardHeader>
        <CardContent className="flex flex-col gap-4">
          {workHistory.length === 0 && (
            <p className="text-sm text-muted-foreground">暂无</p>
          )}
          {workHistory.map((row) => (
            <div
              key={row._key}
              className="grid grid-cols-1 gap-3 rounded-md border p-3 sm:grid-cols-2"
            >
              <Field label="职位" id={`title-${row._key}`}>
                <Input
                  id={`title-${row._key}`}
                  value={row.title}
                  onChange={(e) =>
                    updateWork(row._key, "title", e.target.value)
                  }
                />
              </Field>
              <Field label="公司/组织" id={`company-${row._key}`}>
                <Input
                  id={`company-${row._key}`}
                  value={row.companyOrOrganization}
                  onChange={(e) =>
                    updateWork(
                      row._key,
                      "companyOrOrganization",
                      e.target.value,
                    )
                  }
                />
              </Field>
              <div className="grid grid-cols-2 gap-2">
                <Field label="开始" id={`work-start-${row._key}`}>
                  <Input
                    id={`work-start-${row._key}`}
                    value={row.startDate}
                    placeholder="YYYY-MM-DD"
                    onChange={(e) =>
                      updateWork(row._key, "startDate", e.target.value)
                    }
                  />
                </Field>
                <Field label="结束" id={`work-end-${row._key}`}>
                  <Input
                    id={`work-end-${row._key}`}
                    value={row.endDate}
                    placeholder="YYYY-MM-DD"
                    disabled={row.isCurrentJob}
                    onChange={(e) =>
                      updateWork(row._key, "endDate", e.target.value)
                    }
                  />
                </Field>
              </div>
              <label className="flex items-center gap-2 text-sm sm:col-span-2">
                <Checkbox
                  checked={row.isCurrentJob}
                  onCheckedChange={(v) =>
                    updateWork(row._key, "isCurrentJob", Boolean(v))
                  }
                />
                目前在职
              </label>
              <div className="sm:col-span-2">
                <Button
                  type="button"
                  variant="ghost"
                  size="sm"
                  onClick={() => removeRow(setWorkHistory)(row._key)}
                >
                  删除
                </Button>
              </div>
            </div>
          ))}
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>摘要</CardTitle>
        </CardHeader>
        <CardContent>
          <textarea
            value={summary}
            rows={4}
            onChange={(e) => setSummary(e.target.value)}
            className="w-full rounded-md border border-input bg-transparent p-3 text-sm"
          />
        </CardContent>
      </Card>

      <div className="flex justify-end">
        <Button type="submit">确认</Button>
      </div>
    </form>
  );
}
