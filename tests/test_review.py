"""Tests for ARGUS Review Engine."""

import json
import pytest

from argus.review import (
    CriterionResult,
    CriterionStatus,
    DiffAnalyzer,
    DiffQualityCriterion,
    EvidenceCollector,
    FindingCategory,
    RegressionAnalyzer,
    RegressionCriterion,
    RequirementAnalyzer,
    RequirementCriterion,
    ReviewEngine,
    ReviewEvidence,
    ReviewFinding,
    ReviewResult,
    ReviewSeverity,
    ReviewStatus,
    ReviewCriterion,
    ScopeCriterion,
    SecurityAnalyzer,
    SecurityCriterion,
    TestDeletionCriterion,
    VerificationCriterion,
    run_review,
)


class TestReviewModels:
    def test_review_finding_creation(self):
        finding = ReviewFinding(
            category=FindingCategory.SECURITY,
            severity=ReviewSeverity.CRITICAL,
            summary="Test finding",
            detail="Detail",
        )
        assert finding.category == FindingCategory.SECURITY
        assert finding.severity == ReviewSeverity.CRITICAL

    def test_review_finding_to_dict(self):
        finding = ReviewFinding(
            category=FindingCategory.QUALITY,
            severity=ReviewSeverity.LOW,
            summary="Test",
        )
        d = finding.to_dict()
        assert d["category"] == "quality"
        assert d["severity"] == "low"

    def test_criterion_result_creation(self):
        result = CriterionResult(
            criterion="test",
            status=CriterionStatus.PASS,
            summary="Passed",
        )
        assert result.status == CriterionStatus.PASS
        assert result.confidence == 1.0

    def test_review_result_creation(self):
        result = ReviewResult(
            status=ReviewStatus.PASS,
            task="Test task",
        )
        assert result.status == ReviewStatus.PASS
        assert result.review_id is not None

    def test_review_result_has_critical_findings(self):
        result = ReviewResult(
            status=ReviewStatus.FAIL,
            findings=[
                ReviewFinding(
                    category=FindingCategory.SECURITY,
                    severity=ReviewSeverity.CRITICAL,
                    summary="Critical",
                )
            ],
        )
        assert result.has_critical_findings is True

    def test_review_result_has_no_critical_findings(self):
        result = ReviewResult(
            status=ReviewStatus.PASS,
            findings=[
                ReviewFinding(
                    category=FindingCategory.QUALITY,
                    severity=ReviewSeverity.LOW,
                    summary="Low",
                )
            ],
        )
        assert result.has_critical_findings is False

    def test_review_result_to_dict(self):
        result = ReviewResult(
            status=ReviewStatus.PASS,
            task="Test",
        )
        d = result.to_dict()
        assert d["status"] == "pass"
        assert d["task"] == "Test"

    def test_review_result_to_json(self):
        result = ReviewResult(
            status=ReviewStatus.PASS,
        )
        j = result.to_json()
        d = json.loads(j)
        assert d["status"] == "pass"

    def test_evidence_creation(self):
        evidence = ReviewEvidence(
            source="test",
            evidence_type="test_type",
            data={"key": "value"},
        )
        assert evidence.source == "test"
        assert evidence.evidence_type == "test_type"

    def test_evidence_collection(self):
        from argus.review.models import EvidenceCollection

        collection = EvidenceCollection()
        evidence = ReviewEvidence(
            source="test",
            evidence_type="test_type",
            data={},
        )
        collection.add(evidence)

        assert len(collection.evidence) == 1
        assert collection.has_type("test_type") is True
        assert collection.has_source("test") is True


