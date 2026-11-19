import { Info } from "lucide-react";
import { Button } from "@/components/ui/button";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import EmailFlowDiagram from "@/pages/WorkGuide/EmailFlowDiagram";
import { blockHeading } from "@/pages/WorkGuide/guideModel";
import { renderBody } from "@/whatsNew/renderBody";

const DIAGRAMS = { emailFlow: EmailFlowDiagram };

const SectionHeading = ({ id, children }) => (
  <h2 id={id} className="mt-2 scroll-mt-28 text-xl font-semibold">
    {children}
  </h2>
);

const Steps = ({ steps, onOpen }) => (
  <ol className="flex flex-col gap-7">
    {steps.map((step, index) => (
      <li key={index} className="flex gap-4">
        <span className="flex size-7 shrink-0 items-center justify-center rounded-full bg-primary text-sm font-semibold text-primary-foreground">
          {index + 1}
        </span>
        <div className="flex min-w-0 flex-1 flex-col gap-2.5">
          <p className="mt-0.5 leading-relaxed">{renderBody(step.text)}</p>
          {step.image && (
            <img
              src={step.image}
              alt={step.imageAlt ?? ""}
              loading="lazy"
              decoding="async"
              className="max-w-full rounded-lg border"
            />
          )}
          {step.route && (
            <Button
              variant="link"
              className="h-auto self-start p-0 font-semibold"
              onClick={() => onOpen(step)}
            >
              Open in Purrf →
            </Button>
          )}
        </div>
      </li>
    ))}
  </ol>
);

const GoodToKnow = ({ items }) => (
  <div className="flex gap-3 rounded-xl border border-primary/30 bg-primary/5 px-5 py-4">
    <Info className="mt-0.5 size-5 shrink-0 text-primary" aria-hidden="true" />
    <ul className="flex list-disc flex-col gap-2 pl-4 text-sm leading-relaxed">
      {items.map((item, index) => (
        <li key={index}>{renderBody(item)}</li>
      ))}
    </ul>
  </div>
);

const GuideTable = ({ columns, rows }) => (
  <div className="rounded-lg border">
    <Table>
      <TableHeader>
        <TableRow>
          {columns.map((column) => (
            <TableHead key={column}>{column}</TableHead>
          ))}
        </TableRow>
      </TableHeader>
      <TableBody>
        {rows.map((row, r) => (
          <TableRow key={r}>
            {row.map((cell, c) => (
              <TableCell key={c} className="align-top whitespace-normal">
                {renderBody(cell)}
              </TableCell>
            ))}
          </TableRow>
        ))}
      </TableBody>
    </Table>
  </div>
);

const renderBlock = (block, onOpen) => {
  switch (block.type) {
    case "text":
      return <p className="leading-relaxed">{renderBody(block.text)}</p>;
    case "steps":
      return <Steps steps={block.steps} onOpen={onOpen} />;
    case "goodToKnow":
      return <GoodToKnow items={block.items} />;
    case "table":
      return <GuideTable columns={block.columns} rows={block.rows} />;
    case "diagram": {
      const Diagram = DIAGRAMS[block.name];
      return Diagram ? <Diagram /> : null;
    }
    default:
      return null;
  }
};

/**
 * Renders a flow's blocks in order. A block with a section heading gets an
 * `<h2>` whose id is taken, in order, from `headingIds`.
 *
 * @param {Object} props
 * @param {Array<Object>} props.blocks - The flow's blocks.
 * @param {string[]} props.headingIds - Ids for the blocks' headings, in the
 *   order `headingsOf` lists them.
 * @param {(step: Object) => void} props.onOpen - Follows a step's
 *   "Open in Purrf" link.
 * @returns {JSX.Element}
 */
const GuideBlocks = ({ blocks, headingIds, onOpen }) => {
  let next = 0;
  return (
    <div className="flex flex-col gap-6">
      {blocks.map((block, index) => {
        const heading = blockHeading(block);
        const id = heading === null ? null : headingIds[next++];
        return (
          <section key={index} className="flex flex-col gap-4">
            {heading !== null && (
              <SectionHeading id={id}>{heading}</SectionHeading>
            )}
            {block.type !== "heading" && renderBlock(block, onOpen)}
          </section>
        );
      })}
    </div>
  );
};

export default GuideBlocks;
