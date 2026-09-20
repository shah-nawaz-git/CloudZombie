"use client";
import { useState } from "react";
import { useQueryClient } from "@tanstack/react-query";
import { ErrorState } from "@/components/ErrorState";
import { LoadingState } from "@/components/LoadingState";
import { PageHeader } from "@/components/PageHeader";
import { api } from "@/lib/api";
import { keys, useSettings } from "@/lib/queries";
import type { SettingsData } from "@/lib/types";
const thresholdLabels: Record<string, string> = {
  unattached_ebs_volume: "Unattached EBS volume — days of observed persistence",
  unassociated_elastic_ip: "Unassociated Elastic IP — days",
  stopped_ec2_instance: "Stopped EC2 instance — days",
  snapshot_missing_source_volume: "Snapshot with deleted source volume — days",
};
type FieldProps = { label: string; help: string; children: React.ReactNode };
function Field({ label, help, children }: FieldProps) {
  return (
    <label className="form-field">
      <span>{label}</span>
      {children}
      <small>{help}</small>
    </label>
  );
}
function SettingsForm({ initial }: { initial: SettingsData }) {
  const client = useQueryClient();
  const [form, setForm] = useState(initial);
  const [message, setMessage] = useState("");
  function field(key: keyof SettingsData, value: unknown) {
    setForm({ ...form, [key]: value });
  }
  async function save() {
    try {
      const regions = (form.regions || []).join(",");
      const body = {
        ...form,
        regions: regions.trim() ? regions.split(/[\s,]+/).filter(Boolean) : null,
        mode: undefined,
        detector_thresholds_help: undefined,
        demo_anchor_at: undefined,
      };
      await api("/api/settings", { method: "PATCH", body: JSON.stringify(body) });
      setMessage("Settings saved.");
      await client.invalidateQueries({ queryKey: keys.settings });
    } catch (error) {
      setMessage(`Save failed: ${(error as Error).message}`);
    }
  }
  return (
    <>
      <section className="panel">
        <div className="settings-grid">
          <Field
            label="Regions (empty = all accessible)"
            help="Comma or newline separated AWS regions."
          >
            <textarea
              value={(form.regions || []).join("\n")}
              onChange={(event) =>
                field("regions", event.target.value.split(/[\n,]+/).filter(Boolean))
              }
            />
          </Field>
          {Object.entries(form.thresholds_days).map(([key, value]) => (
            <Field
              key={key}
              label={thresholdLabels[key] || key}
              help={form.detector_thresholds_help[key] || "Observed persistence threshold."}
            >
              <input
                type="number"
                min="0"
                value={value}
                onChange={(event) =>
                  field("thresholds_days", {
                    ...form.thresholds_days,
                    [key]: Number(event.target.value),
                  })
                }
              />
            </Field>
          ))}
          <Field
            label="Minimum consecutive observations"
            help="Required observations in the current uninterrupted streak."
          >
            <input
              type="number"
              min="1"
              value={form.min_consecutive_observations}
              onChange={(event) =>
                field("min_consecutive_observations", Number(event.target.value))
              }
            />
          </Field>
          <Field
            label="Ignore tag key"
            help="Resources with this tag/value remain visible but ignored."
          >
            <input
              value={form.ignore_tag_key}
              onChange={(event) => field("ignore_tag_key", event.target.value)}
            />
          </Field>
          <Field label="Ignore tag value" help="Compared case-insensitively.">
            <input
              value={form.ignore_tag_value}
              onChange={(event) => field("ignore_tag_value", event.target.value)}
            />
          </Field>
          <Field
            label="Ignore reason tag key"
            help="Optional context displayed with ignored findings."
          >
            <input
              value={form.ignore_reason_tag_key}
              onChange={(event) => field("ignore_reason_tag_key", event.target.value)}
            />
          </Field>
          <Field label="Pricing mode" help="Auto tries AWS Pricing API before the fallback table.">
            <select
              value={form.pricing_mode}
              onChange={(event) => field("pricing_mode", event.target.value)}
            >
              <option value="auto">Auto</option>
              <option value="fallback_only">Fallback only</option>
              <option value="disabled">Disabled</option>
            </select>
          </Field>
          <Field
            label="Pricing cache TTL (seconds)"
            help="How long retrieved unit prices remain valid."
          >
            <input
              type="number"
              min="0"
              value={form.pricing_cache_ttl_seconds}
              onChange={(event) => field("pricing_cache_ttl_seconds", Number(event.target.value))}
            />
          </Field>
          <Field label="Region concurrency" help="Maximum AWS regions scanned at once (1–8).">
            <input
              type="number"
              min="1"
              max="8"
              value={form.max_region_concurrency}
              onChange={(event) => field("max_region_concurrency", Number(event.target.value))}
            />
          </Field>
        </div>
        <button className="primary" onClick={save}>
          Save settings
        </button>
        {message && <div className="toast">{message}</div>}
      </section>
      <section className="panel">
        <h2>Runtime mode</h2>
        <p>{form.mode.toUpperCase()}</p>
        <p>
          AWS credentials are never configured or stored here; the backend uses the standard boto3
          credential chain.
        </p>
      </section>
    </>
  );
}
export default function SettingsPage() {
  const query = useSettings();
  if (query.isLoading) return <LoadingState />;
  if (query.error) return <ErrorState error={query.error} />;
  return (
    <>
      <PageHeader title="Settings" />
      <SettingsForm initial={query.data!} />
    </>
  );
}
