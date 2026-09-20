import type { Script } from "@/lib/types";
import { CodeBlock } from "../CodeBlock";
export function GeneratedScript({ script }: { script: Script }) {
  return (
    <section className="panel">
      <h2>Generated script</h2>
      <p>
        {script.kind === "guarded_remediation"
          ? "Guarded remediation script"
          : "Read-only investigation script"}
      </p>
      <h3>Checks performed by this script</h3>
      <ul>
        {script.checks.map((check) => (
          <li key={check}>{check}</li>
        ))}
      </ul>
      {script.warnings.length > 0 && (
        <>
          <h3>Warnings</h3>
          <ul>
            {script.warnings.map((warning) => (
              <li key={warning}>{warning}</li>
            ))}
          </ul>
        </>
      )}
      <CodeBlock content={script.content} filename={script.filename} />
      <p>CloudZombie never runs this script.</p>
    </section>
  );
}
