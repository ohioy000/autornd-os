"""Evaluation: scoring a workflow against known-good expectations.

The graph lets you compare two shapes. This tells you whether either of them is
any good — which is the half that comparison alone cannot answer.

Most of what matters is decidable without a judge. Whether triage found the
right domains, whether the loop converged inside its budget, whether a run cost
more calls than it should: all of that is a set comparison or an integer
comparison against an expectation written down in advance. Those assertions are
free, instant, and they are what catches a regression.

A model judging output quality is the expensive minority of the work, and it
goes on top — never underneath.
"""

from autornd.evals.assertions import Assertion, AssertionResult, score
from autornd.evals.scenario import Scenario, ScenarioError, load_scenarios

__all__ = [
    "Assertion",
    "AssertionResult",
    "Scenario",
    "ScenarioError",
    "load_scenarios",
    "score",
]
