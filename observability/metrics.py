# observability/metrics.py
"""
Prometheus metrics for Aegis.
All counters use tenant_id as a label for per-tenant dashboards.
"""
from prometheus_client import Counter, Histogram, Gauge

# Recovery actions dispatched (by type and tenant)
recovery_actions_total = Counter(
    "aegis_recovery_actions_total",
    "Number of recovery actions dispatched",
    ["tenant_id", "action", "outcome"],
)

# Compliance violations caught by the gate
compliance_violations_total = Counter(
    "aegis_compliance_violations_total",
    "Number of compliance violations caught by the gate",
    ["tenant_id", "violation_rule"],
)

# Tier-2 Groq calls
tier2_calls_total = Counter(
    "aegis_tier2_calls_total",
    "Number of Tier-2 Groq LLM calls",
    ["tenant_id", "model", "result"],  # result: success|fallback|error
)

# Groq inference latency
groq_latency_seconds = Histogram(
    "aegis_groq_latency_seconds",
    "Groq API call latency in seconds",
    ["tenant_id", "model"],
    buckets=[0.1, 0.25, 0.5, 1.0, 2.0, 3.0, 5.0, 10.0],
)

# Active batch jobs in the queue
active_jobs_gauge = Gauge(
    "aegis_active_jobs",
    "Number of mandate jobs currently in the processing queue",
    ["tenant_id"],
)
