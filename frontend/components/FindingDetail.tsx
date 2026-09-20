"use client";
import { ErrorState } from "./ErrorState";
import { LoadingState } from "./LoadingState";
import { CleanupPlan } from "./finding/CleanupPlan";
import { CostCalculation } from "./finding/CostCalculation";
import { Evidence } from "./finding/Evidence";
import { GeneratedScript } from "./finding/GeneratedScript";
import { Header } from "./finding/Header";
import { KnownDependencies } from "./finding/KnownDependencies";
import { Limitations } from "./finding/Limitations";
import { ObservationHistory } from "./finding/ObservationHistory";
import { ObservationTimeline } from "./finding/ObservationTimeline";
import { Ownership } from "./finding/Ownership";
import { WhyFlagged } from "./finding/WhyFlagged";
import { useFinding, usePlan, useScript } from "@/lib/queries";
export function FindingDetail({ id }: { id: string }) {
  const finding = useFinding(id);
  const plan = usePlan(id);
  const script = useScript(id);
  if (finding.isLoading || plan.isLoading || script.isLoading) return <LoadingState />;
  if (finding.error) return <ErrorState error={finding.error} />;
  const detail = finding.data!;
  const cleanupPlan = plan.data!;
  const generatedScript = script.data!;
  return (
    <>
      <Header finding={detail} />
      <WhyFlagged plan={cleanupPlan} />
      <ObservationHistory finding={detail} />
      <Evidence finding={detail} />
      <KnownDependencies finding={detail} />
      <Ownership finding={detail} />
      <CostCalculation finding={detail} />
      <Limitations plan={cleanupPlan} />
      <CleanupPlan plan={cleanupPlan} script={generatedScript} />
      <GeneratedScript script={generatedScript} />
      <ObservationTimeline finding={detail} />
    </>
  );
}
