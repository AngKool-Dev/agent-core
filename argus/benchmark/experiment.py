"""Experiment management for benchmark evaluation."""

from typing import Any, Dict, List, Optional

from argus.benchmark.models import (
    ExperimentConfig,
    ExperimentResult,
    TaskRunResult,
)


class ExperimentManager:
    """Manages benchmark experiments."""

    def __init__(self):
        self._experiments: Dict[str, ExperimentResult] = {}
        self._configs: Dict[str, ExperimentConfig] = {}

    def create_experiment(
        self,
        name: str,
        description: str = "",
        benchmark_version: str = "v1.0",
        provider: str = "",
        model: str = "",
        temperature: float = 0.7,
        seed: int = 42,
        repeat_count: int = 1,
        timeout: int = 300,
        features: Optional[Dict[str, bool]] = None,
    ) -> ExperimentConfig:
        """Create a new experiment configuration."""
        config = ExperimentConfig(
            name=name,
            description=description,
            benchmark_version=benchmark_version,
            provider=provider,
            model=model,
            temperature=temperature,
            seed=seed,
            repeat_count=repeat_count,
            timeout=timeout,
            features=features or {},
        )
        self._configs[config.experiment_id] = config
        return config

    def get_experiment(self, experiment_id: str) -> Optional[ExperimentResult]:
        """Get an experiment result by ID."""
        return self._experiments.get(experiment_id)

    def get_config(self, experiment_id: str) -> Optional[ExperimentConfig]:
        """Get an experiment configuration by ID."""
        return self._configs.get(experiment_id)

    def store_result(self, result: ExperimentResult) -> None:
        """Store an experiment result."""
        self._experiments[result.config.experiment_id] = result

    def list_experiments(self) -> List[str]:
        """List all experiment IDs."""
        return list(self._experiments.keys())

    def get_all_results(self) -> List[ExperimentResult]:
        """Get all experiment results."""
        return list(self._experiments.values())

    def delete_experiment(self, experiment_id: str) -> bool:
        """Delete an experiment."""
        if experiment_id in self._experiments:
            del self._experiments[experiment_id]
            self._configs.pop(experiment_id, None)
            return True
        return False

    def create_ablation_experiment(
        self,
        base_config: ExperimentConfig,
        ablation_name: str,
        disabled_features: List[str],
    ) -> ExperimentConfig:
        """
        Create an ablation experiment by disabling specific features.

        This creates a modified copy of the base config with certain features disabled.
        """
        # Copy features and disable specified ones
        new_features = dict(base_config.features)
        for feature in disabled_features:
            new_features[feature] = False

        config = ExperimentConfig(
            name=f"{base_config.name}-{ablation_name}",
            description=f"Ablation: {ablation_name}",
            benchmark_version=base_config.benchmark_version,
            provider=base_config.provider,
            model=base_config.model,
            temperature=base_config.temperature,
            seed=base_config.seed,
            repeat_count=base_config.repeat_count,
            timeout=base_config.timeout,
            features=new_features,
        )
        self._configs[config.experiment_id] = config
        return config

    def create_repeat_experiment(
        self,
        base_config: ExperimentConfig,
        repeat_count: int,
    ) -> ExperimentConfig:
        """Create a repeat experiment with increased repeat count."""
        config = ExperimentConfig(
            name=f"{base_config.name}-repeat-{repeat_count}",
            description=f"Repeat experiment: {repeat_count} runs",
            benchmark_version=base_config.benchmark_version,
            provider=base_config.provider,
            model=base_config.model,
            temperature=base_config.temperature,
            seed=base_config.seed,
            repeat_count=repeat_count,
            timeout=base_config.timeout,
            features=dict(base_config.features),
        )
        self._configs[config.experiment_id] = config
        return config