class TestEvidenceCollector:
    def test_add_evidence(self):
        collector = EvidenceCollector()
        collector.add_evidence(
            source="test",
            evidence_type="test_type",
            data={"key": "value"},
        )
        assert collector.has_evidence_type("test_type")

    def test_add_requirements(self):
        collector = EvidenceCollector()
        collector.add_requirements([
            {"description": "Req 1", "status": "satisfied"},
            {"description": "Req 2", "status": "unsatisfied"},
        ])
        assert collector.has_evidence_type("requirement")

    def test_add_verification_result(self):
        collector = EvidenceCollector()
        collector.add_verification_result(
            passed=True,
            total=10,
        )
        assert collector.has_evidence_type("verification_result")

    def test_add_regression_result(self):
        collector = EvidenceCollector()
        collector.add_regression_result(
            has_regression=False,
            baseline_available=True,
        )
        assert collector.has_evidence_type("regression_result")

    def test_add_security_event(self):
        collector = EvidenceCollector()
        collector.add_security_event({
            "type": "deny",
            "capability": "test",
        })
        assert collector.has_evidence_type("security_event")

    def test_add_git_diff(self):
        collector = EvidenceCollector()
        collector.add_git_diff({
            "files_changed": ["file1.py"],
            "lines_added": 10,
        })
        assert collector.has_evidence_type("git_diff")

    def test_add_scope_check(self):
        collector = EvidenceCollector()
        collector.add_scope_check(
            in_scope=[{"file": "a.py"}],
            out_of_scope=[{"file": "b.py"}],
        )
        assert collector.has_evidence_type("scope_check")

    def test_summary(self):
        collector = EvidenceCollector()
        collector.add_evidence("test", "type1", {})
        collector.add_evidence("test", "type2", {})

        summary = collector.summary()
        assert summary["total_evidence"] == 2
        assert len(summary["types"]) == 2


class TestRequirementCriterion:
    def test_all_satisfied(self):
        criterion = RequirementCriterion()
        collector = EvidenceCollector()
        collector.add_requirements([
            {"description": "Req 1", "status": "satisfied"},
            {"description": "Req 2", "status": "satisfied"},
        ])

        result = criterion.evaluate(collector.collection)
        assert result.status == CriterionStatus.PASS

    def test_partially_satisfied(self):
        criterion = RequirementCriterion()
        collector = EvidenceCollector()
        collector.add_requirements([
            {"description": "Req 1", "status": "satisfied"},
            {"description": "Req 2", "status": "unsatisfied"},
        ])

        result = criterion.evaluate(collector.collection)
        assert result.status == CriterionStatus.WARNING

    def test_none_satisfied(self):
        criterion = RequirementCriterion()
        collector = EvidenceCollector()
        collector.add_requirements([
            {"description": "Req 1", "status": "unsatisfied"},
            {"description": "Req 2", "status": "unsatisfied"},
        ])

        result = criterion.evaluate(collector.collection)
        assert result.status == CriterionStatus.FAIL

    def test_no_requirements(self):
        criterion = RequirementCriterion()
        collector = EvidenceCollector()

        result = criterion.evaluate(collector.collection)
        assert result.status == CriterionStatus.INCONCLUSIVE


class TestVerificationCriterion:
    def test_passed(self):
        criterion = VerificationCriterion()
        collector = EvidenceCollector()
        collector.add_verification_result(passed=True, total=10)

        result = criterion.evaluate(collector.collection)
        assert result.status == CriterionStatus.PASS

    def test_failed(self):
        criterion = VerificationCriterion()
        collector = EvidenceCollector()
        collector.add_verification_result(
            passed=False,
            total=10,
            failures=[{"name": "test1", "message": "Failed"}],
        )

        result = criterion.evaluate(collector.collection)
        assert result.status == CriterionStatus.FAIL

    def test_no_verification(self):
        criterion = VerificationCriterion()
        collector = EvidenceCollector()

        result = criterion.evaluate(collector.collection)
        assert result.status == CriterionStatus.INCONCLUSIVE


class TestRegressionCriterion:
    def test_no_regression(self):
        criterion = RegressionCriterion()
        collector = EvidenceCollector()
        collector.add_regression_result(
            has_regression=False,
            baseline_available=True,
        )

        result = criterion.evaluate(collector.collection)
        assert result.status == CriterionStatus.PASS

    def test_regression_detected(self):
        criterion = RegressionCriterion()
        collector = EvidenceCollector()
        collector.add_regression_result(
            has_regression=True,
            new_failures=[{"name": "test1"}],
            baseline_available=True,
        )

        result = criterion.evaluate(collector.collection)
        assert result.status == CriterionStatus.FAIL

    def test_no_baseline(self):
        criterion = RegressionCriterion()
        collector = EvidenceCollector()
        collector.add_regression_result(
            has_regression=False,
            baseline_available=False,
        )

        result = criterion.evaluate(collector.collection)
        assert result.status == CriterionStatus.INCONCLUSIVE


