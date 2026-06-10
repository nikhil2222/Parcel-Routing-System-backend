import operator as op
from app.models import Parcel, RoutingResult, Department
from app.config_loader import Rule

OPERATOR_MAP = {
    "<": op.lt,
    "<=": op.le,
    ">": op.gt,
    ">=": op.ge,
    "==": op.eq,
    "!=": op.ne,
}


def _evaluate_condition(parcel: Parcel, rule: Rule) -> bool:
    cond = rule.condition
    parcel_value = getattr(parcel, cond.field)
    operator_fn = OPERATOR_MAP[cond.operator]
    return operator_fn(parcel_value, cond.threshold)


class RoutingEngine:
    def __init__(self, rules: list[Rule], version: str = "v1"):
        self.rules = rules
        self.version = version

    def route(self, parcel: Parcel) -> RoutingResult:
        flags: list[str] = []
        rules_matched: list[str] = []
        department: Department = Department.UNROUTED

        for rule in self.rules:
            if not _evaluate_condition(parcel, rule):
                continue

            if rule.action.startswith("flag:"):
                flag_name = rule.action.split("flag:")[1]
                flags.append(flag_name)
                rules_matched.append(rule.name)

            elif rule.action.startswith("route_to:"):
                dept_name = rule.action.split("route_to:")[1]
                try:
                    department = Department(dept_name)
                except ValueError:
                    department = Department.UNROUTED
                rules_matched.append(rule.name)
                break

        requires_insurance = "requires_insurance" in flags
        message = _build_message(department, requires_insurance)

        return RoutingResult(
            parcel=parcel,
            department=department,
            flags=flags,
            rules_matched=rules_matched,
            requires_insurance=requires_insurance,
            message=message,
            ruleset_version=self.version,
        )

    def route_batch(self, parcels: list[Parcel]) -> list[RoutingResult]:
        return [self.route(p) for p in parcels]


def _build_message(department: Department, requires_insurance: bool) -> str:
    base = {
        Department.MAIL: "Routed to Mail Department",
        Department.REGULAR: "Routed to Regular Department",
        Department.HEAVY: "Routed to Heavy Department",
        Department.UNROUTED: "Could not be routed — no matching rule",
    }[department]

    if requires_insurance:
        base += " — Insurance approval required before dispatch"
    return base