import pytest
from app.config_loader import load_rules_with_metadata
from app.models import Parcel
from app.router import RoutingEngine

API_KEY = "dev-secret-key-change-in-production"
HEADERS = {"X-API-Key": API_KEY}


def test_ruleset_version_loaded():
    loaded = load_rules_with_metadata()
    assert loaded.version == "v1"


def test_duplicate_rule_names_rejected():
    raw = {
        "version": "v2",
        "rules": [
            {
                "name": "dup",
                "condition": {"field": "weight", "operator": "<=", "threshold": 1},
                "action": "route_to:mail",
                "priority": 50,
                "enabled": True,
            },
            {
                "name": "dup",
                "condition": {"field": "weight", "operator": ">", "threshold": 1},
                "action": "route_to:heavy",
                "priority": 40,
                "enabled": True,
            },
        ],
    }
    with pytest.raises(ValueError, match="Duplicate rule names"):
        load_rules_with_metadata(raw_data=raw)


def test_duplicate_route_priorities_rejected():
    raw = {
        "version": "v2",
        "rules": [
            {
                "name": "mail_department",
                "condition": {"field": "weight", "operator": "<=", "threshold": 1},
                "action": "route_to:mail",
                "priority": 50,
                "enabled": True,
            },
            {
                "name": "heavy_department",
                "condition": {"field": "weight", "operator": ">", "threshold": 10},
                "action": "route_to:heavy",
                "priority": 50,
                "enabled": True,
            },
        ],
    }
    with pytest.raises(ValueError, match="Duplicate priorities"):
        load_rules_with_metadata(raw_data=raw)


def test_duplicate_weight_condition_and_action_rejected():
    raw = {
        "version": "v2",
        "rules": [
            {
                "name": "rule_a",
                "condition": {"field": "weight", "operator": "<=", "threshold": 10},
                "action": "route_to:regular",
                "priority": 50,
                "enabled": True,
            },
            {
                "name": "rule_b",
                "condition": {"field": "weight", "operator": "<=", "threshold": 10},
                "action": "route_to:regular",
                "priority": 40,
                "enabled": True,
            },
        ],
    }
    with pytest.raises(ValueError, match="Duplicate weight route rule"):
        load_rules_with_metadata(raw_data=raw)


def test_ruleset_version_propagates_to_results():
    loaded = load_rules_with_metadata()
    engine = RoutingEngine(loaded.rules, version=loaded.version)
    result = engine.route(Parcel(weight=1, value=10, destination="DE"))
    assert result.ruleset_version == "v1"


@pytest.mark.asyncio
async def test_simulate_new_rule_before_live_enablement(app_client):
    payload = {
        "parcels": [{"weight": 0.5, "value": 100, "destination": "UK"}],
        "proposed_rules": {
            "version": "v2",
            "rules": [
                {
                    "name": "insurance_required",
                    "condition": {"field": "value", "operator": ">", "threshold": 1000},
                    "action": "flag:requires_insurance",
                    "priority": 100,
                    "enabled": True,
                },
                {
                    "name": "light_regular_uk",
                    "condition": {"field": "destination", "operator": "==", "threshold": "UK"},
                    "action": "route_to:regular",
                    "priority": 95,
                    "enabled": True,
                },
                {
                    "name": "mail_department",
                    "condition": {"field": "weight", "operator": "<=", "threshold": 1},
                    "action": "route_to:mail",
                    "priority": 90,
                    "enabled": True,
                },
                {
                    "name": "regular_department",
                    "condition": {"field": "weight", "operator": "<=", "threshold": 10},
                    "action": "route_to:regular",
                    "priority": 80,
                    "enabled": True,
                },
                {
                    "name": "heavy_department",
                    "condition": {"field": "weight", "operator": ">", "threshold": 10},
                    "action": "route_to:heavy",
                    "priority": 70,
                    "enabled": True,
                },
            ],
        },
    }

    r = app_client.post("/api/v1/route/simulate", headers=HEADERS, json=payload)
    data = r.json()

    assert r.status_code == 200
    assert data["changed_routes"] == 1
    assert data["diffs"][0]["current_department"] == "mail"
    assert data["diffs"][0]["proposed_department"] == "regular"
    assert data["proposed_ruleset_version"] == "v2"