class TestSecurityCriterion:
    def test_no_issues(self):
        criterion = SecurityCriterion()
        collector = EvidenceCollector()

        result = criterion.evaluate(collector.collection)
        assert result.status == CriterionStatus.PASS

    def test_security_denied(self):
        criterion = SecurityCriterion()
        collector = EvidenceCollector()
        collector.add_security_event({
            "type": "deny",
            "capability": "shell.execute",
            "decision": "deny",
            "reason": "Dangerous",
        })

        result = criterion.evaluate(collector.collection)
        assert result.status == CriterionStatus.FAIL
        assert len(result.findings) > 0

    def test_injection_detected(self):
        criterion = SecurityCriterion()
        collector = EvidenceCollector()
        collector.add_security_event({
            "type": "injection_detected",
            "injection_type": "instruction_override",
        })

        result = criterion.evaluate(collector.collection)
        assert result.status == CriterionStatus.FAIL

    def test_audit_violation(self):
        criterion = SecurityCriterion()
        collector = EvidenceCollector()
        collector.add_audit_event({
            "event_type": "policy_violation",
            "reason": "Violation",
        })

        result = criterion.evaluate(collector.collection)
        assert result.status == CriterionStatus.FAIL


class TestDiffQualityCriterion:
    def test_clean_diff(self):
        criterion = DiffQualityCriterion()
        collector = EvidenceCollector()
        collector.add_git_diff({
            "files_changed": ["file1.py"],
            "lines_added": 10,
            "lines_removed": 5,
        })

        result = criterion.evaluate(collector.collection)
        assert result.status == CriterionStatus.PASS

    def test_debug_prints(self):
        criterion = DiffQualityCriterion()
        collector = EvidenceCollector()
        collector.add_git_diff({
            "files_changed": ["file1.py"],
            "has_debug_prints": True,
            "debug_print_files": ["file1.py"],
        })

        result = criterion.evaluate(collector.collection)
        assert result.status == CriterionStatus.WARNING

    def test_hardcoded_secrets(self):
        criterion = DiffQualityCriterion()
        collector = EvidenceCollector()
        collector.add_git_diff({
            "files_changed": ["file1.py"],
            "has_hardcoded_secrets": True,
            "secret_files": [("file1.py", "API key")],
        })

        result = criterion.evaluate(collector.collection)
        assert result.status == CriterionStatus.FAIL

    def test_large_diff(self):
        criterion = DiffQualityCriterion()
        collector = EvidenceCollector()
        collector.add_git_diff({
            "files_changed": ["file1.py"] * 50,
            "lines_added": 600,
            "lines_removed": 0,
        })

        result = criterion.evaluate(collector.collection)
        assert result.status == CriterionStatus.WARNING

    def test_no_diff(self):
        criterion = DiffQualityCriterion()
        collector = EvidenceCollector()

        result = criterion.evaluate(collector.collection)
        assert result.status == CriterionStatus.INCONCLUSIVE


class TestScopeCriterion:
    def test_in_scope(self):
        criterion = ScopeCriterion()
        collector = EvidenceCollector()
        collector.add_scope_check(
            in_scope=[{"file": "auth.py"}],
            out_of_scope=[],
        )

        result = criterion.evaluate(collector.collection)
        assert result.status == CriterionStatus.PASS

    def test_out_of_scope(self):
        criterion = ScopeCriterion()
        collector = EvidenceCollector()
        collector.add_scope_check(
            in_scope=[{"file": "auth.py"}],
            out_of_scope=[{"file": "billing.py"}],
        )

        result = criterion.evaluate(collector.collection)
        assert result.status == CriterionStatus.WARNING

    def test_no_scope_check(self):
        criterion = ScopeCriterion()
        collector = EvidenceCollector()

        result = criterion.evaluate(collector.collection)
        assert result.status == CriterionStatus.INCONCLUSIVE


