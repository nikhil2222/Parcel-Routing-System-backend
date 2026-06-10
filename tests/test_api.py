import json
import io
import pytest
import pytest_asyncio
from httpx import AsyncClient, ASGITransport

from app.main import app
from app.config_loader import load_rules_with_metadata
from app.router import RoutingEngine
from app.limiter import limiter
from app.feature_flags import FeatureFlags
from app.metrics import MetricsStore

API_KEY = "dev-secret-key-change-in-production"
HEADERS = {"X-API-Key": API_KEY}


@pytest_asyncio.fixture
async def client():
    loaded = load_rules_with_metadata()
    app.state.engine = RoutingEngine(loaded.rules, version=loaded.version)
    app.state.limiter = limiter
    app.state.flags = FeatureFlags()
    app.state.metrics = MetricsStore()
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://testserver") as c:
        yield c


def make_json_file(data: list, filename: str = "parcels.json") -> dict:
    return {"file": (filename, io.BytesIO(json.dumps(data).encode()), "application/json")}


def make_xml_file(xml_text: str, filename: str = "parcels.xml") -> dict:
    return {"file": (filename, io.BytesIO(xml_text.encode()), "application/xml")}


SAMPLE_XML = """<?xml version="1.0"?>
<Container>
  <Id>68465468</Id>
  <ShippingDate>2016-07-22T00:00:00+02:00</ShippingDate>
  <parcels>
    <Parcel>
      <Receipient>
        <Name>Vinny Gankema</Name>
        <Address>
          <Street>Marijkestraat</Street>
          <HouseNumber>28</HouseNumber>
          <PostalCode>4744AT</PostalCode>
          <City>Bosschenhoofd</City>
        </Address>
      </Receipient>
      <Weight>0.02</Weight>
      <Value>0.0</Value>
    </Parcel>
    <Parcel>
      <Receipient>
        <Name>Ricardus Proper</Name>
        <Address>
          <Street>Nieuwstraat</Street>
          <HouseNumber>115</HouseNumber>
          <PostalCode>4724BE</PostalCode>
          <City>Wouw</City>
        </Address>
      </Receipient>
      <Weight>100.0</Weight>
      <Value>2000.0</Value>
    </Parcel>
  </parcels>
</Container>
"""


class TestHealthCheck:
    @pytest.mark.asyncio
    async def test_health_returns_200(self, client):
        assert (await client.get("/health")).status_code == 200

    @pytest.mark.asyncio
    async def test_health_has_rules_count(self, client):
        data = (await client.get("/health")).json()
        assert data["rules_loaded"] > 0

    @pytest.mark.asyncio
    async def test_health_status_healthy(self, client):
        assert (await client.get("/health")).json()["status"] == "healthy"

    @pytest.mark.asyncio
    async def test_health_exposes_feature_flags(self, client):
        data = (await client.get("/health")).json()
        assert "feature_flags" in data
        assert data["feature_flags"]["xml_batch_upload_enabled"] is True

    @pytest.mark.asyncio
    async def test_health_exposes_security_config(self, client):
        data = (await client.get("/health")).json()
        assert "trusted_hosts" in data
        assert "allowed_origins" in data


class TestAuthentication:
    @pytest.mark.asyncio
    async def test_missing_api_key_returns_401(self, client):
        r = await client.post("/api/v1/route", json={"weight": 1.0, "value": 50, "destination": "DE"})
        assert r.status_code == 401

    @pytest.mark.asyncio
    async def test_wrong_api_key_returns_403(self, client):
        r = await client.post(
            "/api/v1/route",
            headers={"X-API-Key": "wrong-key"},
            json={"weight": 1.0, "value": 50, "destination": "DE"},
        )
        assert r.status_code == 403

    @pytest.mark.asyncio
    async def test_valid_api_key_returns_200(self, client):
        r = await client.post(
            "/api/v1/route",
            headers=HEADERS,
            json={"weight": 1.0, "value": 50, "destination": "DE"},
        )
        assert r.status_code == 200


