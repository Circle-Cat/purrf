import { PDFDocument, StandardFonts, rgb } from "pdf-lib";

/**
 * Build a single-page PDF from an array of visual lines for parser tests.
 * pdf-lib's font support is limited, so we use the standard Helvetica family
 * (Helvetica / Helvetica-Bold) — pdf.js then reads a name containing "Bold"
 * so isBold() actually fires. Origin is bottom-left in PDF space.
 *
 * @param {{ text: string, x?: number, y?: number, size?: number, bold?: boolean }[][]} lines
 * @returns {Promise<Uint8Array>}
 */
export async function makeResumePdf(lines) {
  const doc = await PDFDocument.create();
  const page = doc.addPage([612, 792]); // US Letter
  const regular = await doc.embedFont(StandardFonts.Helvetica);
  const bold = await doc.embedFont(StandardFonts.HelveticaBold);
  let cursorY = 740;
  for (const line of lines) {
    let cursorX = 60;
    for (const token of line) {
      const size = token.size ?? 11;
      const font = token.bold ? bold : regular;
      const x = token.x ?? cursorX;
      const y = token.y ?? cursorY;
      page.drawText(token.text, { x, y, size, font, color: rgb(0, 0, 0) });
      cursorX = x + font.widthOfTextAtSize(token.text, size) + 4;
    }
    cursorY -= 22;
  }
  return doc.save();
}