class TestTestDeletionCriterion:
    def test_no_deletion(self):
        criterion = TestDeletionCriterion()
        collector = EvidenceCollector()

        result = criterion.evaluate(collector.collection)
        assert result.status == CriterionStatus.PASS

    def test_test_deleted(self):
        criterion = TestDeletionCriterion()
        collector = EvidenceCollector()
        collector.add_git_diff({
            "deleted_tests": [{"name": "test_login"}],
        })

        result = criterion.evaluate(collector.collection)
        assert result.status == CriterionStatus.FAIL

    def test_assertion_weakened(self):
        criterion = TestDeletionCriterion()
        collector = EvidenceCollector()
        collector.add_git_diff({
            "weakened_assertions": [{"test": "test_login"}],
        })

        result = criterion.evaluate(collector.collection)
        assert result.status == CriterionStatus.FAIL


class TestReviewEngine:
    def test_pass_review(self):
        engine = ReviewEngine()
        collector = EvidenceCollector()
        collector.add_requirements([
            {"description": "Req 1", "status": "satisfied"},
        ])
        collector.add_verification_result(passed=True, total=5)
        collector.add_regression_result(has_regression=False, baseline_available=True)
        collector.add_git_diff({
            "files_changed": ["file1.py"],
            "lines_added": 10,
            "lines_removed": 5,
        })
        collector.add_scope_check(
            in_scope=[{"file": "file1.py"}],
            out_of_scope=[],
        )

        result = engine.review(collector.collection)
        assert result.status == ReviewStatus.PASS

    def test_fail_review(self):
        engine = ReviewEngine()
        collector = EvidenceCollector()
        collector.add_security_event({
            "type": "deny",
            "decision": "deny",
        })

        result = engine.review(collector.collection)
        assert result.status in (ReviewStatus.FAIL, ReviewStatus.BLOCKED)

    def test_blocked_review(self):
        engine = ReviewEngine()
        collector = EvidenceCollector()
        collector.add_git_diff({
            "has_hardcoded_secrets": True,
            "secret_files": [("file.py", "API key")],
        })

        result = engine.review(collector.collection)
        assert result.status == ReviewStatus.BLOCKED

    def test_inconclusive_review(self):
        engine = ReviewEngine()
        # Use only criteria that will be inconclusive with empty evidence
        from argus.review.criteria import RequirementCriterion
        collector = EvidenceCollector()
        engine._criteria = [RequirementCriterion()]

        result = engine.review(collector.collection)
        assert result.status == ReviewStatus.INCONCLUSIVE

    def test_add_remove_criterion(self):
        engine = ReviewEngine()
        initial_count = len(engine.criteria)

        criterion = RequirementCriterion()
        engine.add_criterion(criterion)
        assert len(engine.criteria) == initial_count + 1

        engine.remove_criterion("requirement_satisfaction")
        assert len(engine.criteria) == initial_count

    def test_review_with_task(self):
        engine = ReviewEngine()
        collector = EvidenceCollector()

        result = engine.review(collector.collection, task="Test task")
        assert result.task == "Test task"

    def test_review_duration(self):
        engine = ReviewEngine()
        collector = EvidenceCollector()

        result = engine.review(collector.collection)
        assert result.duration is not None
        assert result.duration >= 0


class TestReviewAggregation:
    def test_critical_finding_blocks(self):
        from argus.review.criteria import ReviewCriterion

        class CriticalCriterion(ReviewCriterion):
            def __init__(self):
                super().__init__("critical_test", FindingCategory.SECURITY, ReviewSeverity.CRITICAL)

            def evaluate(self, evidence):
                return self._fail(
                    "Critical failure",
                    findings=[ReviewFinding(
                        category=FindingCategory.SECURITY,
                        severity=ReviewSeverity.CRITICAL,
                        summary="Critical",
                    )],
                )

        engine = ReviewEngine(criteria=[CriticalCriterion()])
        collector = EvidenceCollector()

        result = engine.review(collector.collection)
        assert result.status == ReviewStatus.BLOCKED

    def test_high_failure_fails(self):
        from argus.review.criteria import ReviewCriterion

        class HighFailCriterion(ReviewCriterion):
            def __init__(self):
                super().__init__("high_fail", FindingCategory.REQUIREMENT, ReviewSeverity.HIGH)

            def evaluate(self, evidence):
                return self._fail("High failure")

        engine = ReviewEngine(criteria=[HighFailCriterion()])
        collector = EvidenceCollector()

        result = engine.review(collector.collection)
        assert result.status == ReviewStatus.FAIL

    def test_warnings_only(self):
        from argus.review.criteria import ReviewCriterion

        class WarningCriterion(ReviewCriterion):
            def __init__(self):
                super().__init__("warning_test", FindingCategory.QUALITY, ReviewSeverity.LOW)

            def evaluate(self, evidence):
                return self._warning("Warning")

        engine = ReviewEngine(criteria=[WarningCriterion()])
        collector = EvidenceCollector()

        result = engine.review(collector.collection)
        assert result.status == ReviewStatus.PASS_WITH_WARNINGS


