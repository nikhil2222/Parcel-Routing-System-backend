# 🧩 Technical Assessment: Parcel Routing System

## Overview

You are a developer at a parcel delivery company responsible for modernizing an internal parcel routing system.

The system processes parcels and routes them to different departments based on business rules.

The company expects the system to:

- Be adaptable to business changes
- Be reliable when failures occur
- Be safe to evolve
- Provide sufficient visibility when something goes wrong
- Demonstrate thoughtful engineering beyond basic coding

You are encouraged to use AI tools during development. However, you must demonstrate ownership of the design and clearly explain your reasoning.

---

## 📦 Core Requirements

### 1. Parcel Routing

Each parcel contains:

- Weight (kg)
- Value (€)
- Destination country
- Optional additional attributes

#### Default Routing Rules

- Up to 1 kg → **Mail Department**
- Up to 10 kg → **Regular Department**
- Over 10 kg → **Heavy Department**
- Parcels with value greater than €1,000 require **Insurance approval** before routing

#### Expectations

- Implement routing logic.
- Make business rules adaptable to change.
- Design the system so that future departments or routing conditions can be added without major refactoring.
- Consider how rule changes could impact system correctness and safety.

> You are not given strict instructions on how to handle configuration safety — your design should account for business risks.

---

### 2. User Interface

Provide a simple interface that allows:

- Entering parcel data
- Uploading batch data (JSON or XML — your choice, justify it)
- Viewing routing outcomes clearly

The interface should:

- Be usable by non-technical operators
- Communicate decisions clearly
- Handle large input files gracefully
- Be responsive (if web-based)

Focus on clarity and usability over visual complexity.

---

### 3. Quality Assurance

- Include automated tests for routing logic.
- Demonstrate how your tests protect against regressions.
- Show how you would introduce a new rule safely.
- Include a small example of feature development from branch to merge.

Also describe how you validate correctness beyond automated tests.

---

### 4. Monitoring & Reliability

Design the system so that if something goes wrong, the team is notified and there is enough information available to investigate, resolve the issue, and detect unusual patterns in parcel routing.

---

### 5. Security

This application will be deployed facing the public internet. Implement appropriate measures to safeguard it.

Consider how you would protect the system against common threats.

#### Requirements

- Implement security measures in your application.
- Be prepared to explain:
  - What additional measures you would implement to secure the system.
  - Why those measures are important.

---

### 6. Debugging

You will be provided with a buggy routing function during the interview.

Be prepared to:

- Identify the issue quickly
- Explain how you reasoned about it
- Fix it cleanly
- Prevent similar issues in the future

---

### 7. AI Usage

You are expected to use AI tools for at least two parts of this assignment.

You must:

- Show the prompts you used
- Explain what you modified and why
- Demonstrate that you understand the generated code
- Reflect on limitations of AI in this context

---

## 📂 Deliverables

- Production-ready application
- You can choose any programming language
- Tests
- Configuration system (if used)
- README including:
  - Architecture decisions
  - Trade-offs
  - AI usage documentation
  - How to extend the system with new routing rules
- Short presentation (10–15 minutes)

---

## 🎤 Interview Expectations

During the interview, you should be able to:

- Demo your system end-to-end
- Modify or extend routing logic live
- Explain design trade-offs
- Explain how your system adapts to business change
- Discuss how failures would be handled
- Walk through your AI-assisted development process

---

## 🧠 What We Are Evaluating

- Engineering judgment
- Adaptability
- System thinking
- Code quality
- UX awareness
- Testing discipline
- Ability to reason about failure
- Responsible use of AI tools

---

This assessment is intentionally open-ended. There is no single correct implementation.

---

## 🚀 Live Deployment

| Component | URL |
|-----------|-----|
| Frontend | https://parcel-routing-system.netlify.app |
| Backend API | https://parcel-routing-system-backend.onrender.com |
| API Docs (Swagger) | https://parcel-routing-system-backend.onrender.com/docs |

---

## 🏗 Architecture

The system is split into two independent layers — a stateless FastAPI backend and a React frontend. This separation makes each layer independently deployable, testable, and scalable.

