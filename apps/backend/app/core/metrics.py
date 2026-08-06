"""
PrintBar Backend — Prometheus Metrics
"""

from prometheus_client import Counter, Gauge, Histogram

# Counters
PRINT_JOBS_TOTAL = Counter("print_jobs_total", "Total print jobs created")
PRINT_JOBS_FAILED = Counter("print_jobs_failed", "Total print jobs failed")
UPLOADS_TOTAL = Counter("uploads_total", "Total files uploaded")

# Gauges
KIOSKS_ONLINE = Gauge("kiosks_online", "Number of currently connected kiosks")
PRINTERS_OFFLINE = Gauge("printers_offline", "Number of currently offline printers")

# Histograms
PRINT_JOB_DURATION = Histogram(
    "print_job_duration_seconds",
    "Time taken to complete a print job",
    buckets=[1, 5, 10, 30, 60, 120, 300, 600],
)
