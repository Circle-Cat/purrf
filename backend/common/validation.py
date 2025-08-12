import json
import os
from jsonschema import validate, Draft7Validator, ValidationError, SchemaError
from backend.common.logger import get_logger

logger = get_logger()


def load_schema(schema_filename: str) -> dict:
    """
    Load a JSON schema from the schemas directory.

    Args:
        schema_filename (str): Name of the JSON schema file.

    Returns:
        dict: Loaded JSON schema as a Python dictionary.

    Raises:
        FileNotFoundError: If the schema file does not exist.
        json.JSONDecodeError: If the file is not valid JSON.

    Example:
        >>> schema = load_schema("calendar_event.schema.json")
    """
    schema_path = os.path.join(os.path.dirname(__file__), "../schemas", schema_filename)
    try:
        with open(schema_path, "r", encoding="utf-8") as f:
            schema = json.load(f)
        return schema
    except FileNotFoundError as e:
        logger.error(f"Schema file not found: {schema_path}")
        raise
    except json.JSONDecodeError as e:
        logger.error(f"Failed to parse schema JSON: {e}")
        raise


def validate_data(data: dict, schema_filename: str) -> None:
    """
    Validate input data against a schema.

    Args:
        data (dict): The JSON-like dictionary to validate.
        schema_filename (str): Filename of the JSON schema to use.

    Raises:
        ValueError: If data is invalid or schema is malformed.
    """
    schema = load_schema(schema_filename)

    try:
        validate(instance=data, schema=schema)
        logger.debug(f"Validation passed for schema: {schema_filename}")
    except ValidationError as ve:
        logger.warning(f"Validation failed: {ve.message}")
        raise ValueError(f"Validation failed: {ve.message}") from ve
    except SchemaError as se:
        logger.error(f"Schema error: {se.message}")
        raise ValueError(f"Schema error: {se.message}") from se
