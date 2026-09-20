"use client";
import { useState } from "react";
import { useQueryClient } from "@tanstack/react-query";
import { api } from "@/lib/api";
import { keys } from "@/lib/queries";
import type { FindingDetail } from "@/lib/types";
import { ConfidenceChip, OwnershipChip, RiskChip, StatusChip } from "../chips";
import { Mono } from "../Mono";
export function Header({ finding }: { finding: FindingDetail }) {
  const [reason, setReason] = useState("");
  const queryClient = useQueryClient();
  async function patch() {
    await api(`/api/findings/${finding.id}`, {
      method: "PATCH",
      body: JSON.stringify({
        status: finding.status === "dismissed" ? "open" : "dismissed",
        reason,
      }),
    });
    await queryClient.invalidateQueries({ queryKey: keys.finding(finding.id) });
  }
  return (
    <section className="panel">
      <div className="detail-head">
        <div>
          <h2>{finding.title}</h2>
          <Mono>{finding.resource_id}</Mono> · <Mono>{finding.region}</Mono> · account{" "}
          <Mono>{finding.account_id}</Mono>
          <div className="inline-list">
            <StatusChip label="Status" value={finding.status} />
            <RiskChip label="Risk" value={finding.remediation_risk} />
            <ConfidenceChip label="Detection" value={finding.detection_confidence} />
            <ConfidenceChip label="Cost confidence" value={finding.cost_confidence} />
            <OwnershipChip label="Ownership" value={finding.ownership.status} />
          </div>
        </div>
        <div className="actions">
          <input
            aria-label="Dismiss reason"
            value={reason}
            onChange={(event) => setReason(event.target.value)}
            placeholder="Reason"
          />
          <button onClick={patch}>{finding.status === "dismissed" ? "Reopen" : "Dismiss"}</button>
        </div>
      </div>
    </section>
  );
}
