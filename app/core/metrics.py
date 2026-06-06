"""Prometheus metrics for observability.

Exposes request counts, latency histograms, pipeline quality metrics,
and system info. Scraped via GET /metrics.
"""

from prometheus_client import Counter, Histogram, Info

# Request metrics
REQUEST_COUNT = Counter(
    'llm_ops_requests_total',
    'Total HTTP requests',
    ['endpoint', 'method', 'status'],
)
REQUEST_LATENCY = Histogram(
    'llm_ops_request_duration_seconds',
    'Request latency in seconds',
    ['endpoint'],
)

# RAG pipeline metrics
RETRIEVAL_LATENCY = Histogram('llm_ops_retrieval_duration_seconds', 'Retrieval stage latency')
GENERATION_LATENCY = Histogram('llm_ops_generation_duration_seconds', 'Generation stage latency')
RETRIEVAL_RESULTS = Histogram('llm_ops_retrieval_results_count', 'Number of chunks retrieved per query')

# Quality metrics
CONFIDENCE_SCORE = Histogram('llm_ops_confidence_score', 'Response confidence distribution')
POLICY_ACTION = Counter('llm_ops_policy_action_total', 'Policy action counts', ['action'])
GROUNDING_RATIO = Histogram('llm_ops_grounding_ratio', 'Verification support ratio distribution')

# System info
BUILD_INFO = Info('llm_ops_build', 'Build and deployment information')
