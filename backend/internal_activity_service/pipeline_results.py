from backend.common.exceptions import ActivityDataUnavailableError


def checked_pipeline_results(results, expected_count: int) -> list:
    """Return a pipeline's results only if every queued command answered.

    A short reply, or an error object in place of a reply, would otherwise be
    read as zero activity or fail later with an IndexError.

    Args:
        results: What ``pipeline.execute()`` returned.
        expected_count: How many commands were queued on the pipeline.

    Returns:
        list: ``results`` unchanged.

    Raises:
        ActivityDataUnavailableError: The reply does not cover every command.
    """
    if results is None or len(results) != expected_count:
        got = None if results is None else len(results)
        raise ActivityDataUnavailableError(
            f"Redis pipeline returned {got} results for {expected_count} commands."
        )
    for index, result in enumerate(results):
        if isinstance(result, Exception):
            raise ActivityDataUnavailableError(
                f"Redis pipeline command {index} failed: {result!r}"
            )
    return results
