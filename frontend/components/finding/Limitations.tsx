import type { Plan } from "@/lib/types";
export function Limitations({ plan }: { plan: Plan }) {
  return (
    <section className="panel">
      <h2>Uncertainty and limitations</h2>
      <ul>
        {plan.limitations.map((item) => (
          <li key={item}>{item}</li>
        ))}
      </ul>
    </section>
  );
}
