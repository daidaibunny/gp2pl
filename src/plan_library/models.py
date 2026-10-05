"""
Structured AgentSpeak(L) plan-library models.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, Tuple


@dataclass(frozen=True)
class AgentSpeakTrigger:
	"""Structured trigger for one AgentSpeak(L) plan."""

	event_type: str
	symbol: str
	arguments: Tuple[str, ...] = ()

	def to_dict(self) -> Dict[str, Any]:
		return {
			"event_type": self.event_type,
			"symbol": self.symbol,
			"arguments": list(self.arguments),
		}

	@classmethod
	def from_dict(cls, payload: Dict[str, Any]) -> "AgentSpeakTrigger":
		return cls(
			event_type=str(payload.get("event_type") or "").strip(),
			symbol=str(payload.get("symbol") or "").strip(),
			arguments=tuple(
				str(value).strip()
				for value in (payload.get("arguments") or ())
				if str(value).strip()
			),
		)


@dataclass(frozen=True)
class AgentSpeakBodyStep:
	"""Structured body step for one AgentSpeak(L) plan."""

	kind: str
	symbol: str
	arguments: Tuple[str, ...] = ()

	def to_dict(self) -> Dict[str, Any]:
		return {
			"kind": self.kind,
			"symbol": self.symbol,
			"arguments": list(self.arguments),
		}

	@classmethod
	def from_dict(cls, payload: Dict[str, Any]) -> "AgentSpeakBodyStep":
		return cls(
			kind=str(payload.get("kind") or "").strip(),
			symbol=str(payload.get("symbol") or "").strip(),
			arguments=tuple(
				str(value).strip()
				for value in (payload.get("arguments") or ())
				if str(value).strip()
			),
		)


@dataclass(frozen=True)
class AgentSpeakPlan:
	"""Structured AgentSpeak(L) plan entry."""

	plan_name: str
	trigger: AgentSpeakTrigger
	context: Tuple[str, ...] = ()
	body: Tuple[AgentSpeakBodyStep, ...] = ()
	source_instruction_ids: Tuple[str, ...] = ()
	binding_certificate: Tuple[Dict[str, Any], ...] = ()

	def to_dict(self) -> Dict[str, Any]:
		return {
			"plan_name": self.plan_name,
			"trigger": self.trigger.to_dict(),
			"context": list(self.context),
			"body": [step.to_dict() for step in self.body],
			"source_instruction_ids": list(self.source_instruction_ids),
			"binding_certificate": [dict(item) for item in self.binding_certificate],
		}

	@classmethod
	def from_dict(cls, payload: Dict[str, Any]) -> "AgentSpeakPlan":
		return cls(
			plan_name=str(payload.get("plan_name") or "").strip(),
			trigger=AgentSpeakTrigger.from_dict(dict(payload.get("trigger") or {})),
			context=tuple(
				str(value).strip()
				for value in (payload.get("context") or ())
				if str(value).strip()
			),
			body=tuple(
				AgentSpeakBodyStep.from_dict(item)
				for item in (payload.get("body") or ())
				if isinstance(item, dict)
			),
			source_instruction_ids=tuple(
				str(value).strip()
				for value in (payload.get("source_instruction_ids") or ())
				if str(value).strip()
			),
			binding_certificate=tuple(
				dict(item)
				for item in (payload.get("binding_certificate") or ())
				if isinstance(item, dict)
			),
		)


@dataclass(frozen=True)
class PlanLibrary:
	"""Generated AgentSpeak(L) plan library S."""

	domain_name: str
	plans: Tuple[AgentSpeakPlan, ...]
	initial_beliefs: Tuple[str, ...] = ()
	metadata: Dict[str, Any] = field(default_factory=dict)

	def to_dict(self) -> Dict[str, Any]:
		return {
			"domain_name": self.domain_name,
			"plans": [plan.to_dict() for plan in self.plans],
			"initial_beliefs": list(self.initial_beliefs),
			"metadata": dict(self.metadata),
		}

	@classmethod
	def from_dict(cls, payload: Dict[str, Any]) -> "PlanLibrary":
		return cls(
			domain_name=str(payload.get("domain_name") or "").strip(),
			plans=tuple(
				AgentSpeakPlan.from_dict(item)
				for item in (payload.get("plans") or ())
				if isinstance(item, dict)
			),
			initial_beliefs=tuple(
				str(value).strip()
				for value in (payload.get("initial_beliefs") or ())
				if str(value).strip()
			),
			metadata=dict(payload.get("metadata") or {}),
		)
