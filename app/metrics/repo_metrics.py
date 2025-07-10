# app/metrics/repo_metrics.py

from prometheus_client import Histogram

repository_sql_duration = Histogram(
    "repository_sql_duration_seconds",
    "Time spent processing SQL in repository",
    ["repository", "method"]
)
