"""
Voight-Kampff Validation Framework

Named after the empathy test from Blade Runner, this framework validates
that AI personas genuinely embody their intended identity through
systematic probing and evaluation.

Modules:
- models: Probe, TestSuite, TestReport, EvaluationCriterion
- runner: Test execution engine with async support
- evaluator: Response evaluation logic
- builder: Fluent test suite construction

Usage:
    from persona_forge.voight_kampff import (
        VoightKampffRunner,
        SuiteBuilder,
        build_luna_suite,
    )

    # Build a test suite
    suite = build_luna_suite()

    # Run against a model
    async def my_model(prompt, context, system_prompt):
        return await call_my_llm(prompt)

    runner = VoightKampffRunner(my_model, "my-model-v1")
    report = await runner.run_suite(suite)

    print(report.to_summary())
"""

from .models import (
    # Enums
    ProbeCategory,
    EvaluationMethod,
    ProbeResult,
    # Data classes
    EvaluationCriterion,
    Probe,
    ProbeExecution,
    TestSuite,
    TestReport,
)

from .evaluator import (
    ProbeEvaluator,
    WeightedEvaluator,
)

from .runner import (
    VoightKampffRunner,
    SyncVoightKampffRunner,
)

from .builder import (
    SuiteBuilder,
    build_luna_suite,
    build_minimal_identity_suite,
)


__all__ = [
    # Enums
    "ProbeCategory",
    "EvaluationMethod",
    "ProbeResult",
    # Data models
    "EvaluationCriterion",
    "Probe",
    "ProbeExecution",
    "TestSuite",
    "TestReport",
    # Evaluator
    "ProbeEvaluator",
    "WeightedEvaluator",
    # Runner
    "VoightKampffRunner",
    "SyncVoightKampffRunner",
    # Builder
    "SuiteBuilder",
    "build_luna_suite",
    "build_minimal_identity_suite",
]
