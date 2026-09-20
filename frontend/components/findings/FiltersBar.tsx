type FiltersBarProps = {
  search: URLSearchParams;
  regions: string[];
  setParam: (key: string, value: string) => void;
  setStatuses: (values: string[]) => void;
};
export function FiltersBar({ search, regions, setParam, setStatuses }: FiltersBarProps) {
  return (
    <div className="filter-stack">
      <div className="filters">
        <input
          aria-label="Search findings"
          placeholder="Search ID or title"
          defaultValue={search.get("q") || ""}
          onBlur={(event) => setParam("q", event.target.value)}
        />
        <select
          aria-label="Resource type"
          value={search.get("resource_type") || ""}
          onChange={(event) => setParam("resource_type", event.target.value)}
        >
          <option value="">All types</option>
          <option value="ebs_volume">EBS volume</option>
          <option value="elastic_ip">Elastic IP</option>
          <option value="ec2_instance">EC2 instance</option>
          <option value="ebs_snapshot">EBS snapshot</option>
        </select>
        <select
          aria-label="Region"
          value={search.get("region") || ""}
          onChange={(event) => setParam("region", event.target.value)}
        >
          <option value="">All regions</option>
          {regions.map((region) => (
            <option key={region}>{region}</option>
          ))}
        </select>
        <select
          multiple
          aria-label="Status"
          value={search.getAll("status").length ? search.getAll("status") : ["open"]}
          onChange={(event) =>
            setStatuses(Array.from(event.target.selectedOptions, (option) => option.value))
          }
        >
          <option value="open">Open</option>
          <option value="ignored">Ignored</option>
          <option value="dismissed">Dismissed</option>
          <option value="resolved">Resolved</option>
        </select>
        <select
          aria-label="Risk"
          value={search.get("remediation_risk") || ""}
          onChange={(event) => setParam("remediation_risk", event.target.value)}
        >
          <option value="">All risks</option>
          <option>LOW</option>
          <option>REVIEW</option>
          <option>HIGH</option>
        </select>
        <select
          aria-label="Ownership"
          value={search.get("ownership") || ""}
          onChange={(event) => setParam("ownership", event.target.value)}
        >
          <option value="">All ownership</option>
          <option>CONFIRMED</option>
          <option>LIKELY</option>
          <option>UNKNOWN</option>
        </select>
      </div>
      <div className="filters">
        <select
          aria-label="Detection confidence"
          value={search.get("detection_confidence") || ""}
          onChange={(event) => setParam("detection_confidence", event.target.value)}
        >
          <option value="">All detection confidence</option>
          <option>HIGH</option>
          <option>MEDIUM</option>
          <option>LOW</option>
        </select>
        <select
          aria-label="Cost confidence"
          value={search.get("cost_confidence") || ""}
          onChange={(event) => setParam("cost_confidence", event.target.value)}
        >
          <option value="">All cost confidence</option>
          <option>HIGH</option>
          <option>MEDIUM</option>
          <option>LOW</option>
          <option>UNAVAILABLE</option>
        </select>
        <select
          aria-label="Persistence state"
          value={search.get("persistence_state") || ""}
          onChange={(event) => setParam("persistence_state", event.target.value)}
        >
          <option value="">All persistence</option>
          <option value="persistent">Persistent</option>
          <option value="newly_observed">Newly observed</option>
        </select>
        <input
          aria-label="Minimum observations"
          type="number"
          min="1"
          placeholder="Min observations"
          value={search.get("min_observation_count") || ""}
          onChange={(event) => setParam("min_observation_count", event.target.value)}
        />
        <label>
          First observed after
          <input
            aria-label="First observed after"
            type="date"
            value={search.get("first_observed_after")?.slice(0, 10) || ""}
            onChange={(event) => setParam("first_observed_after", event.target.value)}
          />
        </label>
        <label>
          First observed before
          <input
            aria-label="First observed before"
            type="date"
            value={search.get("first_observed_before")?.slice(0, 10) || ""}
            onChange={(event) => setParam("first_observed_before", event.target.value)}
          />
        </label>
      </div>
    </div>
  );
}
