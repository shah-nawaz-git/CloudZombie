import { conditionWords, formatTimestamp, isoDate, relativeDays } from "@/lib/format";
import type { FindingDetail } from "@/lib/types";
export function ObservationHistory({ finding }: { finding: FindingDetail }) {
  const condition = conditionWords[finding.detector_type];
  const progress =
    finding.threshold_days === 0
      ? 100
      : Math.min(100, (finding.observation_age_days / finding.threshold_days) * 100);
  return (
    <section className="panel">
      <h2>Observation history</h2>
      <div className="facts">
        <div className="fact">
          <label>Resource age</label>
          <strong>
            {finding.resource_age_days == null ? "unknown" : `${finding.resource_age_days} days`}
          </strong>
          {finding.resource_age_days == null && (
            <small>AWS does not expose an allocation time</small>
          )}
        </div>
        <div className="fact">
          <label>First observed {condition}</label>
          <strong>{relativeDays(finding.first_observed_days_ago)}</strong>
          <div>{isoDate(finding.first_observed_at)}</div>
        </div>
        <div className="fact">
          <label>Observed {condition}</label>
          <strong>{finding.observation_count} scans</strong>
          {finding.consecutive_observations !== finding.observation_count && (
            <div>{finding.consecutive_observations} consecutive</div>
          )}
        </div>
      </div>
      <p>
        Last observed: <span className="mono">{formatTimestamp(finding.last_observed_at)}</span> (
        {relativeDays(finding.last_observed_days_ago)})
      </p>
      {finding.streak_started_at !== finding.first_observed_at && (
        <p>Current streak began {isoDate(finding.streak_started_at)}.</p>
      )}
      <p>
        Cleanup-candidate threshold: {finding.threshold_days} days of observed persistence ·{" "}
        {finding.days_until_persistent == null
          ? "reached"
          : `${finding.days_until_persistent} days remaining`}
      </p>
      <div className="progress">
        <span style={{ width: `${progress}%` }} />
      </div>
      <p>
        HIGH means CloudZombie is certain the condition is currently true; it is not a deletion
        recommendation.
      </p>
    </section>
  );
}
