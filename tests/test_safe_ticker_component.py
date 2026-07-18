"""Tests for the ticker path-component validator that blocks directory traversal."""

import os
import unittest

import pytest

from tradingagents.dataflows.utils import safe_ticker_component, sanitize_ticker_component


@pytest.mark.unit
class TestSafeTickerComponent(unittest.TestCase):
    def test_accepts_common_ticker_formats(self):
        for ticker in ("AAPL", "BRK-B", "BRK.A", "0700.HK", "7203.T", "BHP.AX", "^GSPC"):
            self.assertEqual(safe_ticker_component(ticker), ticker)

    def test_rejects_path_separators(self):
        for bad in (".", "..", "../etc", "a/b", "a\\b", "/abs", "..\\..\\x"):
            with self.assertRaises(ValueError):
                safe_ticker_component(bad)

    def test_rejects_null_byte_and_whitespace(self):
        for bad in ("AAP L", "AAPL\x00", "AAPL\n", "\tAAPL"):
            with self.assertRaises(ValueError):
                safe_ticker_component(bad)

    def test_rejects_empty_or_non_string(self):
        for bad in ("", None, 123, b"AAPL"):
            with self.assertRaises(ValueError):
                safe_ticker_component(bad)

    def test_rejects_overlong_input(self):
        with self.assertRaises(ValueError):
            safe_ticker_component("A" * 33)

    def test_rejects_dot_only_values(self):
        # '.' and '..' pass the regex but traverse when used as a path
        # component (e.g. ``Path(results_dir) / ticker / "logs"``).
        for bad in (".", "..", "...", "...."):
            with self.assertRaises(ValueError):
                safe_ticker_component(bad)

    def test_traversal_string_does_not_escape_join(self):
        """Sanity: sanitized values stay within base when joined."""
        base = os.path.realpath("/tmp/cache")
        ticker = safe_ticker_component("AAPL")
        joined = os.path.realpath(os.path.join(base, f"{ticker}.csv"))
        self.assertTrue(joined.startswith(base + os.sep))


@pytest.mark.unit
class TestSanitizeTickerComponent(unittest.TestCase):
    def test_returns_valid_tickers_unchanged(self):
        for ticker in ("AAPL", "BRK-B", "BRK.A", "^GSPC"):
            self.assertEqual(sanitize_ticker_component(ticker), ticker)

    def test_returns_none_for_feed_symbols_unusable_as_paths(self):
        # Yahoo relatedTickers can emit futures/FX symbols like these; they
        # must be skipped by ingestion, never abort a research run.
        for bad in ("CL=F", "GC=F", "EURUSD=X", "", None, "..", "a/b", "A" * 33):
            self.assertIsNone(sanitize_ticker_component(bad))


if __name__ == "__main__":
    unittest.main()