class TestRouteEndpoint:
    @pytest.mark.asyncio
    async def test_route_mail_parcel(self, client):
        r = await client.post(
            "/api/v1/route",
            headers=HEADERS,
            json={"weight": 0.5, "value": 50, "destination": "DE"},
        )
        assert r.json()["department"] == "mail"

    @pytest.mark.asyncio
    async def test_route_regular_parcel(self, client):
        r = await client.post(
            "/api/v1/route",
            headers=HEADERS,
            json={"weight": 5.0, "value": 200, "destination": "FR"},
        )
        assert r.json()["department"] == "regular"

    @pytest.mark.asyncio
    async def test_route_heavy_parcel(self, client):
        r = await client.post(
            "/api/v1/route",
            headers=HEADERS,
            json={"weight": 15.0, "value": 300, "destination": "NL"},
        )
        assert r.json()["department"] == "heavy"

    @pytest.mark.asyncio
    async def test_route_with_insurance_flag(self, client):
        r = await client.post(
            "/api/v1/route",
            headers=HEADERS,
            json={"weight": 0.5, "value": 1500, "destination": "DE"},
        )
        data = r.json()
        assert data["requires_insurance"] is True
        assert data["department"] == "mail"

    @pytest.mark.asyncio
    async def test_route_dispatch_allowed_by_default(self, client):
        r = await client.post(
            "/api/v1/route",
            headers=HEADERS,
            json={"weight": 0.5, "value": 1500, "destination": "DE"},
        )
        data = r.json()
        assert r.status_code == 200
        assert data["requires_insurance"] is True
        assert data["dispatch_allowed"] is True

    @pytest.mark.asyncio
    async def test_route_with_extra_fields(self, client):
        r = await client.post(
            "/api/v1/route",
            headers=HEADERS,
            json={
                "weight": 10.0,
                "value": 500,
                "destination": "New Delhi",
                "extra": {"sender": {"name": "Nikhil", "place": "Bombay"}},
            },
        )
        assert r.status_code == 200
        assert r.json()["department"] == "regular"

    @pytest.mark.asyncio
    async def test_route_response_has_rules_matched(self, client):
        r = await client.post(
            "/api/v1/route",
            headers=HEADERS,
            json={"weight": 0.5, "value": 50, "destination": "DE"},
        )
        assert len(r.json()["rules_matched"]) > 0


class TestRouteValidation:
    @pytest.mark.asyncio
    async def test_negative_weight_rejected(self, client):
        r = await client.post(
            "/api/v1/route",
            headers=HEADERS,
            json={"weight": -1.0, "value": 50, "destination": "DE"},
        )
        assert r.status_code == 422

    @pytest.mark.asyncio
    async def test_zero_weight_rejected(self, client):
        r = await client.post(
            "/api/v1/route",
            headers=HEADERS,
            json={"weight": 0, "value": 50, "destination": "DE"},
        )
        assert r.status_code == 422

    @pytest.mark.asyncio
    async def test_negative_value_rejected(self, client):
        r = await client.post(
            "/api/v1/route",
            headers=HEADERS,
            json={"weight": 1.0, "value": -10, "destination": "DE"},
        )
        assert r.status_code == 422

    @pytest.mark.asyncio
    async def test_missing_fields_rejected(self, client):
        r = await client.post("/api/v1/route", headers=HEADERS, json={"weight": 1.0})
        assert r.status_code == 422


class TestBatchEndpoint:
    @pytest.mark.asyncio
    async def test_batch_routes_multiple_parcels(self, client):
        parcels = [
            {"weight": 0.5, "value": 50, "destination": "DE"},
            {"weight": 5.0, "value": 200, "destination": "FR"},
            {"weight": 15.0, "value": 300, "destination": "NL"},
        ]
        r = await client.post("/api/v1/route/batch", headers=HEADERS, files=make_json_file(parcels))
        data = r.json()
        assert data["total"] == 3
        assert data["routed"] == 3
        assert data["failed"] == 0

    @pytest.mark.asyncio
    async def test_batch_handles_invalid_rows_gracefully(self, client):
        parcels = [
            {"weight": 0.5, "value": 50, "destination": "DE"},
            {"weight": -1.0, "value": 50, "destination": "DE"},
        ]
        r = await client.post("/api/v1/route/batch", headers=HEADERS, files=make_json_file(parcels))
        assert r.json()["routed"] == 1
        assert r.json()["failed"] == 1

    @pytest.mark.asyncio
    async def test_batch_accepts_xml_file(self, client):
        r = await client.post("/api/v1/route/batch", headers=HEADERS, files=make_xml_file(SAMPLE_XML))
        data = r.json()
        assert r.status_code == 200
        assert data["total"] == 2
        assert data["routed"] == 2
        assert data["results"][0]["department"] == "mail"
        assert data["results"][1]["department"] == "heavy"
        assert data["results"][1]["requires_insurance"] is True

    @pytest.mark.asyncio
    async def test_batch_rejects_invalid_xml(self, client):
        r = await client.post(
            "/api/v1/route/batch",
            headers=HEADERS,
            files=make_xml_file("<Container><parcels></Container>", filename="broken.xml"),
        )
        assert r.status_code == 400

    @pytest.mark.asyncio
    async def test_batch_rejects_oversized_file(self, client):
        big = json.dumps([{"weight": 1.0, "value": 50, "destination": "DE"}] * 100000).encode()
        r = await client.post(
            "/api/v1/route/batch",
            headers=HEADERS,
            files={"file": ("big.json", io.BytesIO(big), "application/json")},
        )
        assert r.status_code in (400, 413)


