def normalized_owner_ids(pipeline_config: dict | None) -> list[int]:
    """Owner ids of a stored pipeline config, tolerating the legacy shape.

    Configs saved before multi-owner carry ``{"ownerId": 5}``; new ones carry
    ``{"ownerIds": [5, 6]}``. Every consumer of the stored JSONB goes through
    this helper so both shapes keep working without a data migration.

    Args:
        pipeline_config (dict | None): The job's stored pipeline_config JSONB.

    Returns:
        list[int]: Owner user ids ([] when unset).
    """
    if not pipeline_config:
        return []
    ids = pipeline_config.get("ownerIds")
    if ids:
        return list(ids)
    legacy = pipeline_config.get("ownerId")
    return [legacy] if legacy is not None else []