class TestDiffAnalyzer:
    def test_analyze_clean_diff(self):
        analyzer = DiffAnalyzer()
        diff_data = {
            "files_changed": ["file1.py"],
            "lines_added": 10,
            "lines_removed": 5,
        }

        findings = analyzer.analyze(diff_data)
        assert len(findings) == 0

    def test_analyze_debug_prints(self):
        analyzer = DiffAnalyzer()
        diff_data = {
            "files_changed": ["file1.py"],
            "has_debug_prints": True,
            "debug_print_files": ["file1.py"],
        }

        findings = analyzer.analyze(diff_data)
        assert len(findings) > 0
        assert any("debug" in f.summary.lower() for f in findings)

    def test_analyze_secrets(self):
        analyzer = DiffAnalyzer()
        diff_data = {
            "files_changed": ["file1.py"],
            "has_hardcoded_secrets": True,
            "secret_files": [("file1.py", "API key")],
        }

        findings = analyzer.analyze(diff_data)
        assert len(findings) > 0
        assert any(f.severity == ReviewSeverity.CRITICAL for f in findings)

    def test_analyze_scope(self):
        analyzer = DiffAnalyzer()
        result = analyzer.analyze_scope(
            task_files=["auth.py"],
            changed_files=["auth.py", "billing.py"],
        )
        assert len(result["in_scope_files"]) == 1
        assert len(result["out_of_scope_files"]) == 1


class TestRequirementAnalyzer:
    def test_all_satisfied(self):
        analyzer = RequirementAnalyzer()
        requirements = [
            {"description": "Req 1", "status": "satisfied"},
        ]

        findings = analyzer.analyze(requirements, {})
        assert len(findings) == 0

    def test_unsatisfied(self):
        analyzer = RequirementAnalyzer()
        requirements = [
            {"description": "Req 1", "status": "unsatisfied"},
        ]

        findings = analyzer.analyze(requirements, {})
        assert len(findings) > 0
        assert findings[0].severity == ReviewSeverity.HIGH

    def test_partially_satisfied(self):
        analyzer = RequirementAnalyzer()
        requirements = [
            {"description": "Req 1", "status": "partially_satisfied"},
        ]

        findings = analyzer.analyze(requirements, {})
        assert len(findings) > 0
        assert findings[0].severity == ReviewSeverity.MEDIUM

    def test_unverified(self):
        analyzer = RequirementAnalyzer()
        requirements = [
            {"description": "Req 1", "status": "unverified"},
        ]

        findings = analyzer.analyze(requirements, {})
        assert len(findings) > 0


class TestSecurityAnalyzer:
    def test_no_issues(self):
        analyzer = SecurityAnalyzer()
        findings = analyzer.analyze([], [])
        assert len(findings) == 0

    def test_security_denied(self):
        analyzer = SecurityAnalyzer()
        events = [{"decision": "deny", "capability": "test"}]

        findings = analyzer.analyze(events, [])
        assert len(findings) > 0
        assert findings[0].severity == ReviewSeverity.CRITICAL

    def test_injection_detected(self):
        analyzer = SecurityAnalyzer()
        events = [{"type": "injection_detected", "injection_type": "override"}]

        findings = analyzer.analyze(events, [])
        assert len(findings) > 0

    def test_audit_violation(self):
        analyzer = SecurityAnalyzer()
        events = [{"event_type": "policy_violation"}]

        findings = analyzer.analyze([], events)
        assert len(findings) > 0


