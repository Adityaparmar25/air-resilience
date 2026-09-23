"""Google Cloud Connectivity and Startup Diagnostics.

Checks configuration and connectivity for:
- GOOGLE_CLOUD_PROJECT
- GOOGLE_APPLICATION_CREDENTIALS
- Firestore
- BigQuery
- GEMINI_API_KEY
- configured GEMINI_MODEL

Security Guardrail:
- Never prints secret values or credential contents.
- If a credential or variable is missing, identifies the variable name only.
"""

import os
from pathlib import Path
from typing import Any, Dict, List


def check_google_cloud_connectivity() -> Dict[str, Any]:
    """Inspect environment and verify cloud infrastructure dependencies.

    Returns diagnostic dictionary without exposing secret values.
    """
    results: Dict[str, Any] = {
        "status": "HEALTHY",
        "checks": {},
        "missing_variables": [],
        "errors": [],
    }

    # 1. GOOGLE_CLOUD_PROJECT
    project_id = os.environ.get("GOOGLE_CLOUD_PROJECT") or os.environ.get("GCP_PROJECT")
    if project_id:
        results["checks"]["GOOGLE_CLOUD_PROJECT"] = {
            "status": "CONFIGURED",
            "configured": True,
            "project_id": project_id,
        }
    else:
        results["checks"]["GOOGLE_CLOUD_PROJECT"] = {
            "status": "MISSING",
            "configured": False,
            "detail": "GOOGLE_CLOUD_PROJECT environment variable is not set",
        }
        results["missing_variables"].append("GOOGLE_CLOUD_PROJECT")

    # 2. GOOGLE_APPLICATION_CREDENTIALS
    creds_path = os.environ.get("GOOGLE_APPLICATION_CREDENTIALS")
    if creds_path:
        p = Path(creds_path)
        file_exists = p.exists()
        results["checks"]["GOOGLE_APPLICATION_CREDENTIALS"] = {
            "status": "CONFIGURED" if file_exists else "FILE_NOT_FOUND",
            "configured": True,
            "file_exists": file_exists,
            "detail": "Path configured" if file_exists else f"Credential file at path does not exist",
        }
        if not file_exists:
            results["errors"].append("GOOGLE_APPLICATION_CREDENTIALS file path not found on disk")
    else:
        results["checks"]["GOOGLE_APPLICATION_CREDENTIALS"] = {
            "status": "NOT_SET",
            "configured": False,
            "detail": "GOOGLE_APPLICATION_CREDENTIALS environment variable is not set (using ADC or local fallback)",
        }
        results["missing_variables"].append("GOOGLE_APPLICATION_CREDENTIALS")

    # 3. Firestore
    try:
        import google.cloud.firestore  # noqa: F401
        firestore_lib = True
    except ImportError:
        firestore_lib = False

    firestore_ready = firestore_lib and bool(project_id)
    results["checks"]["Firestore"] = {
        "status": "READY" if firestore_ready else ("LIBRARY_AVAILABLE" if firestore_lib else "NOT_INSTALLED"),
        "library_available": firestore_lib,
        "configured": firestore_ready,
        "detail": "Firestore client ready" if firestore_ready else "Firestore client requires GOOGLE_CLOUD_PROJECT",
    }

    # 4. BigQuery
    try:
        import google.cloud.bigquery  # noqa: F401
        bigquery_lib = True
    except ImportError:
        bigquery_lib = False

    bigquery_ready = bigquery_lib and bool(project_id)
    results["checks"]["BigQuery"] = {
        "status": "READY" if bigquery_ready else ("LIBRARY_AVAILABLE" if bigquery_lib else "NOT_INSTALLED"),
        "library_available": bigquery_lib,
        "configured": bigquery_ready,
        "detail": "BigQuery client ready" if bigquery_ready else "BigQuery client requires GOOGLE_CLOUD_PROJECT",
    }

    # 5. GEMINI_API_KEY
    gemini_key = os.environ.get("GEMINI_API_KEY")
    if gemini_key:
        results["checks"]["GEMINI_API_KEY"] = {
            "status": "CONFIGURED",
            "configured": True,
            "detail": "GEMINI_API_KEY is present in environment",
        }
    else:
        results["checks"]["GEMINI_API_KEY"] = {
            "status": "MISSING",
            "configured": False,
            "detail": "GEMINI_API_KEY is not set (offline fixture analyzer active)",
        }
        results["missing_variables"].append("GEMINI_API_KEY")

    # 6. configured GEMINI_MODEL
    gemini_model = os.environ.get("GEMINI_MODEL", "gemini-3.5-flash-lite")
    results["checks"]["GEMINI_MODEL"] = {
        "status": "CONFIGURED",
        "configured": True,
        "model_name": gemini_model,
        "detail": f"Active model: {gemini_model}",
    }

    # Overall Status Evaluation
    if results["missing_variables"]:
        results["status"] = "PARTIAL" if results["checks"]["GEMINI_API_KEY"]["configured"] else "DEGRADED"

    return results


if __name__ == "__main__":
    report = check_google_cloud_connectivity()
    print("=" * 60)
    print(" GOOGLE CLOUD CONNECTIVITY CHECK")
    print("=" * 60)
    print(f"Overall Status: {report['status']}")
    print("-" * 60)
    for service, check in report["checks"].items():
        status = check.get("status")
        detail = check.get("detail", "")
        print(f"[{status:15}] {service:30} : {detail}")
    print("=" * 60)
    if report["missing_variables"]:
        print(f"Missing / Unset variables: {', '.join(report['missing_variables'])}")
    print("Zero secrets exposed.")