```
parcel-routing/
├── backend/
│   ├── app/
│   │   ├── __init__.py
│   │   ├── main.py              # App bootstrap, middleware, security headers, lifespan
│   │   ├── routes.py            # All API endpoints
│   │   ├── router.py            # Routing engine — evaluates rules against parcels
│   │   ├── config_loader.py     # YAML rule loader with safety validation
│   │   ├── models.py            # Pydantic request/response models
│   │   ├── security.py          # API key auth, CORS, trusted hosts config
│   │   ├── metrics.py           # In-memory operational counters
│   │   ├── feature_flags.py     # Runtime feature flags from environment variables
│   │   ├── limiter.py           # SlowAPI rate limiter setup
│   │   └── logging_config.py    # Structlog + CloudWatch setup
│   ├── config/
│   │   └── routing_rules.yaml   # Active business routing rules
│   ├── tests/
│   │   ├── conftest.py          # Shared fixtures
│   │   ├── test_api.py          # Full API integration tests
│   │   ├── test_routing.py      # Routing engine unit tests
│   │   └── test_rule_safety.py  # Config validation and safety tests
│   ├── .env
│   ├── pytest.ini
│   └── requirements.txt
├── frontend/
│   ├── src/
│   │   ├── api/
│   │   │   ├── client.js        # Axios base client with API key header
│   │   │   └── parcels.js       # API call functions
│   │   ├── components/
│   │   │   ├── Alert.jsx
│   │   │   ├── Badge.jsx
│   │   │   ├── Card.jsx
│   │   │   └── Spinner.jsx
│   │   ├── pages/
│   │   │   ├── RouteParcel.jsx  # Single parcel routing form
│   │   │   ├── BatchUpload.jsx  # Drag-and-drop batch upload
│   │   │   ├── History.jsx      # In-memory routing history table
│   │   │   ├── ActiveRules.jsx  # Live rule viewer
│   │   │   └── SystemHealth.jsx # Metrics and health dashboard
│   │   ├── App.jsx
│   │   └── main.jsx
│   ├── .env
│   ├── vite.config.js
│   └── package.json
└── README.md
```

---

## ⚙️ How Routing Works

Rules are stored in `config/routing_rules.yaml` and loaded at startup. The routing engine evaluates each rule in descending priority order. The insurance rule runs first (priority 100) because it is a flag that applies regardless of department.

```yaml
rules:
  - name: insurance_required
    description: Parcels with value over 1000 EUR require insurance approval
    field: value
    operator: ">"
    threshold: 1000.0
    action: "flag:requires_insurance"
    priority: 100

  - name: mail_department
    description: Parcels up to 1kg go to Mail department
    field: weight
    operator: "<="
    threshold: 1.0
    action: "route_to:mail"
    priority: 50

  - name: regular_department
    description: Parcels above 1kg and up to 10kg go to Regular department
    field: weight
    operator: "<="
    threshold: 10.0
    action: "route_to:regular"
    priority: 40

  - name: heavy_department
    description: Parcels over 10kg go to Heavy department
    field: weight
    operator: ">"
    threshold: 10.0
    action: "route_to:heavy"
    priority: 30
```

Priority numbers are explicit so evaluation order is deterministic and safe to reason about.

---

## 🚩 Feature Flags

Feature flags are controlled through environment variables and loaded at startup via `feature_flags.py`. This means behaviour can be toggled without redeploying code.

| Flag | Default | What it controls |
|------|---------|-----------------|
| `XML_BATCH_UPLOAD_ENABLED` | `true` | Allow or block XML batch uploads |
| `INSURANCE_REVIEW_BLOCKING_ENABLED` | `true` | Block dispatch when insurance approval is required |
| `RULESET_SIMULATION_ENABLED` | `true` | Enable or disable the simulation endpoint |

**Why this matters:** If the insurance approval team goes offline, you can disable blocking without touching the routing logic. If XML uploads cause issues in production, you can disable them instantly without a deployment.

---

## 📡 API Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/health` | App status, rules loaded, feature flags |
| POST | `/api/v1/route` | Route a single parcel |
| POST | `/api/v1/route/batch` | Upload JSON or XML file for batch routing |
| POST | `/api/v1/route/simulate` | Compare current vs proposed ruleset safely |
| GET | `/api/v1/rules` | List all active routing rules |
| GET | `/api/v1/metrics` | In-memory operational counters and alerts |
| GET | `/api/v1/history` | Last 100 routed parcels |

---

## 🖥 User Interface

The frontend is a responsive React app deployed on Netlify, designed for non-technical warehouse operators.

### Pages

| Page | Purpose |
|------|---------|
| Route Parcel | Form to route a single parcel with optional extra key/value fields |
| Batch Upload | Drag-and-drop JSON or XML upload with sample file downloads |
| History | Table of last 100 routed parcels with extra fields, department, insurance, and dispatch |
| Active Rules | Live view of current routing rules with priority, condition, and action |
| System Health | Live metrics, active alerts, feature flags, and health status |

### Why both JSON and XML?

JSON is the default format — easy to generate, easy to read, widely supported. XML is included because many legacy parcel management systems export data in XML. Supporting both formats means the system can integrate with existing tools without requiring data transformation on the operator side.

