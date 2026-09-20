const IAM_ACTIONS = [
  "ec2:DescribeRegions",
  "ec2:DescribeVolumes",
  "ec2:DescribeAddresses",
  "ec2:DescribeInstances",
  "ec2:DescribeSnapshots",
  "ec2:DescribeImages",
  "ec2:DescribeSnapshotAttribute",
  "ec2:DescribeLockedSnapshots",
  "sts:GetCallerIdentity",
  "pricing:GetProducts",
  "cloudformation:ListStacks",
  "cloudformation:ListStackResources",
] as const;
export { IAM_ACTIONS };
export default function AboutPage() {
  return (
    <>
      <div className="page-header">
        <h1>About CloudZombie</h1>
        <p className="muted">A self-hosted AWS cleanup planner.</p>
      </div>
      <section className="panel">
        <h2>What it does</h2>
        <p>
          CloudZombie performs read-only discovery, records observation history, checks known
          dependencies and ownership, estimates public list-price exposure, and generates scripts
          for human review.
        </p>
        <h2>What it does not do</h2>
        <p>
          The application never calls AWS remediation APIs and never claims complete dependency or
          ownership knowledge.
        </p>
      </section>
      <section className="panel">
        <h2>Workflow</h2>
        <ol>
          <li>Discover with restricted read-only wrappers.</li>
          <li>Observe conditions across repeated scans.</li>
          <li>Review known dependencies and infrastructure ownership.</li>
          <li>Review a cleanup plan and guarded script.</li>
          <li>A human runs a script separately if appropriate.</li>
        </ol>
      </section>
      <section className="panel">
        <h2>Safety architecture</h2>
        <p>
          Restricted wrappers and an operation guard constrain the provider. The script boundary
          accepts only strict validated identifiers.
        </p>
      </section>
      <section className="panel">
        <h2>IAM operations</h2>
        <ul aria-label="IAM operations">
          {IAM_ACTIONS.map((x) => (
            <li className="mono" key={x}>
              {x}
            </li>
          ))}
        </ul>
      </section>
      <section className="panel">
        <h2>Known limitations</h2>
        <p>
          Condition start times are not available from AWS. Terraform ownership remains unknown
          without explicit metadata. Snapshot reclaimable storage cannot be calculated exactly.
        </p>
        <p>
          See the <a href="https://github.com/">docs folder</a> for architecture and policy details.
        </p>
      </section>
    </>
  );
}
