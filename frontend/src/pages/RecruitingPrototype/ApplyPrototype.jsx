import { useState } from "react";
import { PlusCircle, Trash2, CheckCircle2 } from "lucide-react";

import JsonSchemaForm from "./vendor/JsonSchemaForm";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Separator } from "@/components/ui/separator";
import { Badge } from "@/components/ui/badge";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";

import { JOBS, SAMPLE_FORM_SCHEMA } from "./mockData";

/**
 * Candidate-facing Apply form for the Recruiting v2 prototype.
 *
 * Three sections mirror the v2 design spec:
 *  1. Personal  — editable contact fields (name, email, phone).
 *  2. Profile   — education rows, experience rows, resume link.
 *  3. Details   — per-job questions rendered via JsonSchemaForm.
 *
 * All state is local (mock only — no backend).  A job picker at the top lets
 * stakeholders switch postings to see how the Details section changes.
 *
 * @component
 */
const ApplyPrototype = () => {
  // ── Job selection ──────────────────────────────────────────────────────────
  const [selectedJobId, setSelectedJobId] = useState(JOBS[1].id); // default: Mentee
  const selectedJob = JOBS.find((j) => j.id === selectedJobId) ?? JOBS[0];

  // ── Section 1: Personal ───────────────────────────────────────────────────
  const [personal, setPersonal] = useState({
    firstName: "",
    lastName: "",
    email: "",
    phone: "",
  });

  const updatePersonal = (field) => (e) =>
    setPersonal((prev) => ({ ...prev, [field]: e.target.value }));

  // ── Section 2: Profile ────────────────────────────────────────────────────
  const [summary, setSummary] = useState("");
  const [resumeUrl, setResumeUrl] = useState("");

  const [education, setEducation] = useState([
    { id: 1, school: "", degree: "", years: "" },
  ]);

  const [experience, setExperience] = useState([
    { id: 1, company: "", title: "", years: "" },
  ]);

  const addEducation = () =>
    setEducation((prev) => [
      ...prev,
      { id: Date.now(), school: "", degree: "", years: "" },
    ]);

  const removeEducation = (id) =>
    setEducation((prev) => prev.filter((e) => e.id !== id));

  const updateEducation = (id, field) => (e) =>
    setEducation((prev) =>
      prev.map((row) =>
        row.id === id ? { ...row, [field]: e.target.value } : row,
      ),
    );

  const addExperience = () =>
    setExperience((prev) => [
      ...prev,
      { id: Date.now(), company: "", title: "", years: "" },
    ]);

  const removeExperience = (id) =>
    setExperience((prev) => prev.filter((e) => e.id !== id));

  const updateExperience = (id, field) => (e) =>
    setExperience((prev) =>
      prev.map((row) =>
        row.id === id ? { ...row, [field]: e.target.value } : row,
      ),
    );

  // ── Section 3: Details (JsonSchemaForm) ───────────────────────────────────
  const [answers, setAnswers] = useState({});

  // ── Submit ────────────────────────────────────────────────────────────────
  const [submitted, setSubmitted] = useState(false);

  const handleSubmit = (e) => {
    e.preventDefault();
    setSubmitted(true);
  };

  // ── Render ────────────────────────────────────────────────────────────────
  if (submitted) {
    return (
      <div className="flex min-h-screen items-center justify-center bg-background px-4">
        <div className="flex flex-col items-center gap-4 text-center max-w-sm">
          <CheckCircle2 className="h-12 w-12 text-emerald-500" />
          <h2 className="text-xl font-semibold">Application submitted!</h2>
          <p className="text-muted-foreground text-sm">
            We received your application for{" "}
            <span className="font-medium text-foreground">
              {selectedJob.title}
            </span>
            . You will hear from us by email.
          </p>
          <Button variant="outline" onClick={() => setSubmitted(false)}>
            Apply to another posting
          </Button>
        </div>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-muted/30 px-4 py-10">
      <form
        onSubmit={handleSubmit}
        className="mx-auto max-w-2xl space-y-8"
        noValidate
      >
        {/* ── Header / Job picker ── */}
        <div className="space-y-3">
          <div className="flex items-center gap-3">
            <h1 className="text-2xl font-bold tracking-tight">
              Apply for a position
            </h1>
            <Badge variant="outline" className="text-xs">
              v2 prototype
            </Badge>
          </div>

          <div className="space-y-1.5">
            <Label htmlFor="job-picker">Posting</Label>
            <Select
              value={String(selectedJobId)}
              onValueChange={(v) => {
                setSelectedJobId(Number(v));
                setAnswers({});
              }}
            >
              <SelectTrigger id="job-picker" className="w-full">
                <SelectValue placeholder="Select a posting" />
              </SelectTrigger>
              <SelectContent>
                {JOBS.map((job) => (
                  <SelectItem key={job.id} value={String(job.id)}>
                    {job.title}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
            {selectedJob.description && (
              <p className="text-muted-foreground text-sm">
                {selectedJob.description}
              </p>
            )}
          </div>
        </div>

        <Separator />

        {/* ── Section 1: Personal ── */}
        <Card>
          <CardHeader className="pb-2">
            <CardTitle className="text-base font-semibold">
              1 · Personal
            </CardTitle>
            <p className="text-muted-foreground text-sm">
              You can edit these — your account may not have them yet.
            </p>
          </CardHeader>
          <CardContent className="space-y-4">
            <div className="grid grid-cols-2 gap-4">
              <div className="space-y-1.5">
                <Label htmlFor="firstName">First name</Label>
                <Input
                  id="firstName"
                  placeholder="Jane"
                  value={personal.firstName}
                  onChange={updatePersonal("firstName")}
                />
              </div>
              <div className="space-y-1.5">
                <Label htmlFor="lastName">Last name</Label>
                <Input
                  id="lastName"
                  placeholder="Smith"
                  value={personal.lastName}
                  onChange={updatePersonal("lastName")}
                />
              </div>
            </div>

            <div className="space-y-1.5">
              <Label htmlFor="email">Email</Label>
              <Input
                id="email"
                type="email"
                placeholder="jane@example.com"
                value={personal.email}
                onChange={updatePersonal("email")}
              />
            </div>

            <div className="space-y-1.5">
              <Label htmlFor="phone">Phone</Label>
              <Input
                id="phone"
                type="tel"
                placeholder="+1 (555) 000-0000"
                value={personal.phone}
                onChange={updatePersonal("phone")}
              />
            </div>
          </CardContent>
        </Card>

        {/* ── Section 2: Profile ── */}
        <Card>
          <CardHeader className="pb-2">
            <CardTitle className="text-base font-semibold">
              2 · Profile
            </CardTitle>
            <p className="text-muted-foreground text-sm">
              This info is reused across all your applications.
            </p>
          </CardHeader>
          <CardContent className="space-y-6">
            {/* Education */}
            <div className="space-y-2">
              <div className="flex items-center justify-between">
                <div className="flex items-center gap-2">
                  <span className="text-sm font-medium">Education</span>
                  <span className="text-muted-foreground text-xs">
                    (recommended)
                  </span>
                </div>
                <Button
                  type="button"
                  variant="ghost"
                  size="sm"
                  className="h-7 gap-1 text-xs"
                  onClick={addEducation}
                >
                  <PlusCircle className="h-3.5 w-3.5" />
                  Add
                </Button>
              </div>

              <div className="space-y-2">
                {education.map((row) => (
                  <div
                    key={row.id}
                    className="flex items-start gap-2 rounded-lg border bg-background p-3"
                  >
                    <div className="grid flex-1 grid-cols-3 gap-2">
                      <Input
                        placeholder="School"
                        value={row.school}
                        onChange={updateEducation(row.id, "school")}
                        className="text-sm"
                      />
                      <Input
                        placeholder="Degree / Major"
                        value={row.degree}
                        onChange={updateEducation(row.id, "degree")}
                        className="text-sm"
                      />
                      <Input
                        placeholder="Years (e.g. 2022–2026)"
                        value={row.years}
                        onChange={updateEducation(row.id, "years")}
                        className="text-sm"
                      />
                    </div>
                    {education.length > 1 && (
                      <button
                        type="button"
                        onClick={() => removeEducation(row.id)}
                        className="mt-2 text-muted-foreground hover:text-destructive transition-colors"
                        aria-label="Remove education row"
                      >
                        <Trash2 className="h-4 w-4" />
                      </button>
                    )}
                  </div>
                ))}
              </div>
            </div>

            <Separator />

            {/* Experience */}
            <div className="space-y-2">
              <div className="flex items-center justify-between">
                <div className="flex items-center gap-2">
                  <span className="text-sm font-medium">Experience</span>
                  <span className="text-muted-foreground text-xs">
                    (recommended)
                  </span>
                </div>
                <Button
                  type="button"
                  variant="ghost"
                  size="sm"
                  className="h-7 gap-1 text-xs"
                  onClick={addExperience}
                >
                  <PlusCircle className="h-3.5 w-3.5" />
                  Add
                </Button>
              </div>

              <div className="space-y-2">
                {experience.map((row) => (
                  <div
                    key={row.id}
                    className="flex items-start gap-2 rounded-lg border bg-background p-3"
                  >
                    <div className="grid flex-1 grid-cols-3 gap-2">
                      <Input
                        placeholder="Company"
                        value={row.company}
                        onChange={updateExperience(row.id, "company")}
                        className="text-sm"
                      />
                      <Input
                        placeholder="Title / Role"
                        value={row.title}
                        onChange={updateExperience(row.id, "title")}
                        className="text-sm"
                      />
                      <Input
                        placeholder="Years (e.g. 2024)"
                        value={row.years}
                        onChange={updateExperience(row.id, "years")}
                        className="text-sm"
                      />
                    </div>
                    {experience.length > 1 && (
                      <button
                        type="button"
                        onClick={() => removeExperience(row.id)}
                        className="mt-2 text-muted-foreground hover:text-destructive transition-colors"
                        aria-label="Remove experience row"
                      >
                        <Trash2 className="h-4 w-4" />
                      </button>
                    )}
                  </div>
                ))}
              </div>
            </div>

            <Separator />

            {/* Summary — short personal intro / bio */}
            <div className="space-y-1.5">
              <div className="flex items-center gap-2">
                <Label htmlFor="summary">Summary</Label>
                <span className="text-muted-foreground text-xs">
                  (recommended)
                </span>
              </div>
              <textarea
                id="summary"
                rows={3}
                placeholder="A short intro about your background, focus, and what you're looking for…"
                value={summary}
                onChange={(e) => setSummary(e.target.value)}
                className="w-full rounded-md border border-input bg-background px-3 py-2 text-sm shadow-sm placeholder:text-muted-foreground focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-ring resize-y"
              />
            </div>

            <Separator />

            {/* Resume link */}
            <div className="space-y-1.5">
              <Label htmlFor="resumeUrl">Resume link</Label>
              <Input
                id="resumeUrl"
                type="url"
                placeholder="https://drive.google.com/…"
                value={resumeUrl}
                onChange={(e) => setResumeUrl(e.target.value)}
              />
              <p className="text-muted-foreground text-xs">
                Paste a shareable Google Drive, Dropbox, or similar link.
              </p>
            </div>
          </CardContent>
        </Card>

        {/* ── Section 3: Details ── */}
        <Card>
          <CardHeader className="pb-2">
            <CardTitle className="text-base font-semibold">
              3 · Details
            </CardTitle>
            <p className="text-muted-foreground text-sm">
              Questions specific to{" "}
              <span className="font-medium text-foreground">
                {selectedJob.title}
              </span>
              .
            </p>
          </CardHeader>
          <CardContent>
            <JsonSchemaForm
              schema={SAMPLE_FORM_SCHEMA}
              value={answers}
              onChange={setAnswers}
            />
          </CardContent>
        </Card>

        {/* ── Submit ── */}
        <div className="flex justify-end pb-4">
          <Button type="submit" size="lg" className="px-8">
            Submit application
          </Button>
        </div>
      </form>
    </div>
  );
};

export default ApplyPrototype;
