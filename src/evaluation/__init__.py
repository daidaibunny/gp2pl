"""Evaluation support exports."""

from __future__ import annotations

from typing import Any

__all__ = [
	"DFABuilder",
	"LTLfToDFA",
	"compare_gold_and_prediction",
	"validate_execution_trace",
]


def __getattr__(name: str) -> Any:
	if name in {
		"DFABuilder",
		"LTLfToDFA",
	}:
		from .temporal_compilation import (
			DFABuilder,
			LTLfToDFA,
		)

		return {
			"DFABuilder": DFABuilder,
			"LTLfToDFA": LTLfToDFA,
		}[name]
	if name in {
		"compare_gold_and_prediction",
		"validate_execution_trace",
	}:
		from .temporal_goal_validation import (
			compare_gold_and_prediction,
			validate_execution_trace,
		)

		return {
			"compare_gold_and_prediction": compare_gold_and_prediction,
			"validate_execution_trace": validate_execution_trace,
		}[name]
	raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
