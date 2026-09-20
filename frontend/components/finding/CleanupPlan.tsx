import type { Plan, Script } from "@/lib/types";
export function CleanupPlan({ plan, script }: { plan: Plan; script: Script }) {
  return (
    <section className="panel">
      <h2>Cleanup plan</h2>
      <h3>Preconditions</h3>
      <ul>
        {plan.preconditions.map((item) => (
          <li key={item}>{item}</li>
        ))}
      </ul>
      {plan.warnings.length > 0 && (
        <>
          <h3>Warnings</h3>
          <ul>
            {plan.warnings.map((item) => (
              <li key={item}>{item}</li>
            ))}
          </ul>
        </>
      )}
      <div className="action-callout">{plan.recommended_action}</div>
      <p>
        Script:{" "}
        {plan.script_available ? "available" : script.unavailable_text || "investigation only"}
      </p>
    </section>
  );
}
