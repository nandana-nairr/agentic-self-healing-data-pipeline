# 🔄 Agentic Self-Healing Data Pipeline

> A production-grade, autonomous data platform that detects, diagnoses, and repairs data quality failures without human intervention — powered by an LLM-backed recovery agent, Apache Airflow, dbt, and Great Expectations.

[![CI](https://github.com/nandana-nairr/agentic-self-healing-data-pipeline/actions/workflows/ci.yml/badge.svg)](https://github.com/nandana-nairr/agentic-self-healing-data-pipeline/actions)
![Python](https://img.shields.io/badge/Python-3.11-blue)
![dbt](https://img.shields.io/badge/dbt-1.7-orange)
![Airflow](https://img.shields.io/badge/Airflow-2.9-red)
![License](https://img.shields.io/badge/license-MIT-green)

---

## The Problem

Most data pipelines fail silently. Bad data — nulls, duplicates, invalid values — flows through undetected and reaches analysts as wrong numbers. When engineers discover failures, they fix them manually: hours lost, trust eroded.

**This project solves that.** Instead of stopping on failure, the pipeline:

1. Detects failures via Great Expectations quality gates
2. Sends the failure report to an LLM-powered recovery agent
3. The agent classifies the failure and scores its confidence
4. If confidence is high → automated repair executes
5. If confidence is low → human escalation is triggered
6. Pipeline re-validates and continues
7. Every decision is logged to PostgreSQL with a full audit trail

---

## Architecture

```
AWS S3 (Data Lake)
    ↓
Python Ingestion (Olist e-commerce dataset — 100k+ orders)
    ↓
PostgreSQL (8 raw tables)
    ↓
dbt Core (staging → intermediate → mart)
    ↓
Great Expectations (8 automated quality checks)
    ↓
    ├── ALL PASS → dbt mart models → analysts
    └── FAILURES DETECTED
            ↓
        LLM Recovery Agent (OpenRouter free tier)
            ↓ classifies failure + scores confidence
        Confidence Gate
            ├── HIGH (≥ 0.75) → Deterministic Repair Engine
            │       ↓ repair_orders() / repair_payments()
            │       ↓ quarantine_orders / quarantine_payments tables
            │   Re-validation (Great Expectations reruns)
            │       ├── PASS → pipeline continues ✅
            │       └── FAIL → escalate to human 🚨
            └── LOW (< 0.75) → escalate to human 🚨
                    ↓
        agent_recovery_log (PostgreSQL audit trail)
```

---

## Tech Stack

| Layer | Technology |
|---|---|
| Orchestration | Apache Airflow 2.9 |
| Transformation | dbt Core 1.7 |
| Data Quality | Great Expectations 0.18 |
| Recovery Agent | OpenRouter (free tier LLM) |
| Structured Outputs | Pydantic v2 |
| Data Warehouse | PostgreSQL |
| Data Lake | AWS S3 |
| Containerization | Docker + Docker Compose |
| CI/CD | GitHub Actions |
| Infrastructure as Code | Terraform |
| Language | Python 3.11 |

---

## Dataset

**Olist Brazilian E-Commerce** — 100k+ real orders across 8 interconnected tables (orders, customers, products, sellers, payments, reviews). Available publicly on Kaggle.

**Business metrics produced:**
- Daily revenue trends (`mart_revenue`)
- Delivery SLA breach rate (`mart_delivery_sla`)
- Seller health scores

---

## Self-Healing Mechanisms

### Layer 1 — Airflow (Task-level)
- `retries=3` with 2-minute delay on every task
- `on_failure_callback` fires alerts on repeated failure
- Tasks retry automatically on transient errors

### Layer 2 — Great Expectations (Data-level)
8 quality checks run before any transformation:

| # | Table | Check |
|---|---|---|
| 1 | raw_orders | order_id not null |
| 2 | raw_orders | order_id unique |
| 3 | raw_orders | customer_id not null |
| 4 | raw_orders | order_status valid values |
| 5 | raw_orders | table not empty |
| 6 | raw_payments | order_id not null |
| 7 | raw_payments | payment_value positive |
| 8 | raw_payments | payment_type valid |

### Layer 3 — LLM Recovery Agent (Decision-level)
- LLM receives the failure report and returns a structured `RecoveryDecision`
- Confidence scoring gates automated vs human-escalated repair
- LLM **never executes SQL** — it only classifies and decides
- Deterministic Python owns all database operations

### Layer 4 — Repair Engine (Execution-level)
| Failure Type | Repair Action |
|---|---|
| Null order_id | Quarantine rows → `quarantine_orders` |
| Duplicate order_id | Deduplicate keeping latest by timestamp |
| Null customer_id | Quarantine rows → `quarantine_orders` |
| Invalid order_status | Normalize known variants, quarantine unknown |
| Zero/negative payment | Quarantine → `quarantine_payments` |
| Invalid payment_type | Normalize known variants, quarantine unknown |

Every repair is logged to `repair_log` with row counts and action taken.

---

## Agent Architecture

```
agent/
├── orchestrator_v1.py      # Main loop: Observe→Diagnose→Plan→Execute→Validate
├── schemas.py              # Pydantic models — constrains LLM output to approved tools only
├── tool_executor.py        # Maps LLM tool decisions to real Python repair functions
├── memory.py               # PostgreSQL memory layer — logs every decision
├── test_scenario_a.py      # Deterministic test: high confidence → repaired
├── test_scenario_b.py      # Deterministic test: low confidence → escalated
├── test_scenario_c.py      # Deterministic test: repair attempted → repair_failed
├── inject_test_failure.py  # Injects bad data for demo/testing
└── show_metrics.py         # Historical performance reporting
```

### Safety Design
The LLM can ONLY return one of 5 approved tool names (enforced by Pydantic enum):
```python
class RecoveryTool(str, Enum):
    REPAIR_DUPLICATE_ORDERS = "repair_duplicate_orders"
    REPAIR_NULL_ORDERS      = "repair_null_orders"
    REPAIR_INVALID_STATUS   = "repair_invalid_status"
    QUARANTINE_ROWS         = "quarantine_rows"
    RERUN_VALIDATION        = "rerun_validation"
    NONE                    = "none"
```
If the LLM returns anything else → Pydantic validation fails → no repair executes.

---

## Recovery Metrics

After running all three validated scenarios:

```
════════════════════════════════════════════════════════
  AGENTIC SELF-HEALING PIPELINE — RECOVERY METRICS
════════════════════════════════════════════════════════

Total Runs:                    4
Production Runs:               0
Test Runs:                     4

Repaired:                      2
Escalated:                     1
Repair Failed:                 1

Repair Success Rate:           50.0%
Average Confidence:            0.8
Avg Execution Time (s):        1.88

Most Common Failure:           unknown (3 times)
Most Used Tool:                quarantine_rows (3 times)

────────────────────────────────────────────────────────
  CONFIDENCE + SUCCESS RATE BY FAILURE TYPE
────────────────────────────────────────────────────────
  duplicate_orders         avg_conf=0.95  success=100.0%
  unknown                  avg_conf=0.75  success=33.3%
════════════════════════════════════════════════════════
```

---

## Decision Branches — All Verified

| Scenario | Input | Outcome | Verified |
|---|---|---|---|
| A | High confidence (0.95), real failures | `repaired` | ✅ |
| B | Low confidence (0.40), poisoned execute_fn | `escalated` (no DB touched) | ✅ |
| C | High confidence, repair runs, mocked failing re-validation | `repair_failed` | ✅ |

---

## dbt Model Lineage

```
raw_orders ──────────────────────────────┐
raw_order_items ──┐                      ├─→ int_orders_enriched ─→ mart_revenue
raw_payments ─────┘   stg_order_items ───┘                       ─→ mart_delivery_sla
                       stg_payments
                       stg_orders
```

All models tested with `dbt test`:
- `unique` on order_id
- `not_null` on key columns
- `accepted_values` on order_status

---

## Project Structure

```
agentic-self-healing-data-pipeline/
├── agent/                  # LLM recovery agent
├── dags/                   # Airflow DAGs
├── dbt/ecommerce/          # dbt project (6 models, 3 layers)
│   └── models/
│       ├── staging/        # stg_orders, stg_order_items, stg_payments
│       ├── intermediate/   # int_orders_enriched
│       └── mart/           # mart_revenue, mart_delivery_sla
├── docker/                 # Dockerfile + docker-compose.yml
├── ge/                     # Great Expectations + recovery engine
├── ingestion/              # Python ingestion scripts + Olist data
├── k8s/                    # Kubernetes manifests (deployment, service, HPA)
├── terraform/              # AWS infrastructure as code
├── tests/                  # pytest test suite (9 tests)
└── .github/workflows/      # GitHub Actions CI/CD
```

---

## Quick Start

```bash
# 1. Clone and set up environment
git clone https://github.com/nandana-nairr/agentic-self-healing-data-pipeline.git
cd agentic-self-healing-data-pipeline
python -m venv venv && venv\Scripts\activate
pip install -r requirements.txt

# 2. Configure environment
cp .env.example .env
# Add your AWS and OpenRouter keys to .env

# 3. Load Olist data into PostgreSQL
python ingestion/load_data.py

# 4. Run dbt transformations
cd dbt/ecommerce && dbt run && dbt test && cd ../..

# 5. Run the self-healing agent demo
python agent/inject_test_failure.py   # inject bad data
python agent/orchestrator_v1.py       # agent detects, diagnoses, repairs
python agent/show_metrics.py          # view recovery history
```

---

## CI/CD

Every push to `main` triggers:
1. `pytest tests/test_dag.py` — 9 tests covering DAG config, recovery engine, and GE module imports
2. Agent schema smoke test — confirms Pydantic models import cleanly
3. Branch protection — merges blocked if CI fails

---

## Kubernetes (Architecture)

Local Kubernetes deployment was replaced with Docker Compose for development due to hardware constraints. The full Kubernetes architecture is documented in `/k8s/`:

- `deployment.yaml` — Airflow worker with liveness/readiness probes
- `service.yaml` — ClusterIP service
- `hpa.yaml` — Horizontal Pod Autoscaler (1-5 replicas, 70% CPU threshold)

Deployable to GKE Autopilot in ~20 minutes with free GCP credits.

---

## Resume Bullet

> Built an agentic self-healing ELT pipeline for e-commerce analytics — ingesting 100k+ Olist orders into AWS S3, transforming via dbt (staging/intermediate/mart layers) into revenue and delivery SLA metrics, enforced by Great Expectations quality gates and an LLM-powered recovery agent (OpenRouter free tier) that classifies failures, scores confidence, executes deterministic repairs, and logs every decision to a PostgreSQL audit trail. Orchestrated by Airflow with retries, deployed via Docker Compose, and validated by GitHub Actions CI/CD (9 tests).

---

## Interview Q&A

**Q: What makes this self-healing rather than just fault-tolerant?**
A: It doesn't just retry — it diagnoses *what kind* of failure occurred, selects a targeted repair strategy, executes it, re-validates, and only escalates if repair itself fails. Every decision is logged with confidence score and reasoning.

**Q: Why does the LLM never execute SQL?**
A: Safety by design. The LLM returns a tool name (a Pydantic enum). Deterministic Python maps that to a real function. The LLM has no path to the database — it can only choose from 6 approved actions.

**Q: How do you prove the escalation gate works?**
A: Scenario B uses a poisoned execute_fn that raises AssertionError if called. If the confidence gate failed, the test would crash — not just report the wrong status.

**Q: What would you add next?**
A: LangGraph multi-agent decomposition — separate Failure Analyzer, Repair Planner, and Validation agents with shared PostgreSQL memory. The foundation is already built for it.

---

## Author

**Nandana Nair** — Data Engineering Portfolio 2026

[![GitHub](https://img.shields.io/badge/GitHub-nandana--nairr-black)](https://github.com/nandana-nairr)