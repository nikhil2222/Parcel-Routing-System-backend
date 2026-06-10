"""
Phase 2: Routing Engine Unit Tests
===================================
Every business rule has at least one named test.
Boundary values (exactly 1kg, exactly 10kg, exactly €1000) are tested explicitly.
"""
import pytest
from pathlib import Path
from app.models import Parcel, Department
from app.config_loader import load_rules
from app.router import RoutingEngine

CONFIG_PATH = Path(__file__).parent.parent / "config" / "routing_rules.yaml"


@pytest.fixture(scope="module")
def engine():
    rules = load_rules(CONFIG_PATH)
    return RoutingEngine(rules)


def make_parcel(weight: float, value: float = 100.0, destination: str = "DE") -> Parcel:
    return Parcel(weight=weight, value=value, destination=destination)


# ─── Department Routing Rules ───────────────────────────────────────────────

class TestMailDepartment:
    def test_light_parcel_goes_to_mail(self, engine):
        result = engine.route(make_parcel(weight=0.5))
        assert result.department == Department.MAIL

    def test_exactly_1kg_goes_to_mail(self, engine):
        """Boundary: exactly 1kg must go to mail (<=1)"""
        result = engine.route(make_parcel(weight=1.0))
        assert result.department == Department.MAIL

    def test_very_light_parcel(self, engine):
        result = engine.route(make_parcel(weight=0.1))
        assert result.department == Department.MAIL


class TestRegularDepartment:
    def test_medium_parcel_goes_to_regular(self, engine):
        result = engine.route(make_parcel(weight=5.0))
        assert result.department == Department.REGULAR

    def test_just_over_1kg_goes_to_regular(self, engine):
        """Boundary: just above 1kg must go to regular"""
        result = engine.route(make_parcel(weight=1.01))
        assert result.department == Department.REGULAR

    def test_exactly_10kg_goes_to_regular(self, engine):
        """Boundary: exactly 10kg must go to regular (<=10)"""
        result = engine.route(make_parcel(weight=10.0))
        assert result.department == Department.REGULAR


class TestHeavyDepartment:
    def test_heavy_parcel_goes_to_heavy(self, engine):
        result = engine.route(make_parcel(weight=25.0))
        assert result.department == Department.HEAVY

    def test_just_over_10kg_goes_to_heavy(self, engine):
        """Boundary: just above 10kg must go to heavy"""
        result = engine.route(make_parcel(weight=10.01))
        assert result.department == Department.HEAVY

    def test_very_heavy_parcel(self, engine):
        result = engine.route(make_parcel(weight=100.0))
        assert result.department == Department.HEAVY


# ─── Insurance Flag Rules ───────────────────────────────────────────────────

class TestInsuranceFlag:
    def test_high_value_parcel_requires_insurance(self, engine):
        result = engine.route(make_parcel(weight=0.5, value=1500))
        assert result.requires_insurance is True
        assert "requires_insurance" in result.flags

    def test_exactly_1000_does_not_require_insurance(self, engine):
        """Boundary: exactly €1000 does NOT trigger insurance (condition is >1000)"""
        result = engine.route(make_parcel(weight=0.5, value=1000.0))
        assert result.requires_insurance is False

    def test_just_over_1000_requires_insurance(self, engine):
        """Boundary: €1000.01 DOES trigger insurance"""
        result = engine.route(make_parcel(weight=0.5, value=1000.01))
        assert result.requires_insurance is True

    def test_low_value_parcel_no_insurance(self, engine):
        result = engine.route(make_parcel(weight=5.0, value=50.0))
        assert result.requires_insurance is False

    def test_insurance_flag_does_not_change_department(self, engine):
        """Insurance flag must NOT override the routing department"""
        result = engine.route(make_parcel(weight=0.5, value=1500))
        assert result.department == Department.MAIL
        assert result.requires_insurance is True

    def test_heavy_parcel_with_insurance(self, engine):
        result = engine.route(make_parcel(weight=15.0, value=2000))
        assert result.department == Department.HEAVY
        assert result.requires_insurance is True


# ─── Rules Matched Audit Trail ──────────────────────────────────────────────

class TestRulesMatched:
    def test_rules_matched_recorded(self, engine):
        result = engine.route(make_parcel(weight=0.5))
        assert "mail_department" in result.rules_matched

    def test_insurance_rule_in_matched(self, engine):
        result = engine.route(make_parcel(weight=0.5, value=1500))
        assert "insurance_required" in result.rules_matched
        assert "mail_department" in result.rules_matched

    def test_no_extra_rules_matched(self, engine):
        """Routing stops at first matching route rule — no extra dept rules"""
        result = engine.route(make_parcel(weight=0.5))
        dept_rules = [r for r in result.rules_matched if "department" in r]
        assert len(dept_rules) == 1


# ─── Message Output ─────────────────────────────────────────────────────────

class TestMessages:
    def test_mail_message(self, engine):
        result = engine.route(make_parcel(weight=0.5))
        assert "Mail" in result.message

    def test_insurance_message_appended(self, engine):
        result = engine.route(make_parcel(weight=0.5, value=1500))
        assert "Insurance" in result.message

    def test_heavy_message(self, engine):
        result = engine.route(make_parcel(weight=20.0))
        assert "Heavy" in result.message


# ─── Batch Routing ──────────────────────────────────────────────────────────

class TestBatchRouting:
    def test_batch_routes_all_parcels(self, engine):
        parcels = [
            make_parcel(0.5),
            make_parcel(5.0),
            make_parcel(15.0),
        ]
        results = engine.route_batch(parcels)
        assert len(results) == 3
        assert results[0].department == Department.MAIL
        assert results[1].department == Department.REGULAR
        assert results[2].department == Department.HEAVY

    def test_batch_with_insurance(self, engine):
        parcels = [make_parcel(0.5, value=1500), make_parcel(5.0, value=500)]
        results = engine.route_batch(parcels)
        assert results[0].requires_insurance is True
        assert results[1].requires_insurance is False


# ─── Config Loader ──────────────────────────────────────────────────────────

class TestConfigLoader:
    def test_rules_load_successfully(self):
        rules = load_rules(CONFIG_PATH)
        assert len(rules) > 0

    def test_rules_sorted_by_priority(self):
        rules = load_rules(CONFIG_PATH)
        priorities = [r.priority for r in rules]
        assert priorities == sorted(priorities, reverse=True)

    def test_all_rules_enabled(self):
        rules = load_rules(CONFIG_PATH)
        assert all(r.enabled for r in rules)

    def test_invalid_config_raises_error(self, tmp_path):
        bad_config = tmp_path / "bad_rules.yaml"
        bad_config.write_text("""
rules:
  - name: "broken"
    condition:
      field: "invalid_field"
      operator: ">"
      threshold: 10
    action: "route_to:mail"
    priority: 50
    enabled: true
""")
        with pytest.raises(Exception):
            load_rules(bad_config)