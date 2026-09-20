"use client";
import { useState } from "react";
import { useQueryClient } from "@tanstack/react-query";
import { api, ApiError } from "@/lib/api";
import type { Scan } from "@/lib/types";
export function ScanControls() {
  const [running, setRunning] = useState(false);
  const [message, setMessage] = useState("");
  const query = useQueryClient();
  async function run() {
    setRunning(true);
    setMessage("");
    try {
      let scan = await api<Scan>("/api/scans", {
        method: "POST",
        body: JSON.stringify({ wait: false }),
      });
      while (scan.status === "running") {
        await new Promise((r) => setTimeout(r, 1000));
        scan = await api<Scan>(`/api/scans/${scan.id}`);
      }
      setMessage(
        `new ${scan.new_findings} · persistent ${scan.persistent_findings} · resolved ${scan.resolved_findings}`,
      );
      await query.invalidateQueries();
    } catch (error) {
      const e = error as ApiError;
      setMessage(e.status === 409 ? "A scan is already running" : e.message);
    } finally {
      setRunning(false);
    }
  }
  return (
    <div className="actions">
      <button className="primary" onClick={run} disabled={running}>
        {running ? "Scan running…" : "Run scan"}
      </button>
      {message && <span aria-live="polite">{message}</span>}
    </div>
  );
}
