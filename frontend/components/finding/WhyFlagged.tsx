import type { Plan } from "@/lib/types";
export function WhyFlagged({ plan }: { plan: Plan }) {
  return (
    <section className="panel">
      <h2>Why it was flagged</h2>
      <p>{plan.plain_language_summary}</p>
    </section>
  );
}
