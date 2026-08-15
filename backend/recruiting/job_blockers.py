from backend.recruiting.pipeline_owners import normalized_owner_ids

# Written as instructions rather than as complaints, because they are read in
# two places: raised as the API's refusal, and rendered beside the Submit
# control as the reason it is disabled.
NO_STAGE = "Add at least one pipeline stage before submitting for review."
NO_RECRUITER = "Add at least one recruiter before submitting for review."


def effective_pipeline_config(job) -> dict:
    """The pipeline config a submission would put live.

    A staged edit is what approval would publish, so it is what submission is
    judged on; the live config applies only when nothing is staged. A staged
    payload carrying no pipeline is an empty config, not a fallback to the
    live one -- approving it would publish no pipeline.

    Args:
        job (JobEntity): The posting.

    Returns:
        dict: The pipeline config to judge, ``{}`` when there is none.
    """
    if job.pending_payload is not None:
        return job.pending_payload.get("pipelineConfig") or {}
    return job.pipeline_config or {}


def submit_blockers(job) -> list[str]:
    """Everything stopping this posting from being submitted for review.

    Returns every blocker rather than the first, so a client can show the
    whole list beside the control instead of revealing them one failed click
    at a time. Owner ids go through ``normalized_owner_ids``, which tolerates
    both the legacy ``ownerId`` and current ``ownerIds`` shapes.

    Args:
        job (JobEntity): The posting.

    Returns:
        list[str]: Blocker messages, empty when the posting can be submitted.
    """
    cfg = effective_pipeline_config(job)
    blockers = []
    if not cfg.get("stages"):
        blockers.append(NO_STAGE)
    if not normalized_owner_ids(cfg):
        blockers.append(NO_RECRUITER)
    return blockers
