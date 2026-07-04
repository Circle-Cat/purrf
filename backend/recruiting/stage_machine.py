from backend.common.recruiting_enums import ApplicationStage

# Global ordering of the configurable pipeline stages. A job's pipeline_config
# selects a subset of these (see configured_stages); APPLIED/REJECTED/HIRED/
# OFFER_DECLINED/BLACKLISTED are not configurable pipeline steps.
PIPELINE_ORDER: list[ApplicationStage] = [
    ApplicationStage.RECRUITER_SCREENING,
    ApplicationStage.BEHAVIORAL,
    ApplicationStage.TECH,
    ApplicationStage.BOARD_REVIEW,
    ApplicationStage.OFFER,
]

# Allowed sub_status values per stage. Stages without an entry (terminal
# stages, or stages outside the configurable pipeline) have no sub-status.
SUB_STATUS_SETS: dict[ApplicationStage, tuple[str, ...]] = {
    ApplicationStage.RECRUITER_SCREENING: ("pending", "in_progress", "evaluated"),
    ApplicationStage.BOARD_REVIEW: ("pending", "in_progress", "evaluated"),
    ApplicationStage.BEHAVIORAL: ("pending", "scheduling", "scheduled", "evaluated"),
    ApplicationStage.TECH: ("pending", "scheduling", "scheduled", "evaluated"),
    ApplicationStage.OFFER: ("pending", "evaluated"),
}


def configured_stages(pipeline_config: dict | None) -> list[ApplicationStage]:
    """The job's selected pipeline stages, in global pipeline order.

    Reads the ``stage`` string of each entry in
    ``pipeline_config["stages"]``, keeps only entries that name a
    ``PIPELINE_ORDER`` member, and returns them sorted by their index in
    ``PIPELINE_ORDER`` (the stored config's own order is untrusted).

    Args:
        pipeline_config (dict | None): The job's stored pipeline
            configuration, e.g. ``{"ownerIds": [...], "stages": [{"stage":
            "behavioral", ...}, ...]}``. Tolerates ``None`` or a config
            missing/empty ``"stages"``.

    Returns:
        list[ApplicationStage]: The configured stages in pipeline order.
            Empty when the config is ``None`` or names no pipeline stages.
    """
    if not pipeline_config:
        return []
    entries = pipeline_config.get("stages") or []
    selected: set[ApplicationStage] = set()
    for entry in entries:
        raw = entry.get("stage") if isinstance(entry, dict) else None
        try:
            stage = ApplicationStage(raw)
        except ValueError:
            continue
        if stage in PIPELINE_ORDER:
            selected.add(stage)
    return [stage for stage in PIPELINE_ORDER if stage in selected]


def rounds_for_stage(pipeline_config: dict | None, stage: ApplicationStage) -> int:
    """The configured round count for one of a job's pipeline stages.

    Args:
        pipeline_config (dict | None): The job's stored pipeline
            configuration (see ``configured_stages``).
        stage (ApplicationStage): The stage to look up.

    Returns:
        int: The stage's configured ``rounds`` value, or ``1`` if the stage
            isn't configured, ``pipeline_config`` is falsy, or the entry's
            ``rounds`` is missing or not a positive integer.
    """
    if not pipeline_config:
        return 1
    entries = pipeline_config.get("stages") or []
    for entry in entries:
        if not isinstance(entry, dict) or entry.get("stage") != stage.value:
            continue
        rounds = entry.get("rounds")
        return rounds if isinstance(rounds, int) and rounds >= 1 else 1
    return 1


def first_stage(pipeline_config: dict | None) -> ApplicationStage:
    """The job's first configured stage.

    Args:
        pipeline_config (dict | None): The job's stored pipeline
            configuration (see ``configured_stages``).

    Returns:
        ApplicationStage: The earliest stage in pipeline order among the
            configured ones, or ``ApplicationStage.RECRUITER_SCREENING``
            when none are configured.
    """
    stages = configured_stages(pipeline_config)
    return stages[0] if stages else ApplicationStage.RECRUITER_SCREENING


def advance_target(
    pipeline_config: dict | None, current: ApplicationStage
) -> ApplicationStage | None:
    """The stage a forward move from ``current`` would land on.

    Args:
        pipeline_config (dict | None): The job's stored pipeline
            configuration (see ``configured_stages``).
        current (ApplicationStage): The application's current stage.

    Returns:
        ApplicationStage | None: The next configured stage after
            ``current``; ``ApplicationStage.HIRED`` when ``current`` is the
            last configured stage; ``None`` when ``current`` is terminal or
            is not one of the job's configured pipeline stages.
    """
    stages = configured_stages(pipeline_config)
    if current not in stages:
        return None
    index = stages.index(current)
    if index + 1 < len(stages):
        return stages[index + 1]
    return ApplicationStage.HIRED


def validate_transition(
    pipeline_config: dict | None, current: ApplicationStage, to: ApplicationStage
) -> None:
    """Validate a proposed stage transition for a job's configured pipeline.

    Args:
        pipeline_config (dict | None): The job's stored pipeline
            configuration (see ``configured_stages``).
        current (ApplicationStage): The application's current stage.
        to (ApplicationStage): The proposed destination stage.

    Returns:
        None

    Raises:
        ValueError: Unless ``to`` is the ``advance_target`` of ``current``,
            or ``to`` is ``ApplicationStage.REJECTED`` and ``current`` is one
            of the job's configured pipeline stages.
    """
    if to == advance_target(pipeline_config, current):
        return
    if to == ApplicationStage.REJECTED and current in configured_stages(
        pipeline_config
    ):
        return
    raise ValueError(
        f"Invalid stage transition from {current!s} to {to!s} for this job's "
        "configured pipeline."
    )


def validate_sub_status(stage: ApplicationStage, sub_status: str) -> None:
    """Validate a sub_status value against the stage's allowed set.

    Args:
        stage (ApplicationStage): The stage the sub_status applies to.
        sub_status (str): The proposed sub_status value.

    Returns:
        None

    Raises:
        ValueError: When ``stage`` has no sub-status set (terminal or
            unknown stage), or ``sub_status`` is not a member of
            ``SUB_STATUS_SETS[stage]``.
    """
    allowed = SUB_STATUS_SETS.get(stage)
    if not allowed:
        raise ValueError(f"Stage {stage!s} has no sub_status values.")
    if sub_status not in allowed:
        raise ValueError(
            f"Invalid sub_status {sub_status!r} for stage {stage!s}; "
            f"expected one of {allowed}."
        )
