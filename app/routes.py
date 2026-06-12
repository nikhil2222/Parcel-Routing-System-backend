import json
import structlog
import xml.etree.ElementTree as ET
from fastapi import APIRouter, Request, HTTPException, UploadFile, File, Security

from app.models import Parcel, RoutingResult, BatchRoutingResult, RuleSimulationRequest, RuleSimulationResponse, RuleDiffItem
from app.router import RoutingEngine
from app.config_loader import load_rules_with_metadata
from app.security import get_api_key

logger = structlog.get_logger()
router = APIRouter()

MAX_BATCH_SIZE = 10_000
MAX_FILE_BYTES = 5 * 1024 * 1024 


def _child_text(node, tag: str, default: str = "") -> str:
    child = node.find(tag)
    if child is None or child.text is None:
        return default
    return child.text.strip()


def _parse_xml_batch(contents: bytes) -> list[dict]:
    try:
        root = ET.fromstring(contents)
    except ET.ParseError as e:
        raise HTTPException(status_code=400, detail=f"Invalid XML: {str(e)}")

    parcels_parent = root.find("parcels")
    if parcels_parent is None:
        raise HTTPException(status_code=400, detail="XML must contain a <parcels> element.")

    raw_data = []
    for parcel_node in parcels_parent.findall("Parcel"):
        recipient = parcel_node.find("Receipient")
        address = recipient.find("Address") if recipient is not None else None
        destination_parts = []
        if address is not None:
            for tag in ("City", "PostalCode"):
                value = _child_text(address, tag)
                if value:
                    destination_parts.append(value)
        destination = ", ".join(destination_parts) or "UNKNOWN"

        raw_data.append({
            "weight": _child_text(parcel_node, "Weight", "0"),
            "value": _child_text(parcel_node, "Value", "0"),
            "destination": destination,
            "extra": {
                "container_id": _child_text(root, "Id", ""),
                "shipping_date": _child_text(root, "ShippingDate", ""),
                "recipient": {
                    "name": _child_text(recipient, "Name", "") if recipient is not None else "",
                    "address": {
                        "street": _child_text(address, "Street", "") if address is not None else "",
                        "house_number": _child_text(address, "HouseNumber", "") if address is not None else "",
                        "postal_code": _child_text(address, "PostalCode", "") if address is not None else "",
                        "city": _child_text(address, "City", "") if address is not None else "",
                    },
                },
            },
        })

    return raw_data


@router.post(
    "/route",
    response_model=RoutingResult,
    summary="Route a single parcel",
    tags=["Routing"],
)
async def route_parcel(
    parcel: Parcel,
    request: Request,
    _api_key: str = Security(get_api_key),
):
    engine: RoutingEngine = request.app.state.engine
    result = engine.route(parcel)

    if request.app.state.flags.insurance_review_blocking_enabled and result.requires_insurance:
        result.dispatch_allowed = False
        result.message += " — Routing is blocked until insurance approval is completed"

    metrics = request.app.state.metrics
    metrics.incr("parcels_routed_total")
    metrics.incr(f"department_{result.department.value}_total")
    if result.requires_insurance:
        metrics.incr("parcels_requires_insurance_total")
        if not result.dispatch_allowed:
            metrics.incr("insurance_blocked_total")
    if result.department.value == "unrouted":
        metrics.incr("parcels_unrouted_total")

    request.app.state.parcel_history.append({
        "weight": parcel.weight,
        "value": parcel.value,
        "destination": parcel.destination,
        "extra": parcel.extra,
        "department": result.department.value,
        "requires_insurance": result.requires_insurance,
        "dispatch_allowed": result.dispatch_allowed,
        "message": result.message,
        "rules_matched": result.rules_matched,
    })

    logger.info(
        "parcel_routed",
        department=result.department.value,
        weight=parcel.weight,
        value=parcel.value,
        destination=parcel.destination,
        flags=result.flags,
        rules_matched=result.rules_matched,
        requires_insurance=result.requires_insurance,
        insurance_blocking_enabled=request.app.state.flags.insurance_review_blocking_enabled,
    )
    return result

