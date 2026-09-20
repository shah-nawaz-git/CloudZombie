from threading import Event

from tests.api.conftest import find_by_resource


def test_repeated_status_filter(api_client) -> None:
    response = api_client.get(
        "/api/findings", params=[("status", "open"), ("status", "dismissed")]
    )
    assert response.status_code == 200
    assert {item["status"] for item in response.json()["items"]} <= {"open", "dismissed"}


def test_health_identity_and_openapi(api_client) -> None:
    health = api_client.get("/api/health")
    assert health.status_code == 200
    assert health.json()["mode"] == "demo"
    identity = api_client.get("/api/identity")
    assert identity.json()["account_id"] == "123456789012"
    assert identity.json()["identity_type"] == "assumed-role"
    openapi = api_client.get("/api/openapi.json")
    assert openapi.status_code == 200
    assert openapi.json()["info"]["title"] == "CloudZombie"


def test_wait_scan_returns_finished_scan(api_client) -> None:
    response = api_client.post("/api/scans", json={"wait": True})
    assert response.status_code == 202
    scan = response.json()
    assert scan["status"] == "partial"
    assert scan["new_findings"] == 0
    assert "ap-southeast-2" in scan["partial_regions"]


def test_concurrent_scan_conflict(api_client, monkeypatch) -> None:
    runner = api_client.app.state.context.scan_runner
    started = Event()
    release = Event()
    original = runner._execute

    def blocked(scan_id, regions):
        started.set()
        release.wait(timeout=5)
        original(scan_id, regions)

    monkeypatch.setattr(runner, "_execute", blocked)
    first = api_client.post("/api/scans", json={"wait": False})
    assert first.status_code == 202
    assert started.wait(timeout=2)
    second = api_client.post("/api/scans", json={"wait": False})
    assert second.status_code == 409
    assert second.json()["detail"]["code"] == "scan_running"
    release.set()


def test_findings_filters_sort_and_pagination(api_client) -> None:
    default = api_client.get("/api/findings")
    assert default.status_code == 200
    assert default.json()["total"] == 12
    assert (
        default.json()["items"][0]["estimated_monthly_cost"]
        >= default.json()["items"][1]["estimated_monthly_cost"]
    )
    cases = [
        ({"ownership": "CONFIRMED"}, "vol-0a1b2c3d4e5f60002"),
        ({"status": "ignored"}, "vol-0a1b2c3d4e5f60004"),
        ({"region": "us-east-1"}, "vol-0a1b2c3d4e5f60003"),
        ({"resource_type": "elastic_ip"}, "eipalloc-0a1b2c3d4e5f60001"),
        ({"min_observation_count": 4}, "vol-0a1b2c3d4e5f60001"),
        ({"q": "f60002"}, "vol-0a1b2c3d4e5f60002"),
        ({"persistence_state": "persistent"}, "vol-0a1b2c3d4e5f60001"),
        ({"remediation_risk": "HIGH"}, "vol-0a1b2c3d4e5f60002"),
        ({"cost_confidence": "LOW"}, "snap-0a1b2c3d4e5f60001"),
        ({"detection_confidence": "HIGH"}, "vol-0a1b2c3d4e5f60001"),
    ]
    for params, resource_id in cases:
        response = api_client.get("/api/findings", params=params)
        assert response.status_code == 200, response.text
        assert resource_id in {item["resource_id"] for item in response.json()["items"]}
    page = api_client.get("/api/findings", params={"page": 2, "page_size": 3}).json()
    assert page["total"] == 12
    assert len(page["items"]) == 3


def test_detail_patch_plan_and_scripts(api_client) -> None:
    hero = find_by_resource(api_client, "vol-0a1b2c3d4e5f60001")
    detail = api_client.get(f"/api/findings/{hero['id']}")
    assert detail.json()["first_observed_days_ago"] == 21
    assert detail.json()["last_observed_days_ago"] == 2
    assert len(detail.json()["observations"]) == 4
    assert "related_findings" in detail.json()
    plan = api_client.get(f"/api/findings/{hero['id']}/plan")
    assert plan.status_code == 200
    assert plan.json()["script_available"] is True
    script = api_client.get(f"/api/findings/{hero['id']}/script")
    assert script.json()["kind"] == "guarded_remediation"
    raw = api_client.get(f"/api/findings/{hero['id']}/script", params={"format": "raw"})
    assert raw.headers["content-type"].startswith("text/x-shellscript")
    assert "attachment; filename=" in raw.headers["content-disposition"]

    dismissed = api_client.patch(
        f"/api/findings/{hero['id']}", json={"status": "dismissed", "reason": "reviewed"}
    )
    assert dismissed.status_code == 200
    assert dismissed.json()["status"] == "dismissed"
    reopened = api_client.patch(f"/api/findings/{hero['id']}", json={"status": "open"})
    assert reopened.json()["status"] == "open"
    invalid = api_client.patch(f"/api/findings/{hero['id']}", json={"status": "open"})
    assert invalid.status_code == 409
    assert invalid.json()["detail"]["code"] == "invalid_transition"


def test_bulk_history_coverage_and_overview(api_client) -> None:
    hero = find_by_resource(api_client, "vol-0a1b2c3d4e5f60001")
    snapshot = find_by_resource(api_client, "snap-0a1b2c3d4e5f60001")
    bulk = api_client.post("/api/scripts/bulk", json={"finding_ids": [hero["id"], snapshot["id"]]})
    assert bulk.status_code == 200
    assert bulk.json()["included"] == [hero["id"]]
    assert len(bulk.json()["skipped"]) == 1
    history = api_client.get("/api/history").json()
    assert len(history["points"]) == 4
    assert all(point["observed_by_resource_type"] for point in history["points"])
    coverage = api_client.get("/api/coverage").json()
    assert coverage["regions"]["ap-southeast-2"]["status"] == "partial"
    cell = coverage["regions"]["ap-southeast-2"]["detectors"]["snapshot_missing_source_volume"]
    assert cell["missing_operation"] == "ec2:DescribeSnapshots"
    overview = api_client.get("/api/overview")
    assert overview.status_code == 200
    data = overview.json()
    assert data["open_findings"] == 10
    assert data["latest_scan"]["seeded"] is True
    assert data["coverage_summary"]["partial"] == 1


def test_settings_validation_and_not_found_shape(api_client) -> None:
    settings = api_client.get("/api/settings")
    assert settings.status_code == 200
    assert settings.json()["mode"] == "demo"
    patched = api_client.patch(
        "/api/settings",
        json={"regions": ["us-east-1"], "max_region_concurrency": 4},
    )
    assert patched.status_code == 200
    assert patched.json()["regions"] == ["us-east-1"]
    invalid_region = api_client.patch("/api/settings", json={"regions": ["NOT-A-REGION"]})
    assert invalid_region.status_code == 422
    invalid_tag = api_client.patch("/api/settings", json={"ignore_tag_key": "cloud zombie"})
    assert invalid_tag.status_code == 422
    anchor = settings.json()["demo_anchor_at"]
    ignored = api_client.patch("/api/settings", json={"demo_anchor_at": "2000-01-01T00:00:00Z"})
    assert ignored.json()["demo_anchor_at"] == anchor
    missing = api_client.get("/api/findings/11111111-1111-4111-8111-111111111111")
    assert missing.status_code == 404
    assert missing.json()["detail"]["code"] == "not_found"
