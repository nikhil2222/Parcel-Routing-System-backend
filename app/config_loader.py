import yaml
from pathlib import Path
from pydantic import BaseModel, field_validator, model_validator

VALID_OPERATORS = {"<", "<=", ">", ">=", "==", "!="}
VALID_FIELDS = {"weight", "value", "destination"}
VALID_ACTIONS_PREFIX = {"route_to:", "flag:"}


class RuleCondition(BaseModel):
    field: str
    operator: str
    threshold: float | str

    @field_validator("field")
    @classmethod
    def field_must_be_valid(cls, v: str) -> str:
        if v not in VALID_FIELDS:
            raise ValueError(f"Invalid condition field '{v}'. Must be one of: {VALID_FIELDS}")
        return v

    @field_validator("operator")
    @classmethod
    def operator_must_be_valid(cls, v: str) -> str:
        if v not in VALID_OPERATORS:
            raise ValueError(f"Invalid operator '{v}'. Must be one of: {VALID_OPERATORS}")
        return v


class Rule(BaseModel):
    name: str
    description: str = ""
    condition: RuleCondition
    action: str
    priority: int = 0
    enabled: bool = True

    @field_validator("action")
    @classmethod
    def action_must_be_valid(cls, v: str) -> str:
        if not any(v.startswith(prefix) for prefix in VALID_ACTIONS_PREFIX):
            raise ValueError(
                f"Invalid action '{v}'. Must start with one of: {VALID_ACTIONS_PREFIX}"
            )
        return v


class RoutingConfig(BaseModel):
    version: str = "v1"
    rules: list[Rule]

    @model_validator(mode="after")
    def validate_ruleset(self):
        names = [r.name for r in self.rules]
        if len(names) != len(set(names)):
            raise ValueError("Duplicate rule names detected. Rule names must be unique.")

        route_rules = [r for r in self.rules if r.enabled and r.action.startswith("route_to:")]
        self._validate_priority_collisions(route_rules)
        self._validate_weight_overlap(route_rules)
        return self

    def _validate_priority_collisions(self, route_rules: list[Rule]):
        priorities = [r.priority for r in route_rules]
        if len(priorities) != len(set(priorities)):
            raise ValueError(
                "Duplicate priorities detected among route rules. Use unique priorities for deterministic routing."
            )

    def _validate_weight_overlap(self, route_rules: list[Rule]):
        weight_rules = [r for r in route_rules if r.condition.field == "weight"]
        if len(weight_rules) < 2:
            return

        # Allow intentional first-match tiering like <=1, <=10, >10.
        # Reject only exact duplicate conditions that create ambiguous duplicates.
        signatures = []
        for rule in weight_rules:
            sig = (rule.condition.field, rule.condition.operator, float(rule.condition.threshold), rule.action)
            if sig in signatures:
                raise ValueError(
                    f"Duplicate weight route rule detected for condition/action: '{rule.name}'."
                )
            signatures.append(sig)


class LoadedRules(BaseModel):
    version: str
    rules: list[Rule]


def _condition_to_range(operator: str, threshold: float | str):
    if not isinstance(threshold, (int, float)):
        return float("-inf"), float("inf")
    t = float(threshold)
    eps = 1e-9
    return {
        "<": (float("-inf"), t - eps),
        "<=": (float("-inf"), t),
        ">": (t + eps, float("inf")),
        ">=": (t, float("inf")),
        "==": (t, t),
        "!=": (float("-inf"), float("inf")),
    }[operator]


def _ranges_overlap(lo_a: float, hi_a: float, lo_b: float, hi_b: float) -> bool:
    return max(lo_a, lo_b) <= min(hi_a, hi_b)


def load_rules(config_path: Path | str | None = None) -> list[Rule]:
    return load_rules_with_metadata(config_path).rules


def load_rules_with_metadata(config_path: Path | str | None = None, raw_data: dict | None = None) -> LoadedRules:
    if raw_data is None:
        if config_path is None:
            config_path = Path(__file__).parent.parent / "config" / "routing_rules.yaml"
        config_path = Path(config_path)
        if not config_path.exists():
            raise FileNotFoundError(f"Routing config not found: {config_path}")
        with open(config_path, "r") as f:
            raw_data = yaml.safe_load(f)

    config = RoutingConfig(**raw_data)
    enabled_rules = [r for r in config.rules if r.enabled]
    sorted_rules = sorted(enabled_rules, key=lambda r: r.priority, reverse=True)
    return LoadedRules(version=config.version, rules=sorted_rules)