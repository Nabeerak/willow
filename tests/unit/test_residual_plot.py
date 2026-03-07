"""
Unit Tests: ResidualPlot — T059

Verifies:
- 5-turn rolling array with oldest eviction
- Weights [0.40, 0.25, 0.15, 0.12, 0.08] sum to 1.0
- weighted_average_m calculation
- Empty and partial-fill behaviour
"""

import pytest

from src.core.residual_plot import ResidualPlot


class TestResidualPlotWeights:
    """Weights must be normalised to 1.0."""

    def test_weights_sum_to_one(self):
        """The five weights must sum exactly to 1.0."""
        from src.core.residual_plot import RECENCY_WEIGHTS
        total = sum(RECENCY_WEIGHTS)
        assert abs(total - 1.0) < 1e-9, f"Weights sum to {total}, expected 1.0"

    def test_weights_length(self):
        """Exactly 5 weights defined."""
        from src.core.residual_plot import RECENCY_WEIGHTS
        assert len(RECENCY_WEIGHTS) == 5

    def test_most_recent_weight_highest(self):
        """Most-recent turn has the highest weight (index 0 = newest)."""
        from src.core.residual_plot import RECENCY_WEIGHTS
        assert RECENCY_WEIGHTS[0] == max(RECENCY_WEIGHTS)


class TestResidualPlotRolling:
    """Rolling 5-turn array evicts oldest entries."""

    def test_empty_plot_weighted_average_zero(self):
        """No turns → weighted_average_m is 0.0."""
        plot = ResidualPlot()
        assert plot.weighted_average_m == 0.0

    def test_single_turn(self):
        """One turn: weighted average equals that turn's value."""
        plot = ResidualPlot()
        plot.add_turn(2.0)
        # Only one weight active: the most-recent weight (0.40)
        # BUT weighted_average_m is normalised over filled entries.
        # After 1 turn: average = 2.0 * weights[0] / weights[0] = 2.0
        assert abs(plot.weighted_average_m - 2.0) < 1e-6

    def test_five_turns_fills_array(self):
        """After 5 turns the array is full."""
        plot = ResidualPlot()
        for v in [1.0, 1.0, 1.0, 1.0, 1.0]:
            plot.add_turn(v)
        assert len(plot.m_values) == 5

    def test_sixth_turn_evicts_oldest(self):
        """6th turn must evict the oldest entry, keeping only 5."""
        plot = ResidualPlot()
        for v in [0.0, 0.0, 0.0, 0.0, 0.0]:
            plot.add_turn(v)
        plot.add_turn(1.0)
        assert len(plot.m_values) == 5

    def test_uniform_values_weighted_average(self):
        """If all 5 turns have the same value, weighted_average_m equals that value."""
        plot = ResidualPlot()
        for _ in range(5):
            plot.add_turn(1.5)
        assert abs(plot.weighted_average_m - 1.5) < 1e-6

    def test_recent_turn_dominates_average(self):
        """A large most-recent value pulls the average significantly."""
        plot = ResidualPlot()
        # 4 turns of 0.0, then a capped positive value
        for _ in range(4):
            plot.add_turn(0.0)
        plot.add_turn(2.0)  # max allowed by ±2.0 cap
        # weighted_average_m should be > 0 and influenced primarily by 2.0
        assert plot.weighted_average_m > 0.0

    def test_to_dict_returns_expected_keys(self):
        """to_dict() provides m_values and weighted_average_m."""
        plot = ResidualPlot()
        plot.add_turn(1.0)
        d = plot.to_dict()
        assert "m_values" in d
        assert "weighted_average_m" in d


class TestResidualPlotNegativeValues:
    """Negative m values correctly decrease weighted average."""

    def test_negative_turns_produce_negative_average(self):
        """All-negative turns → weighted average is negative."""
        plot = ResidualPlot()
        for _ in range(5):
            plot.add_turn(-1.0)
        assert plot.weighted_average_m < 0.0

    def test_mixed_positive_negative(self):
        """Mixed turns produce average between min and max."""
        plot = ResidualPlot()
        for v in [2.0, -2.0, 2.0, -2.0, 2.0]:
            plot.add_turn(v)
        avg = plot.weighted_average_m
        assert -2.0 <= avg <= 2.0
