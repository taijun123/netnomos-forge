import type { ReactNode } from "react";

function renderInline(text: string): ReactNode[] {
  const parts = text.split(/(`[^`]+`|\*\*[^*]+\*\*)/g);
  return parts.map((part, index) => {
    if (part.startsWith("`") && part.endsWith("`")) {
      return <code key={index}>{part.slice(1, -1)}</code>;
    }
    if (part.startsWith("**") && part.endsWith("**")) {
      return <strong key={index}>{part.slice(2, -2)}</strong>;
    }
    return part;
  });
}

function splitTableRow(line: string): string[] {
  return line.trim().replace(/^\|/, "").replace(/\|$/, "").split("|").map((cell) => cell.trim());
}

function isTableSeparator(line: string): boolean {
  const cells = splitTableRow(line);
  return cells.length > 1 && cells.every((cell) => /^:?-{3,}:?$/.test(cell));
}

export function MarkdownBlock({ text }: { text?: string | null }) {
  const lines = String(text ?? "").split(/\r?\n/);
  const blocks: ReactNode[] = [];
  let i = 0;

  while (i < lines.length) {
    const line = lines[i].trim();
    if (!line) {
      i += 1;
      continue;
    }

    const heading = /^(#{1,4})\s+(.+)$/.exec(line);
    if (heading) {
      const level = heading[1].length;
      const content = renderInline(heading[2]);
      blocks.push(level <= 2 ? <h3 key={i}>{content}</h3> : <h4 key={i}>{content}</h4>);
      i += 1;
      continue;
    }

    if (line === "---") {
      blocks.push(<hr key={i} />);
      i += 1;
      continue;
    }

    if (/^[-*]\s+/.test(line)) {
      const items: ReactNode[] = [];
      while (i < lines.length && /^[-*]\s+/.test(lines[i].trim())) {
        items.push(<li key={i}>{renderInline(lines[i].trim().replace(/^[-*]\s+/, ""))}</li>);
        i += 1;
      }
      blocks.push(<ul key={`ul-${i}`}>{items}</ul>);
      continue;
    }

    if (/^\d+\.\s+/.test(line)) {
      const items: ReactNode[] = [];
      while (i < lines.length && /^\d+\.\s+/.test(lines[i].trim())) {
        items.push(<li key={i}>{renderInline(lines[i].trim().replace(/^\d+\.\s+/, ""))}</li>);
        i += 1;
      }
      blocks.push(<ol key={`ol-${i}`}>{items}</ol>);
      continue;
    }

    if (line.startsWith("|") && lines[i + 1] && isTableSeparator(lines[i + 1].trim())) {
      const headers = splitTableRow(line);
      i += 2;
      const rows: string[][] = [];
      while (i < lines.length && lines[i].trim().startsWith("|")) {
        rows.push(splitTableRow(lines[i]));
        i += 1;
      }
      blocks.push(
        <div className="markdown-table-wrap" key={`table-${i}`}>
          <table>
            <thead>
              <tr>{headers.map((header, idx) => <th key={idx}>{renderInline(header)}</th>)}</tr>
            </thead>
            <tbody>
              {rows.map((row, rowIndex) => (
                <tr key={rowIndex}>
                  {headers.map((_, cellIndex) => <td key={cellIndex}>{renderInline(row[cellIndex] ?? "")}</td>)}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      );
      continue;
    }

    const paragraph: string[] = [line];
    i += 1;
    while (
      i < lines.length
      && lines[i].trim()
      && !/^(#{1,4})\s+/.test(lines[i].trim())
      && !/^[-*]\s+/.test(lines[i].trim())
      && !/^\d+\.\s+/.test(lines[i].trim())
      && !(lines[i].trim().startsWith("|") && lines[i + 1] && isTableSeparator(lines[i + 1].trim()))
    ) {
      paragraph.push(lines[i].trim());
      i += 1;
    }
    blocks.push(<p key={`p-${i}`}>{renderInline(paragraph.join(" "))}</p>);
  }

  return <div className="markdown-block">{blocks}</div>;
}