@router.post(
    "/route/batch",
    response_model=BatchRoutingResult,
    summary="Route a batch of parcels from a JSON or XML file",
    tags=["Routing"],
)
async def route_batch(
    request: Request,
    file: UploadFile = File(...),
    _api_key: str = Security(get_api_key),
):
    if not file.filename or not (file.filename.endswith(".json") or file.filename.endswith(".xml")):
        raise HTTPException(status_code=400, detail="Only .json and .xml files are accepted.")

    if file.filename.endswith(".xml") and not request.app.state.flags.xml_batch_upload_enabled:
        raise HTTPException(status_code=403, detail="XML batch upload is currently disabled.")

    contents = await file.read()
    if len(contents) > MAX_FILE_BYTES:
        raise HTTPException(status_code=413, detail="File too large. Maximum size is 5MB.")

    if file.filename.endswith(".json"):
        try:
            raw_data = json.loads(contents)
        except json.JSONDecodeError as e:
            raise HTTPException(status_code=400, detail=f"Invalid JSON: {str(e)}")
        if not isinstance(raw_data, list):
            raise HTTPException(status_code=400, detail="JSON must be a list of parcel objects.")
    else:
        raw_data = _parse_xml_batch(contents)

    if len(raw_data) > MAX_BATCH_SIZE:
        raise HTTPException(
            status_code=400,
            detail=f"Batch too large. Maximum {MAX_BATCH_SIZE} parcels per request.",
        )

    engine: RoutingEngine = request.app.state.engine
    results, errors = [], []

    for idx, item in enumerate(raw_data):
        try:
            parcel = Parcel(**item)
            result = engine.route(parcel)
            if request.app.state.flags.insurance_review_blocking_enabled and result.requires_insurance:
                result.dispatch_allowed = False
                result.message += " — Routing is blocked until insurance approval is completed"

     
            request.app.state.parcel_history.append({
                "weight": parcel.weight,
                "value": parcel.value,
                "destination": parcel.destination,
                "extra": parcel.extra,
                "department": result.department.value,
                "requires_insurance": result.requires_insurance,
                "dispatch_allowed": result.dispatch_allowed,
                "message": result.message,
                "rules_matched": result.rules_matched,
            })

            metrics = request.app.state.metrics
            metrics.incr("parcels_routed_total")
            metrics.incr(f"department_{result.department.value}_total")
            if result.requires_insurance:
                metrics.incr("parcels_requires_insurance_total")
                if not result.dispatch_allowed:
                    metrics.incr("insurance_blocked_total")
            if result.department.value == "unrouted":
                metrics.incr("parcels_unrouted_total")
 
            results.append(result)
        except Exception as e:
            errors.append({"index": idx, "data": item, "error": str(e)})
            request.app.state.metrics.incr("batch_records_failed_total")

    request.app.state.metrics.incr("batch_requests_total")
    request.app.state.metrics.incr("batch_records_total", len(raw_data))

    logger.info("batch_routed", total=len(raw_data), routed=len(results), failed=len(errors))

    if results:
        insurance_count = sum(1 for r in results if r.requires_insurance)
        unrouted_count = sum(1 for r in results if r.department.value == "unrouted")

        if insurance_count > 0:
            logger.warning(
                "anomaly_insurance_spike",
                insurance_count=insurance_count,
                insurance_rate_pct=round(insurance_count / len(results) * 100, 1),
                total_parcels=len(results),
            )
        if unrouted_count > 0:
            logger.warning(
                "anomaly_unrouted_parcels",
                unrouted_count=unrouted_count,
                total_parcels=len(results),
            )

    return BatchRoutingResult(
        total=len(raw_data),
        routed=len(results),
        failed=len(errors),
        results=results,
        errors=errors,
    )

@router.post(
    "/route/simulate",
    response_model=RuleSimulationResponse,
    summary="Simulate a proposed ruleset against sample parcels",
    tags=["Configuration"],
)
async def simulate_rules(
    payload: RuleSimulationRequest,
    request: Request,
    _api_key: str = Security(get_api_key),
):
    if not request.app.state.flags.ruleset_simulation_enabled:
        raise HTTPException(status_code=403, detail="Ruleset simulation is currently disabled.")

    current_engine: RoutingEngine = request.app.state.engine

    if payload.proposed_rules:
        loaded = load_rules_with_metadata(raw_data=payload.proposed_rules)
        proposed_engine = RoutingEngine(loaded.rules, version=loaded.version)
        proposed_version = loaded.version
    else:
        proposed_engine = current_engine
        proposed_version = current_engine.version

    diffs = []
    changed_routes = 0
    changed_flags = 0

    for parcel in payload.parcels:
        current = current_engine.route(parcel)
        proposed = proposed_engine.route(parcel)
        route_changed = current.department != proposed.department
        flags_changed = sorted(current.flags) != sorted(proposed.flags)
        if route_changed:
            changed_routes += 1
        if flags_changed:
            changed_flags += 1
        diffs.append(RuleDiffItem(
            parcel=parcel,
            current_department=current.department,
            proposed_department=proposed.department,
            current_flags=current.flags,
            proposed_flags=proposed.flags,
            changed=route_changed or flags_changed,
        ))

    request.app.state.metrics.incr("ruleset_simulations_total")

    return RuleSimulationResponse(
        current_ruleset_version=current_engine.version,
        proposed_ruleset_version=proposed_version,
        total_parcels=len(payload.parcels),
        changed_routes=changed_routes,
        changed_flags=changed_flags,
        diffs=diffs,
    )


@router.get(
    "/rules",
    summary="List all active routing rules",
    tags=["Configuration"],
)
async def get_rules(
    request: Request,
    _api_key: str = Security(get_api_key),
):
    engine: RoutingEngine = request.app.state.engine
    return {
        "version": engine.version,
        "total": len(engine.rules),
        "rules": [
            {
                "name": r.name,
                "description": r.description,
                "field": r.condition.field,
                "operator": r.condition.operator,
                "threshold": r.condition.threshold,
                "action": r.action,
                "priority": r.priority,
            }
            for r in engine.rules
        ],
    }


@router.get("/metrics", summary="Simple operational counters", tags=["System"])
async def get_metrics(request: Request, _api_key: str = Security(get_api_key)):
    metrics = request.app.state.metrics.snapshot()
    alerts = []
    if metrics.get("parcels_unrouted_total", 0) > 0:
        alerts.append("Unrouted parcels detected")
    if metrics.get("batch_records_failed_total", 0) > 0:
        alerts.append("Batch record failures detected")
    if metrics.get("insurance_blocked_total", 0) > 0:
        alerts.append("Insurance-blocked parcels present")
    return {"metrics": metrics, "alerts": alerts}


@router.get(
    "/history",
    summary="Get last 100 routed parcels (in-memory only)",
    tags=["History"],
)
async def get_history(
    request: Request,
    _api_key: str = Security(get_api_key),
):
    history = list(request.app.state.parcel_history)
    return {"total": len(history), "parcels": history[::-1]}