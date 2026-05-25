import type { ReactNode } from "react";

type Props = {
  markdown: string;
};

type Block =
  | { type: "heading"; level: number; text: string }
  | { type: "paragraph"; text: string }
  | { type: "blockquote"; text: string }
  | { type: "fieldList"; label: string; items: string[] }
  | { type: "fieldInline"; label: string; value: string }
  | { type: "ul"; items: string[] }
  | { type: "ol"; items: string[] };

const FIELD_LABELS = new Set([
  "required inputs",
  "produces",
  "outputs",
  "tools",
  "approver",
  "decision rules",
  "notes",
  "note",
]);

function stripInlineMarkdown(text: string): string {
  return text.replace(/^\*\*/, "").replace(/\*\*$/, "").trim();
}

function parseFieldLabel(line: string): { label: string; value: string } | null {
  const normalized = stripInlineMarkdown(line);
  const match = /^([A-Za-z][A-Za-z\s/-]*):\s*(.*)$/.exec(normalized);
  if (!match) return null;
  const label = match[1].trim();
  if (!FIELD_LABELS.has(label.toLowerCase())) return null;
  return { label, value: match[2].replace(/^\*\*\s*/, "").trim() };
}

function isBlockBoundary(line: string): boolean {
  return (
    !line ||
    /^(#{1,4})\s+/.test(line) ||
    line.startsWith(">") ||
    parseFieldLabel(line) !== null
  );
}

function parseMarkdown(markdown: string): Block[] {
  const blocks: Block[] = [];
  const lines = markdown.replace(/\r\n/g, "\n").split("\n");
  let paragraph: string[] = [];
  let listItems: string[] = [];
  let listType: "ul" | "ol" | null = null;

  function flushParagraph() {
    if (paragraph.length) {
      blocks.push({ type: "paragraph", text: paragraph.join(" ") });
      paragraph = [];
    }
  }

  function flushList() {
    if (listType && listItems.length) {
      blocks.push({ type: listType, items: listItems });
      listItems = [];
      listType = null;
    }
  }

  for (let index = 0; index < lines.length; index += 1) {
    const rawLine = lines[index];
    const line = rawLine.trim();
    if (!line) {
      flushParagraph();
      flushList();
      continue;
    }

    const field = parseFieldLabel(line);
    if (field) {
      flushParagraph();
      flushList();
      const items: string[] = [];
      if (field.value) items.push(field.value);

      let lookahead = index + 1;
      while (lookahead < lines.length) {
        const next = lines[lookahead].trim();
        if (isBlockBoundary(next)) break;

        const unordered = /^[-*]\s+(.+)$/.exec(next);
        const ordered = /^\d+\.\s+(.+)$/.exec(next);
        items.push(unordered?.[1] ?? ordered?.[1] ?? next);
        lookahead += 1;
      }

      index = lookahead - 1;
      if (items.length > 1 || !field.value) {
        blocks.push({ type: "fieldList", label: field.label, items });
      } else {
        blocks.push({ type: "fieldInline", label: field.label, value: items[0] });
      }
      continue;
    }

    const heading = /^(#{1,4})\s+(.+)$/.exec(line);
    if (heading) {
      flushParagraph();
      flushList();
      blocks.push({ type: "heading", level: heading[1].length, text: heading[2] });
      continue;
    }

    if (line.startsWith(">")) {
      flushParagraph();
      flushList();
      blocks.push({ type: "blockquote", text: line.replace(/^>\s?/, "") });
      continue;
    }

    const unordered = /^[-*]\s+(.+)$/.exec(line);
    if (unordered) {
      flushParagraph();
      if (listType !== "ul") flushList();
      listType = "ul";
      listItems.push(unordered[1]);
      continue;
    }

    const ordered = /^\d+\.\s+(.+)$/.exec(line);
    if (ordered) {
      flushParagraph();
      if (listType !== "ol") flushList();
      listType = "ol";
      listItems.push(ordered[1]);
      continue;
    }

    flushList();
    paragraph.push(line);
  }

  flushParagraph();
  flushList();
  return blocks;
}

function renderInline(text: string): ReactNode[] {
  const nodes: ReactNode[] = [];
  const pattern = /(\*\*[^*]+\*\*|`[^`]+`)/g;
  let cursor = 0;
  let match: RegExpExecArray | null;

  while ((match = pattern.exec(text)) !== null) {
    if (match.index > cursor) nodes.push(text.slice(cursor, match.index));
    const token = match[0];
    if (token.startsWith("**")) {
      nodes.push(<strong key={`${match.index}-strong`}>{token.slice(2, -2)}</strong>);
    } else {
      nodes.push(<code key={`${match.index}-code`}>{token.slice(1, -1)}</code>);
    }
    cursor = match.index + token.length;
  }

  if (cursor < text.length) nodes.push(text.slice(cursor));
  return nodes;
}

export default function MarkdownDocument({ markdown }: Props) {
  const blocks = parseMarkdown(markdown);

  return (
    <div className="sop-rendered">
      {blocks.map((block, index) => {
        if (block.type === "heading") {
          if (block.level === 1) return null;
          const Heading = block.level === 2 ? "h2" : block.level === 3 ? "h3" : "h4";
          return <Heading key={index}>{renderInline(block.text)}</Heading>;
        }
        if (block.type === "paragraph") {
          return <p key={index}>{renderInline(block.text)}</p>;
        }
        if (block.type === "blockquote") {
          return <blockquote key={index}>{renderInline(block.text)}</blockquote>;
        }
        if (block.type === "fieldList") {
          return (
            <section className="sop-field" key={index}>
              <div className="sop-field-label">{renderInline(block.label)}</div>
              {block.items.length > 0 ? (
                <ul>
                  {block.items.map((item, itemIndex) => (
                    <li key={itemIndex}>{renderInline(item)}</li>
                  ))}
                </ul>
              ) : (
                <p className="sop-field-empty">Not specified.</p>
              )}
            </section>
          );
        }
        if (block.type === "fieldInline") {
          return (
            <p className="sop-field-inline" key={index}>
              <strong>{block.label}:</strong> {renderInline(block.value)}
            </p>
          );
        }
        if (block.type === "ul") {
          return (
            <ul key={index}>
              {block.items.map((item, itemIndex) => (
                <li key={itemIndex}>{renderInline(item)}</li>
              ))}
            </ul>
          );
        }
        return (
          <ol key={index}>
            {block.items.map((item, itemIndex) => (
              <li key={itemIndex}>{renderInline(item)}</li>
            ))}
          </ol>
        );
      })}
    </div>
  );
}
