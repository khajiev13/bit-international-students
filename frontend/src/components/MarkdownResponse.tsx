import ReactMarkdown from "react-markdown";
import rehypeSanitize from "rehype-sanitize";
import remarkGfm from "remark-gfm";

type MarkdownResponseProps = {
  markdown: string;
};

export function MarkdownResponse({ markdown }: MarkdownResponseProps) {
  return (
    <section className="markdown-area" aria-label="Agent markdown response">
      <div className="markdown-body" data-testid="markdown-body">
        <ReactMarkdown remarkPlugins={[remarkGfm]} rehypePlugins={[rehypeSanitize]}>
          {markdown}
        </ReactMarkdown>
      </div>
    </section>
  );
}
