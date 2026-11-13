import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

const ROOT = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..");
export const RESUME_DIR = path.join(ROOT, ".state", "resume");

/**
 * Two one-page résumés laid out the way the in-browser parser
 * (frontend/src/lib/resume-parser) reads them: the name in bold on the first
 * line, contact lines under it, then bold all-caps EDUCATION and EXPERIENCE
 * titles. Every value is what the specs expect to see prefilled.
 */
export const RESUMES = {
  first: {
    file: "e2e-resume-quinn.pdf",
    firstName: "Quinn",
    lastName: "Parsewell",
    linkedin: "linkedin.com/in/quinn-parsewell-e2e",
    school: "Example State University",
    degree: "Bachelor",
    field: "Computer Science",
    eduStart: ["September", "2014"],
    eduEnd: ["May", "2018"],
    title: "Software Engineer",
    company: "Example Robotics Inc",
    jobStart: ["June", "2018"],
    current: true,
  },
  second: {
    file: "e2e-resume-riley.pdf",
    firstName: "Riley",
    lastName: "Swapsworth",
    linkedin: "linkedin.com/in/riley-swapsworth-e2e",
    school: "Second Example College",
    degree: "Master",
    field: "Data Science",
    eduStart: ["August", "2019"],
    eduEnd: ["June", "2021"],
    title: "Data Analyst",
    company: "Northwind Labs",
    jobStart: ["July", "2021"],
    current: true,
  },
};

const MONTH_ABBR = {
  January: "Jan",
  February: "Feb",
  March: "Mar",
  April: "Apr",
  May: "May",
  June: "Jun",
  July: "Jul",
  August: "Aug",
  September: "Sep",
  October: "Oct",
  November: "Nov",
  December: "Dec",
};

const when = ([month, year]) => `${MONTH_ABBR[month]} ${year}`;

/** The lines of a résumé: [font, size, y, text]; F2 is bold. */
function linesOf(r) {
  return [
    ["F2", 18, 740, `${r.firstName} ${r.lastName}`],
    ["F1", 10, 722, `${r.firstName.toLowerCase()}@example.com`],
    ["F1", 10, 708, r.linkedin],
    ["F2", 12, 680, "EDUCATION"],
    ["F2", 10, 664, r.school],
    ["F1", 10, 650, `${r.degree} of Science in ${r.field}`],
    ["F1", 10, 636, `${when(r.eduStart)} - ${when(r.eduEnd)}`],
    ["F2", 12, 606, "EXPERIENCE"],
    ["F2", 10, 590, r.company],
    ["F1", 10, 576, r.title],
    ["F1", 10, 562, `${when(r.jobStart)} - Present`],
    ["F1", 10, 548, "- Kept the end-to-end suite honest"],
  ];
}

const escape = (text) => text.replace(/[\\()]/g, (c) => `\\${c}`);

/** A minimal PDF 1.4 with the two standard Helvetica fonts. Deterministic. */
export function resumePdf(r) {
  const content = linesOf(r)
    .map(
      ([font, size, y, text]) =>
        `BT /${font} ${size} Tf 1 0 0 1 72 ${y} Tm (${escape(text)}) Tj ET`,
    )
    .join("\n");
  const objects = [
    "<< /Type /Catalog /Pages 2 0 R >>",
    "<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
    "<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] /Resources << /Font << /F1 4 0 R /F2 5 0 R >> >> /Contents 6 0 R >>",
    "<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica /Encoding /WinAnsiEncoding >>",
    "<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica-Bold /Encoding /WinAnsiEncoding >>",
    `<< /Length ${Buffer.byteLength(content)} >>\nstream\n${content}\nendstream`,
  ];
  let out = "%PDF-1.4\n";
  const offsets = [];
  objects.forEach((body, i) => {
    offsets.push(Buffer.byteLength(out));
    out += `${i + 1} 0 obj\n${body}\nendobj\n`;
  });
  const xref = Buffer.byteLength(out);
  out += `xref\n0 ${objects.length + 1}\n0000000000 65535 f \n`;
  for (const off of offsets)
    out += `${String(off).padStart(10, "0")} 00000 n \n`;
  out += `trailer\n<< /Size ${objects.length + 1} /Root 1 0 R >>\nstartxref\n${xref}\n%%EOF\n`;
  return Buffer.from(out, "latin1");
}

/** Write both résumés and a non-PDF file into `dir`; returns their paths. */
export function writeResumeFixtures(dir = RESUME_DIR) {
  fs.mkdirSync(dir, { recursive: true });
  const paths = {};
  for (const [key, r] of Object.entries(RESUMES)) {
    paths[key] = path.join(dir, r.file);
    fs.writeFileSync(paths[key], resumePdf(r));
  }
  paths.notPdf = path.join(dir, "e2e-resume.txt");
  fs.writeFileSync(paths.notPdf, "Not a PDF.\n");
  return paths;
}

if (process.argv[1] === fileURLToPath(import.meta.url)) {
  console.log(writeResumeFixtures(process.argv[2] ?? RESUME_DIR));
}
