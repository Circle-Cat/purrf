from unittest import TestCase, main
from unittest.mock import patch, mock_open, MagicMock
from backend.common.json_schema_validator import JsonSchemaValidator


class TestJsonSchemaValidator(TestCase):
    def setUp(self):
        self.mock_logger = MagicMock()
        self.validator = JsonSchemaValidator(logger=self.mock_logger)

    def test_validate_data_success(self):
        with patch("builtins.open", mock_open()), patch("json.load") as mock_json_load:
            mock_json_load.return_value = {
                "type": "object",
                "properties": {
                    "calendar_id": {"type": "string"},
                    "summary": {"type": "string"},
                    "timeZone": {"type": "string"},
                },
                "required": ["calendar_id", "summary", "timeZone"],
            }

            data = {
                "calendar_id": "abc123",
                "summary": "Test Calendar",
                "timeZone": "UTC",
            }

            self.validator.validate_data(data, "calendar_schema.json")
            self.mock_logger.debug.assert_called_with(
                "Validation passed for schema: calendar_schema.json"
            )

    def test_validate_data_missing_required_field(self):
        with patch("builtins.open", mock_open()), patch("json.load") as mock_json_load:
            mock_json_load.return_value = {
                "type": "object",
                "properties": {
                    "calendar_id": {"type": "string"},
                    "summary": {"type": "string"},
                    "timeZone": {"type": "string"},
                },
                "required": ["calendar_id", "summary", "timeZone"],
            }

            invalid_data = {
                "calendar_id": "abc123",
                "summary": "Test Calendar",
            }

            with self.assertRaises(ValueError) as context:
                self.validator.validate_data(invalid_data, "calendar_schema.json")

            self.assertIn("Validation failed", str(context.exception))
            self.mock_logger.warning.assert_called()

    def test_validate_data_malformed_schema(self):
        with patch("builtins.open", mock_open()), patch("json.load") as mock_json_load:
            mock_json_load.return_value = {"type": "invalid_type"}

            data = {"calendar_id": "abc"}

            with self.assertRaises(ValueError) as context:
                self.validator.validate_data(data, "calendar_schema.json")

            self.assertIn("Schema error", str(context.exception))
            self.mock_logger.error.assert_called()

    def test_load_schema_file_not_found(self):
        with patch("builtins.open", side_effect=FileNotFoundError):
            with self.assertRaises(FileNotFoundError):
                self.validator.load_schema("missing_schema.json")
            self.mock_logger.error.assert_called()


if __name__ == "__main__":
    main()