class TestRulesEndpoint:
    @pytest.mark.asyncio
    async def test_rules_returns_list(self, client):
        r = await client.get("/api/v1/rules", headers=HEADERS)
        assert len(r.json()["rules"]) > 0

    @pytest.mark.asyncio
    async def test_rules_require_auth(self, client):
        r = await client.get("/api/v1/rules")
        assert r.status_code == 401

    @pytest.mark.asyncio
    async def test_rules_endpoint_returns_version(self, client):
        r = await client.get("/api/v1/rules", headers=HEADERS)
        assert r.status_code == 200
        assert r.json()["version"] == "v1"


class TestSecurityHeaders:
    @pytest.mark.asyncio
    async def test_x_content_type_options(self, client):
        r = await client.get("/health")
        assert r.headers.get("x-content-type-options") == "nosniff"

    @pytest.mark.asyncio
    async def test_x_frame_options(self, client):
        r = await client.get("/health")
        assert r.headers.get("x-frame-options") == "DENY"

    @pytest.mark.asyncio
    async def test_content_security_policy(self, client):
        r = await client.get("/health")
        assert r.headers.get("content-security-policy") is not None


class TestRuleSimulation:
    @pytest.mark.asyncio
    async def test_simulate_rules_detects_route_changes(self, client):
        payload = {
            "parcels": [{"weight": 0.5, "value": 50, "destination": "DE"}],
            "proposed_rules": {
                "version": "v2",
                "rules": [
                    {
                        "name": "mail_department_new",
                        "condition": {"field": "weight", "operator": "<=", "threshold": 0.25},
                        "action": "route_to:mail",
                        "priority": 50,
                        "enabled": True,
                    },
                    {
                        "name": "regular_department",
                        "condition": {"field": "weight", "operator": "<=", "threshold": 10},
                        "action": "route_to:regular",
                        "priority": 40,
                        "enabled": True,
                    },
                    {
                        "name": "heavy_department",
                        "condition": {"field": "weight", "operator": ">", "threshold": 10},
                        "action": "route_to:heavy",
                        "priority": 30,
                        "enabled": True,
                    },
                ],
            },
        }
        r = await client.post("/api/v1/route/simulate", headers=HEADERS, json=payload)
        data = r.json()
        assert r.status_code == 200
        assert data["changed_routes"] == 1
        assert data["proposed_ruleset_version"] == "v2"


class TestFeatureFlags:
    @pytest.mark.asyncio
    async def test_xml_upload_disabled_by_flag(self, client):
        app.state.flags.xml_batch_upload_enabled = False
        r = await client.post("/api/v1/route/batch", headers=HEADERS, files=make_xml_file(SAMPLE_XML))
        assert r.status_code == 403
        app.state.flags.xml_batch_upload_enabled = True

    @pytest.mark.asyncio
    async def test_simulation_disabled_by_flag(self, client):
        app.state.flags.ruleset_simulation_enabled = False
        payload = {"parcels": [{"weight": 0.5, "value": 50, "destination": "DE"}]}
        r = await client.post("/api/v1/route/simulate", headers=HEADERS, json=payload)
        assert r.status_code == 403
        app.state.flags.ruleset_simulation_enabled = True

    @pytest.mark.asyncio
    async def test_insurance_blocking_flag_updates_message_and_dispatch(self, client):
        app.state.flags.insurance_review_blocking_enabled = True
        r = await client.post(
            "/api/v1/route",
            headers=HEADERS,
            json={"weight": 0.5, "value": 1500, "destination": "DE"},
        )
        data = r.json()
        assert r.status_code == 200
        assert data["requires_insurance"] is True
        assert data["dispatch_allowed"] is False
        assert "blocked until insurance approval" in data["message"]
        app.state.flags.insurance_review_blocking_enabled = False


class TestMetricsEndpoint:
    @pytest.mark.asyncio
    async def test_metrics_returns_200(self, client):
        r = await client.get("/api/v1/metrics", headers=HEADERS)
        assert r.status_code == 200

    @pytest.mark.asyncio
    async def test_metrics_counts_routed_and_insured_parcels(self, client):
        await client.post(
            "/api/v1/route",
            headers=HEADERS,
            json={"weight": 0.5, "value": 1500, "destination": "DE"},
        )
        r = await client.get("/api/v1/metrics", headers=HEADERS)
        data = r.json()

        assert "metrics" in data
        assert data["metrics"].get("parcels_routed_total", 0) >= 1
        assert data["metrics"].get("parcels_requires_insurance_total", 0) >= 1

    @pytest.mark.asyncio
    async def test_metrics_records_batch_failures(self, client):
        parcels = [
            {"weight": 0.5, "value": 50, "destination": "DE"},
            {"weight": -1.0, "value": 50, "destination": "DE"},
        ]
        await client.post("/api/v1/route/batch", headers=HEADERS, files=make_json_file(parcels))
        r = await client.get("/api/v1/metrics", headers=HEADERS)
        data = r.json()

        assert data["metrics"].get("batch_records_failed_total", 0) >= 1