class TestRegressionAnalyzer:
    def test_no_regression(self):
        analyzer = RegressionAnalyzer()
        result = {"has_regression": False, "baseline_available": True}

        findings = analyzer.analyze(result)
        assert len(findings) == 0

    def test_regression_detected(self):
        analyzer = RegressionAnalyzer()
        result = {
            "has_regression": True,
            "new_failures": [{"name": "test1"}],
            "baseline_available": True,
        }

        findings = analyzer.analyze(result)
        assert len(findings) > 0

    def test_no_baseline(self):
        analyzer = RegressionAnalyzer()
        result = {"has_regression": False, "baseline_available": False}

        findings = analyzer.analyze(result)
        assert len(findings) > 0
        assert findings[0].severity == ReviewSeverity.LOW


class TestAdversarialCases:
    def test_passing_tests_missing_requirement(self):
        """Tests pass but requirement not implemented."""
        collector = EvidenceCollector()
        collector.add_verification_result(passed=True, total=10)
        collector.add_requirements([
            {"description": "Add feature X", "status": "unsatisfied"},
        ])

        result = run_review(collector.collection)
        assert result.status == ReviewStatus.FAIL

    def test_deleted_failing_test(self):
        """Old test deleted, remaining tests pass."""
        collector = EvidenceCollector()
        collector.add_verification_result(passed=True, total=5)
        collector.add_git_diff({
            "deleted_tests": [{"name": "test_login"}],
        })

        result = run_review(collector.collection)
        assert result.status in (ReviewStatus.FAIL, ReviewStatus.BLOCKED)

    def test_unrelated_modification(self):
        """Requested auth fix, but payment subsystem changed."""
        collector = EvidenceCollector()
        collector.add_scope_check(
            in_scope=[{"file": "auth.py"}],
            out_of_scope=[{"file": "billing.py"}],
        )

        result = run_review(collector.collection)
        assert result.status in (ReviewStatus.PASS_WITH_WARNINGS, ReviewStatus.FAIL)

    def test_secret_introduced(self):
        """Hardcoded API token, tests pass."""
        collector = EvidenceCollector()
        collector.add_verification_result(passed=True, total=5)
        collector.add_git_diff({
            "has_hardcoded_secrets": True,
            "secret_files": [("file.py", "API key")],
        })

        result = run_review(collector.collection)
        assert result.status == ReviewStatus.BLOCKED

    def test_verification_unavailable(self):
        """Implementation changed, tests could not run."""
        collector = EvidenceCollector()
        collector.add_requirements([
            {"description": "Add feature X", "status": "unverified"},
        ])

        result = run_review(collector.collection)
        assert result.status == ReviewStatus.INCONCLUSIVE

    def test_recovery_succeeded_requirement_incomplete(self):
        """Execution recovered, tests pass, requirement still missing."""
        collector = EvidenceCollector()
        collector.add_verification_result(passed=True, total=5)
        collector.add_recovery_history([
            {"attempt": 1, "success": True, "strategy": "repair"},
        ])
        collector.add_requirements([
            {"description": "Add feature X", "status": "unsatisfied"},
        ])

        result = run_review(collector.collection)
        assert result.status == ReviewStatus.FAIL


class TestReviewReport:
    def test_text_report(self):
        from argus.review.report import ReviewReport

        result = ReviewResult(
            status=ReviewStatus.PASS,
            task="Test task",
        )
        report = ReviewReport(result)
        text = report.to_text()

        assert "PASS" in text
        assert "Test task" in text

    def test_json_report(self):
        from argus.review.report import ReviewReport

        result = ReviewResult(
            status=ReviewStatus.PASS,
        )
        report = ReviewReport(result)
        json_str = report.to_json()
        d = json.loads(json_str)

        assert d["status"] == "pass"

    def test_report_with_findings(self):
        from argus.review.report import ReviewReport

        result = ReviewResult(
            status=ReviewStatus.FAIL,
            findings=[
                ReviewFinding(
                    category=FindingCategory.SECURITY,
                    severity=ReviewSeverity.CRITICAL,
                    summary="Critical finding",
                )
            ],
        )
        report = ReviewReport(result)
        text = report.to_text()

        assert "Critical finding" in text
        assert "CRITICAL" in text


class TestRunReview:
    def test_run_review_function(self):
        collector = EvidenceCollector()
        collector.add_verification_result(passed=True, total=5)

        result = run_review(collector.collection, task="Test")
        assert isinstance(result, ReviewResult)

    def test_run_review_with_run_id(self):
        collector = EvidenceCollector()

        result = run_review(collector.collection, run_id="run-123")
        assert result.run_id == "run-123"
