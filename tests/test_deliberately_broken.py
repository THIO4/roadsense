"""Demonstration for the report: this test is wrong on purpose.

Opened as a pull request to show that CI rejects the change and that the deploy job
never runs for pull requests. The PR is closed without merging.
"""

from roadsense.index import band_for


def test_wrong_expectation():
    assert band_for(85) == "hazardous"  # correct answer is "good"
