import copy
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from match_events import draw_match_event, load_match_events


class MatchEventTests(unittest.TestCase):
    def setUp(self):
        self.events = load_match_events()

    def test_player_lock_excludes_team_events_and_avoids_repeating(self):
        for rank in (1, 15):
            with patch("match_events.random.choice", side_effect=lambda pool: pool[0]) as choice, patch("match_events.random.randint", return_value=rank) as randint:
                result = draw_match_event(self.events, previous_id="match--next-man-up")
            self.assertEqual(result["id"], "match--hot-hand")
            self.assertEqual(result["mode"], "Player Lock")
            self.assertEqual(result["player_rank"], rank)
            self.assertEqual(result["player"], f"#{rank} (rank by overall)")
            self.assertEqual(choice.call_args_list[0].args[0], ["Player Lock", "Full Team"])
            self.assertTrue(all(event["scope"] == "Player" for event in choice.call_args.args[0]))
            randint.assert_called_once_with(1, 15)

    def test_full_team_handles_both_scopes_without_mutating_catalog(self):
        original = copy.deepcopy(self.events)
        for event in self.events:
            with self.subTest(event=event["id"]), patch("match_events.random.choice", side_effect=["Full Team", event]), patch("match_events.random.randint", return_value=15) as randint:
                result = draw_match_event(self.events)
                self.assertEqual(result["mode"], "Full Team")
                if event.get("player_pool") == "two_way":
                    self.assertEqual(sorted(result["two_way_order"]), [1, 2, 3])
                    self.assertIn("Two-way call-up", result["player"])
                else:
                    expected = "#15 (rank by overall)" if event["scope"] == "Player" else None
                    self.assertEqual(result["player"], expected)
                self.assertNotIn("team", result)
                self.assertEqual(randint.call_count, int(event["scope"] == "Player" and event.get("player_pool") != "two_way"))
        self.assertEqual(self.events, original)

    def test_call_up_targets_two_way_player_in_both_modes(self):
        event = next(event for event in self.events if event["id"] == "match--next-man-up")
        for mode in ("Player Lock", "Full Team"):
            with self.subTest(mode=mode), patch("match_events.random.choice", side_effect=[mode, event]), patch("match_events.random.sample", return_value=[3, 1, 2]) as sample, patch("match_events.random.randint") as randint:
                result = draw_match_event(self.events)
            self.assertEqual(result["mode"], mode)
            self.assertEqual(result["two_way_order"], [3, 1, 2])
            self.assertIn("#3 → #1 → #2", result["player"])
            self.assertIsNone(result["player_rank"])
            sample.assert_called_once_with([1, 2, 3], 3)
            randint.assert_not_called()

    def test_empty_pool_and_single_event_fallback(self):
        with self.assertRaisesRegex(ValueError, "No match events"):
            draw_match_event([])
        single = [self.events[2]]
        result = draw_match_event(single, previous_id=single[0]["id"])
        self.assertEqual(result["id"], single[0]["id"])
        self.assertEqual(result["mode"], "Full Team")

    def test_invalid_catalog_is_rejected(self):
        bad_modes = {**self.events[2], "modes": ["Player Lock"]}
        for payload in ({}, [self.events[0], self.events[0]], [bad_modes], [{"id": "missing-fields"}]):
            with self.subTest(payload=payload), tempfile.TemporaryDirectory() as directory:
                path = Path(directory) / "match_events.json"
                path.write_text(json.dumps(payload))
                with self.assertRaises(ValueError):
                    load_match_events(path)
