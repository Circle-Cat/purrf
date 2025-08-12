from unittest import TestCase, main
from unittest.mock import patch, mock_open
from backend.common.validation import validate_data
import jsonschema


class TestValidateData(TestCase):
    @patch("backend.common.validation.open", new_callable=mock_open)
    @patch("backend.common.validation.json.load")
    def test_validate_data_success(self, mock_json_load, mock_file):
        mock_json_load.return_value = {
            "type": "object",
            "properties": {
                "calendar_id": {"type": "string"},
                "summary": {"type": "string"},
                "description": {"type": "string"},
                "timeZone": {"type": "string"},
            },
            "required": ["calendar_id", "summary", "timeZone"],
        }

        valid_data = {
            "calendar_id": "abc123",
            "summary": "Test Calendar",
            "timeZone": "UTC",
            "description": "optional",
        }

        validate_data(valid_data, "calendar_schema.json")

    @patch("backend.common.validation.open", new_callable=mock_open)
    @patch("backend.common.validation.json.load")
    def test_validate_data_missing_required_field(self, mock_json_load, mock_file):
        schema = {
            "type": "object",
            "properties": {
                "calendar_id": {"type": "string"},
                "summary": {"type": "string"},
                "timeZone": {"type": "string"},
            },
            "required": ["calendar_id", "summary", "timeZone"],
        }
        mock_json_load.return_value = schema

        invalid_data = {
            "calendar_id": "abc123",
            "summary": "Test Calendar",
        }

        with self.assertRaises(ValueError) as context:
            validate_data(invalid_data, "calendar_schema.json")

        self.assertIn("Validation failed", str(context.exception))

    @patch("backend.common.validation.open", new_callable=mock_open)
    @patch("backend.common.validation.json.load")
    def test_validate_data_malformed_schema(self, mock_json_load, mock_file):
        mock_json_load.return_value = {
            "type": "invalid_type",
        }

        data = {"calendar_id": "abc"}

        with self.assertRaises(ValueError) as context:
            validate_data(data, "calendar_schema.json")

        self.assertIn("Schema error", str(context.exception))

    @patch("backend.common.validation.open", side_effect=FileNotFoundError)
    def test_load_schema_file_not_found(self, mock_open):
        with self.assertRaises(FileNotFoundError):
            validate_data({}, "missing_schema.json")


if __name__ == "__main__":
    main()
