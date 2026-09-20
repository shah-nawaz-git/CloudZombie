"use client";
import { useState } from "react";
type CodeBlockProps = { content: string; filename?: string };
export function CodeBlock({ content, filename }: CodeBlockProps) {
  const [copied, setCopied] = useState(false);
  function download() {
    const anchor = document.createElement("a");
    anchor.href = URL.createObjectURL(new Blob([content], { type: "text/x-shellscript" }));
    anchor.download = filename || "cloudzombie.sh";
    anchor.click();
  }
  return (
    <div>
      <div className="code-actions">
        <button
          onClick={() => {
            void navigator.clipboard.writeText(content);
            setCopied(true);
          }}
          aria-label="Copy script"
        >
          {copied ? "Copied" : "Copy"}
        </button>
        <button onClick={download} aria-label="Download script">
          Download
        </button>
      </div>
      <pre className="code">{content}</pre>
    </div>
  );
}
