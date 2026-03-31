import unittest

from event_schema import validate_events_schema


class EventSchemaTests(unittest.TestCase):
    def test_valid_minimal_schema(self):
        payload = {
            "Regular Season": [
                {"title": "Team Argument", "effect": "The team drawn has an argument."}
            ]
        }
        validate_events_schema(payload)

    def test_valid_with_optional_metadata(self):
        payload = {
            "Draft Combine": [
                {
                    "title": "Laser Vision",
                    "effect": "Draw a number between 1 and 45.",
                    "impact": "Medium Impact",
                    "requires_team": False,
                    "requires_player": False,
                    "roll_type": "range",
                    "roll_min": 1,
                    "roll_max": 45,
                }
            ]
        }
        validate_events_schema(payload)

    def test_invalid_root_type(self):
        with self.assertRaises(ValueError):
            validate_events_schema([])

    def test_missing_title_or_effect(self):
        with self.assertRaises(ValueError):
            validate_events_schema({"Phase": [{"effect": "x"}]})

        with self.assertRaises(ValueError):
            validate_events_schema({"Phase": [{"title": "x"}]})

    def test_invalid_impact(self):
        with self.assertRaises(ValueError):
            validate_events_schema({"Phase": [{"title": "x", "effect": "y", "impact": "Ultra"}]})

    def test_invalid_bool_fields(self):
        with self.assertRaises(ValueError):
            validate_events_schema({"Phase": [{"title": "x", "effect": "y", "requires_team": "yes"}]})

    def test_roll_bounds_require_range_type(self):
        with self.assertRaises(ValueError):
            validate_events_schema({
                "Phase": [{"title": "x", "effect": "y", "roll_min": 1, "roll_max": 30}]
            })

    def test_range_requires_int_bounds(self):
        with self.assertRaises(ValueError):
            validate_events_schema({
                "Phase": [{"title": "x", "effect": "y", "roll_type": "range", "roll_min": 1, "roll_max": "30"}]
            })

    def test_range_bounds_cannot_match(self):
        with self.assertRaises(ValueError):
            validate_events_schema({
                "Phase": [{"title": "x", "effect": "y", "roll_type": "range", "roll_min": 10, "roll_max": 10}]
            })


if __name__ == "__main__":
    unittest.main()
