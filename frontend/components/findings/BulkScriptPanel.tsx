import type { Script } from "@/lib/types";
import { CodeBlock } from "../CodeBlock";
export interface BulkResult {
  script: Script | null;
  included: string[];
  skipped: Array<{ finding_id: string; reason: string }>;
}
type BulkScriptPanelProps = {
  selectedCount: number;
  result: BulkResult | null;
  generate: () => void;
};
export function BulkScriptPanel({ selectedCount, result, generate }: BulkScriptPanelProps) {
  if (selectedCount === 0) return null;
  return (
    <section className="panel">
      <button className="primary" onClick={generate}>
        Generate bulk script ({selectedCount})
      </button>
      {result && (
        <div>
          <p>
            {result.included.length} included · {result.skipped.length} skipped
          </p>
          {result.skipped.map((item) => (
            <div key={item.finding_id}>
              {item.finding_id}: {item.reason}
            </div>
          ))}
          {result.script && (
            <CodeBlock content={result.script.content} filename={result.script.filename} />
          )}
        </div>
      )}
    </section>
  );
}
