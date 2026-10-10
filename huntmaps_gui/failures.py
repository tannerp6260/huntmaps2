"""Actionable failure summaries without hiding the originating worker error."""


def summarize(lines):
    stages = [line[6:] for line in lines if line.startswith("STAGE ")]
    diagnostics = [
        line
        for line in lines
        if line.startswith(("GUI JOB:", "SCOUT:", "ValueError:", "FileNotFoundError:"))
    ]
    origin = next(
        (line for line in diagnostics if line.startswith("GUI JOB:")),
        diagnostics[-1] if diagnostics else "Job failed.",
    )
    text = origin.lower()
    if any(
        word in text
        for word in ["approval", "plan changed", "allowance", "download budget"]
    ):
        code, action, hint = (
            "review_required",
            "review",
            "Refresh the source plan and review its requests and allowance before starting.",
        )
    elif any(
        word in text
        for word in [
            "eligible observer",
            "separated candidates",
            "output limit",
            "grid exceeds",
            "max_cells",
            "checkpoint is incompatible",
        ]
    ):
        code, action, hint = (
            "settings_required",
            "adjust",
            "Adjust the boundary or sampling settings; preserve this run and use a new name for changed inputs.",
        )
    elif any(
        word in text for word in ["corrupt", "unverified", "changed input", "checksum"]
    ):
        code, action, hint = (
            "source_invalid",
            "review",
            "Review the named source; retain evidence and supply a verified replacement in a new run.",
        )
    elif any(
        word in text
        for word in ["service returned", "approved source acquisition failed"]
    ):
        code, action, hint = (
            "provider_failed",
            "retry",
            "Retry when the source service is available; rejected responses are retained for diagnosis and reacquired. Verified sources are reused.",
        )
    else:
        code, action, hint = (
            "processing_failed",
            "retry",
            "Review the failed stage and retry unchanged work; verified sources and compatible checkpoints are reused.",
        )
    return dict(
        error=origin + " " + hint + " Partial files were retained.",
        failure_code=code,
        failed_stage=stages[-1] if stages else "Starting job",
        recovery_action=action,
    )