### Extra attributes

The single parcel form uses a key/value row builder instead of raw JSON. This means non-technical operators can add custom attributes (like fragile, sender name, or priority) without needing to type JSON manually.

---

## ✅ Quality Assurance

### Test coverage — 92%

![Test Coverage](https://drive.google.com/file/d/1rC9uoM2KzWIKwDQF41uSMn2GsPqRWHwB/view?usp=sharing)

Tests cover:

- Routing decisions for all departments (mail, regular, heavy)
- Insurance flag and dispatch blocking behavior
- Batch upload for JSON and XML
- Partial batch failure handling
- Rule simulation and diff output
- Config safety validation (duplicate rule names, duplicate priorities, invalid operators)
- Feature flags enabling and disabling endpoints
- API key authentication
- Security headers
- Metrics counter behavior

### Why not 100%?

The uncovered 8% is intentional:

- **CloudWatch logging handler** (`watchtower`) — requires live AWS credentials and a real log group to test meaningfully. Mocking this provides no real value.
- **Unreachable XML exception paths** — some error branches in the XML parser only trigger on internal library-level failures, not on any realistic input.
- **Middleware edge cases** — certain low-level ASGI middleware paths require invasive mocking that adds maintenance cost without improving confidence.

All critical business logic — routing decisions, insurance, validation, config safety — is fully covered.

### Safe rule introduction — branch to merge example

```
main
 └── feature/add-fragile-routing
      ├── Add rule to config/routing_rules.yaml
      ├── Add test: test_fragile_parcel_routed_correctly
      ├── Run: POST /api/v1/route/simulate with sample parcels
      ├── Review diff output — confirm only expected parcels changed
      ├── Run: pytest — all tests pass
      └── PR reviewed and merged to main
```

### Validation beyond automated tests

- **Simulation endpoint** — run proposed rules against real sample data before deploying
- **Live health page** — check rules loaded count and ruleset version after deploy
- **Metrics page** — verify counters increment correctly after test routing
- **CloudWatch logs** — confirm structured log events appear as expected

---

## 📊 Monitoring & Reliability

### CloudWatch Integration

The backend ships structured logs to AWS CloudWatch using `watchtower` and `structlog`. Every routing decision, batch job, anomaly, and error is logged with structured fields so the team can filter, search, and alert on specific events.

**CloudWatch log screenshots:**

- [Log Stream Overview](https://drive.google.com/file/d/1ZyMNDJMu_4dQejsIHaq9eRCenGTmJBpt/view?usp=sharing)
- [Routing Events](https://drive.google.com/file/d/1B_seBlrMaaL1gZ7B0Z1LA-a9F7GZ-93n/view?usp=sharing)




### Anomaly detection

```python
# Insurance spike — unusually high insurance rate in a batch
logger.warning("anomaly_insurance_spike", insurance_rate_pct=65.0, total_parcels=200)

# Unrouted parcels — parcels that did not match any rule
logger.warning("anomaly_unrouted_parcels", unrouted_count=5, total_parcels=200)
```

### Live metrics and alerts

| Counter | What it tracks |
|---------|---------------|
| `parcels_routed_total` | All routed parcels |
| `department_mail_total` | Routed to Mail |
| `department_regular_total` | Routed to Regular |
| `department_heavy_total` | Routed to Heavy |
| `parcels_requires_insurance_total` | Insurance flag triggered |
| `insurance_blocked_total` | Blocked due to insurance |
| `parcels_unrouted_total` | No rule matched |
| `batch_requests_total` | Total batch uploads |
| `batch_records_total` | Records processed in batches |
| `batch_records_failed_total` | Records that failed in batches |

Alerts are surfaced automatically on the health page when unrouted parcels, batch failures, or insurance-blocked parcels are present.

---

## 🔐 Security

### Implemented measures

| Measure | Implementation |
|---------|---------------|
| API key authentication | `X-API-Key` header required on all endpoints |
| Rate limiting | SlowAPI — limits requests per IP |
| CORS | Only configured origins can call the API |
| Trusted host validation | Blocks requests with spoofed host headers |
| Security headers | `X-Frame-Options`, `X-Content-Type-Options`, `X-XSS-Protection`, `CSP`, `Referrer-Policy` |
| Request size limits | JSON requests capped at 1MB, file uploads capped at 5MB |
| File type validation | Only `.json` and `.xml` accepted in batch upload |
| Input validation | Pydantic validates all fields before processing |
| Global exception handler | All unhandled errors are caught, logged, and return safe messages |

### Additional measures for production

- **HTTPS enforcement** — TLS at load balancer level
- **WAF** — block SQL injection, XSS, and common attack patterns at the edge
- **Secrets management** — API keys in AWS Secrets Manager, not environment variables
- **Audit logging** — track which key performed which action and when
- **Dependency scanning** — automated CVE checks on Python dependencies
- **Container hardening** — non-root user, read-only filesystem in Docker

---

## 🤖 AI Usage

AI tools were used in two specific parts of this project. I used AI as a learning and acceleration tool, not as a replacement for design decisions.

### 1. UI design for the parcel routing interface

I asked AI to help design a clean UI layout for the parcel routing form and batch upload page. It gave a starting structure which I then adapted to match the actual API response shapes, fixed field names that didn't match the backend, and replaced the raw JSON textarea for extra attributes with a key/value builder that is more appropriate for non-technical operators.

Everything generated was reviewed, understood, and modified before use. 

### 2. Learning pytest with a simple example

I had not used `pytest` with `httpx` and async FastAPI testing before. I asked AI for a simple skeleton test example to understand the pattern — how to set up the test client, how to pass headers, and how to assert response fields. I then wrote all actual test cases myself based on that pattern.

The test cases — covering routing decisions, insurance logic, batch failures, config validation, feature flags — were all designed and written by me.

### What I changed and why

- UI field names corrected to match actual API responses
- Extra attribute input replaced with key/value builder (better UX for operators)
- Test skeleton expanded into full test suite covering all business rules
- AI-suggested generic security descriptions replaced with the actual middleware used

### Limitations of AI in this project

- Generated code consistently used wrong field names until corrected against real API output
- AI had no awareness of the actual data shapes — manual correction was required every time
- AI suggestions were sometimes too generic or too complex for the scope of this assessment

---

## 🔧 How to Extend the System

### Adding a new routing rule

1. Open `backend/config/routing_rules.yaml`
2. Add a new entry with a unique name, unique priority, valid field, operator, and action

```yaml
- name: fragile_department
  description: Fragile parcels go to Special Handling
  field: weight
  operator: "<="
  threshold: 2.0
  action: "route_to:fragile"
  priority: 45
```

3. Run simulation to see which parcels are affected before deploying
4. Add a test in `tests/test_routing.py`
5. Verify all existing tests still pass
6. Merge via pull request

### Adding a new department

1. Add the new value to the `Department` enum in `app/models.py`
2. Add routing rules pointing to the new department in YAML
3. Update badge colors in `frontend/src/components/Badge.jsx`
4. Add tests for the new department behavior

### Toggling behavior without deploying

Use feature flags in `.env`:

```
XML_BATCH_UPLOAD_ENABLED=false        # Disable XML batch uploads
INSURANCE_REVIEW_BLOCKING_ENABLED=false  # Stop blocking on insurance
RULESET_SIMULATION_ENABLED=true       # Keep simulation available
```

Restart the backend — no code change needed.

---

## ⚖️ Trade-offs

| Decision | Why | Alternative |
|----------|-----|-------------|
| No database | Routing is stateless; no persistence needed for the assessment | PostgreSQL for audit trail and persistent history |
| In-memory metrics | No infrastructure needed; sufficient for demo and visibility | Prometheus + Grafana for production observability |
| YAML config | Human-readable, version-controlled, easy to validate and diff | Database-driven rule admin UI for non-technical rule management |
| Both JSON and XML | JSON is default; XML covers legacy system compatibility | JSON-only is simpler but limits integration options |
| Bounded deque for history | Memory-safe, no cleanup, shows recent activity clearly | Redis or database for persistent queryable history |
| Feature flags via env vars | Zero-cost runtime control without UI or database | LaunchDarkly or similar for team-managed feature flags |
| API key auth | Simple and sufficient for this scope | OAuth2 / JWT for user-level access control in production |

---

## 🛠 Local Setup

### Backend

```bash
cd backend
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
uvicorn app.main:app --reload
```

### Frontend

```bash
cd frontend
npm install
npm run dev
```

### Run Tests

```bash
cd backend
pytest --cov=app --cov-report=term-missing
```

---

## 🎯 Demo Flow

1. Open **System Health** — shows loaded rules, feature flags, and metrics starting at zero
2. Open **Active Rules** — explains the priority order and why insurance rules run first
3. Go to **Route Parcel** — route a 0.5 kg parcel worth €50 — **Mail + Allowed**
4. Route a 15 kg parcel worth €1,500 — **Heavy + Insurance Required + Blocked**
5. Go to **Batch Upload** — download the sample JSON, upload it, and show the results table
6. Go to **History** — view all routed parcels with extra fields visible
7. Return to **System Health** — see the metrics updated correctly

