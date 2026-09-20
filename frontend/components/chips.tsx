import type { Identity } from "@/lib/types";
import { Mono } from "./Mono";

type ChipProps = { value: string; label?: string };
export function Chip({ value, label }: ChipProps) {
  const className = value.toLowerCase().replaceAll("_", "-");
  return (
    <span className={`chip ${className}`}>
      {label ? `${label} ${value}` : value.replaceAll("_", " ")}
    </span>
  );
}
export const StatusChip = Chip;
export const RiskChip = Chip;
export const ConfidenceChip = Chip;
export const OwnershipChip = Chip;

export function ModeBadge({ identity }: { identity: Identity }) {
  return (
    <span className={`chip mode ${identity.mode}`}>
      {identity.mode === "demo" ? (
        "DEMO MODE"
      ) : (
        <>
          LIVE AWS&nbsp; <Mono>{identity.account_id}</Mono>&nbsp;{" "}
          <Mono>{identity.principal_arn}</Mono>
        </>
      )}
    </span>
  );
}
