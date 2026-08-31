"""Statistical analysis for benchmark results."""

import math
import random
from typing import Dict, List, Optional, Tuple


class StatisticsError(Exception):
    """Error in statistical calculations."""
    pass


class BenchmarkStatistics:
    """Statistical functions for benchmark analysis."""

    @staticmethod
    def mean(values: List[float]) -> float:
        """Calculate arithmetic mean."""
        if not values:
            return 0.0
        return sum(values) / len(values)

    @staticmethod
    def median(values: List[float]) -> float:
        """Calculate median."""
        if not values:
            return 0.0
        sorted_vals = sorted(values)
        n = len(sorted_vals)
        mid = n // 2
        if n % 2 == 0:
            return (sorted_vals[mid - 1] + sorted_vals[mid]) / 2
        return sorted_vals[mid]

    @staticmethod
    def min_value(values: List[float]) -> float:
        """Get minimum value."""
        if not values:
            return 0.0
        return min(values)

    @staticmethod
    def max_value(values: List[float]) -> float:
        """Get maximum value."""
        if not values:
            return 0.0
        return max(values)

    @staticmethod
    def variance(values: List[float]) -> float:
        """Calculate population variance."""
        if len(values) < 2:
            return 0.0
        m = sum(values) / len(values)
        return sum((x - m) ** 2 for x in values) / len(values)

    @staticmethod
    def std_dev(values: List[float]) -> float:
        """Calculate population standard deviation."""
        return math.sqrt(BenchmarkStatistics.variance(values))

    @staticmethod
    def percentile(values: List[float], p: float) -> float:
        """Calculate the p-th percentile (0-100)."""
        if not values:
            return 0.0
        sorted_vals = sorted(values)
        n = len(sorted_vals)
        k = (p / 100) * (n - 1)
        f = math.floor(k)
        c = math.ceil(k)
        if f == c:
            return sorted_vals[int(k)]
        return sorted_vals[f] * (c - k) + sorted_vals[c] * (k - f)

    @staticmethod
    def percentiles(values: List[float], ps: List[float]) -> Dict[float, float]:
        """Calculate multiple percentiles."""
        return {p: BenchmarkStatistics.percentile(values, p) for p in ps}

    @staticmethod
    def confidence_interval_binary(
        successes: int,
        total: int,
        confidence: float = 0.95,
    ) -> Tuple[float, float]:
        """
        Calculate Wilson score confidence interval for binary outcomes.

        This is more appropriate than normal approximation for small samples
        or extreme probabilities.
        """
        if total == 0:
            return (0.0, 0.0)

        z = 1.96 if confidence == 0.95 else 2.576  # 95% or 99%
        p_hat = successes / total

        denominator = 1 + z * z / total
        center = (p_hat + z * z / (2 * total)) / denominator
        margin = z * math.sqrt(
            (p_hat * (1 - p_hat) + z * z / (4 * total)) / total
        ) / denominator

        return (max(0, center - margin), min(1, center + margin))

    @staticmethod
    def confidence_interval_mean(
        values: List[float],
        confidence: float = 0.95,
    ) -> Tuple[float, float]:
        """Calculate confidence interval for mean using normal approximation."""
        if len(values) < 2:
            return (0.0, 0.0)

        m = sum(values) / len(values)
        s = math.sqrt(sum((x - m) ** 2 for x in values) / len(values))
        n = len(values)

        # Use z=1.96 for 95% CI (reasonable for n >= 30)
        # For smaller samples, t-distribution would be more appropriate
        z = 1.96 if confidence == 0.95 else 2.576
        margin = z * s / math.sqrt(n)

        return (m - margin, m + margin)

    @staticmethod
    def bootstrap_confidence_interval(
        values: List[float],
        statistic_fn,
        n_bootstrap: int = 1000,
        confidence: float = 0.95,
        seed: int = 42,
    ) -> Tuple[float, float]:
        """
        Calculate bootstrap confidence interval for any statistic.

        Uses deterministic seed for reproducibility.
        """
        if not values:
            return (0.0, 0.0)

        rng = random.Random(seed)
        bootstrap_stats = []

        for _ in range(n_bootstrap):
            sample = [values[rng.randint(0, len(values) - 1)] for _ in range(len(values))]
            bootstrap_stats.append(statistic_fn(sample))

        bootstrap_stats.sort()
        lower_idx = int((1 - confidence) / 2 * n_bootstrap)
        upper_idx = int((1 + confidence) / 2 * n_bootstrap)

        return (bootstrap_stats[lower_idx], bootstrap_stats[upper_idx])

    @staticmethod
    def coefficient_of_variation(values: List[float]) -> float:
        """Calculate coefficient of variation (std_dev / mean)."""
        m = BenchmarkStatistics.mean(values)
        if m == 0:
            return 0.0
        return BenchmarkStatistics.std_dev(values) / m

    @staticmethod
    def summarize(values: List[float]) -> Dict[str, float]:
        """Generate a full statistical summary."""
        if not values:
            return {
                "count": 0,
                "mean": 0.0,
                "median": 0.0,
                "min": 0.0,
                "max": 0.0,
                "std_dev": 0.0,
                "variance": 0.0,
                "p50": 0.0,
                "p75": 0.0,
                "p90": 0.0,
                "p95": 0.0,
                "p99": 0.0,
                "cv": 0.0,
            }

        return {
            "count": len(values),
            "mean": BenchmarkStatistics.mean(values),
            "median": BenchmarkStatistics.median(values),
            "min": BenchmarkStatistics.min_value(values),
            "max": BenchmarkStatistics.max_value(values),
            "std_dev": BenchmarkStatistics.std_dev(values),
            "variance": BenchmarkStatistics.variance(values),
            "p50": BenchmarkStatistics.percentile(values, 50),
            "p75": BenchmarkStatistics.percentile(values, 75),
            "p90": BenchmarkStatistics.percentile(values, 90),
            "p95": BenchmarkStatistics.percentile(values, 95),
            "p99": BenchmarkStatistics.percentile(values, 99),
            "cv": BenchmarkStatistics.coefficient_of_variation(values),
        }

    @staticmethod
    def compare_proportions(
        successes_a: int,
        total_a: int,
        successes_b: int,
        total_b: int,
    ) -> Dict[str, float]:
        """
        Compare two proportions using normal approximation.

        Returns the z-score and approximate p-value.
        """
        if total_a == 0 or total_b == 0:
            return {"z_score": 0.0, "p_value": 1.0, "significant": False}

        p_a = successes_a / total_a
        p_b = successes_b / total_b
        p_pool = (successes_a + successes_b) / (total_a + total_b)

        se = math.sqrt(p_pool * (1 - p_pool) * (1 / total_a + 1 / total_b))
        if se == 0:
            return {"z_score": 0.0, "p_value": 1.0, "significant": False}

        z = (p_a - p_b) / se
        # Approximate p-value using normal distribution
        p_value = 2 * (1 - _normal_cdf(abs(z)))

        return {
            "z_score": z,
            "p_value": p_value,
            "significant": p_value < 0.05,
        }


def _normal_cdf(x: float) -> float:
    """Approximate the cumulative distribution function of standard normal."""
    # Using the error function approximation
    return 0.5 * (1 + math.erf(x / math.sqrt(2)))
