import json
import os
import tempfile
import unittest
from unittest.mock import patch

from event_engine import (
    extract_draw_range,
    generate_event_number,
    get_event_intensity,
    infer_intensity,
    load_events,
    requires_player_draw,
    requires_team_draw,
    weighted_random_event,
)


class EventEngineTests(unittest.TestCase):
    def test_load_events_from_path(self):
        payload = {"Regular Season": [{"title": "X", "effect": "Y"}]}
        with tempfile.NamedTemporaryFile("w", delete=False, suffix=".json") as tmp:
            json.dump(payload, tmp)
            tmp_path = tmp.name

        try:
            loaded = load_events(tmp_path)
            self.assertEqual(loaded, payload)
        finally:
            os.remove(tmp_path)

    def test_extract_draw_range(self):
        self.assertEqual(
            extract_draw_range("Draw a number between 1 and 45 for the player."),
            (1, 45),
        )
        self.assertEqual(
            extract_draw_range("draw a number between 45-1 now"),
            (1, 45),
        )
        self.assertIsNone(extract_draw_range("No random draw here"))

    @patch("event_engine.random.randint", return_value=17)
    def test_generate_event_number_from_text(self, _):
        event = {"title": "T", "effect": "Draw a number between 1 and 45 for the player."}
        roll = generate_event_number(event)
        self.assertEqual(roll["value"], 17)
        self.assertEqual(roll["label"], "1-45")

    @patch("event_engine.random.randint", return_value=9)
    def test_generate_event_number_from_metadata(self, _):
        event = {
            "title": "T",
            "effect": "irrelevant",
            "roll_type": "range",
            "roll_min": 5,
            "roll_max": 20,
        }
        roll = generate_event_number(event)
        self.assertEqual(roll["value"], 9)
        self.assertEqual(roll["label"], "5-20")

    def test_requires_team_and_player_draw(self):
        self.assertTrue(requires_team_draw({"effect": "The team drawn receives a boost."}))
        self.assertFalse(requires_team_draw({"effect": "No team mention"}))
        self.assertTrue(requires_player_draw({"effect": "The player drawn is suspended."}))
        self.assertFalse(requires_player_draw({"effect": "No player mention"}))

        # Metadata should override text detection
        self.assertFalse(requires_team_draw({"effect": "team drawn", "requires_team": False}))
        self.assertTrue(requires_player_draw({"effect": "No player mention", "requires_player": True}))

    def test_intensity_uses_metadata_then_fallback(self):
        event_with_metadata = {"title": "X", "effect": "minor", "impact": "High Impact"}
        self.assertEqual(get_event_intensity(event_with_metadata), "High Impact")

        # Invalid metadata should fallback to inference
        fallback_event = {"title": "X", "effect": "The player is out 30 days." , "impact": "Ultra"}
        self.assertEqual(get_event_intensity(fallback_event), infer_intensity(fallback_event))

    @patch("event_engine.random.choices")
    def test_weighted_random_event_uses_recent_penalty(self, mock_choices):
        events = [
            {"title": "A", "effect": "small update"},
            {"title": "B", "effect": "small update"},
        ]
        weights = {"Low Impact": 10, "Medium Impact": 0, "High Impact": 0, "Chaos": 0}
        recent = {"A"}

        mock_choices.return_value = [events[1]]
        result = weighted_random_event(events, weights, recent)

        self.assertEqual(result, events[1])
        args, kwargs = mock_choices.call_args
        self.assertEqual(kwargs["k"], 1)
        self.assertEqual(args[0], events)
        self.assertAlmostEqual(kwargs["weights"][0], 3.5)  # penalized from 10 to 3.5
        self.assertAlmostEqual(kwargs["weights"][1], 10.0)

    @patch("event_engine.random.choice")
    def test_weighted_random_event_falls_back_if_all_weights_zero(self, mock_choice):
        events = [
            {"title": "A", "effect": "small update"},
            {"title": "B", "effect": "small update"},
        ]
        weights = {"Low Impact": 0, "Medium Impact": 0, "High Impact": 0, "Chaos": 0}
        mock_choice.return_value = events[0]

        picked = weighted_random_event(events, weights, set())
        self.assertEqual(picked, events[0])
        mock_choice.assert_called_once_with(events)


if __name__ == "__main__":
    unittest.main()
