export function MarkdownBlock({ text }: { text: string }) {
  return <pre className="markdown-block">{text}</pre>;
}
