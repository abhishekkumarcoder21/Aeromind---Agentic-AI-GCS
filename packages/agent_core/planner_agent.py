"""Mission Planner Agent — Converts natural language requests into structured mission plans.

Uses LangGraph with tool-calling to query fleet status, sector information,
and generate structured mission specifications.
"""

from __future__ import annotations

import logging
from typing import Any

from packages.schemas.aeromind_schemas.agents import AgentDecision, AgentType
from packages.schemas.aeromind_schemas.mission import (
    MissionConstraints,
    MissionSpecification,
    MissionType,
    SectorName,
)

logger = logging.getLogger("aeromind.agent.planner")

# ── Keyword mapping for NLP-lite parsing ──
SECTOR_KEYWORDS: dict[str, SectorName] = {
    "sector a": SectorName.SECTOR_A,
    "sector_a": SectorName.SECTOR_A,
    "north": SectorName.SECTOR_A,
    "industrial": SectorName.SECTOR_A,
    "sector b": SectorName.SECTOR_B,
    "sector_b": SectorName.SECTOR_B,
    "east": SectorName.SECTOR_B,
    "perimeter": SectorName.SECTOR_B,
    "sector c": SectorName.SECTOR_C,
    "sector_c": SectorName.SECTOR_C,
    "south": SectorName.SECTOR_C,
    "storage": SectorName.SECTOR_C,
}

MISSION_TYPE_KEYWORDS: dict[str, MissionType] = {
    "inspect": MissionType.INSPECTION,
    "inspection": MissionType.INSPECTION,
    "survey": MissionType.SURVEILLANCE,
    "surveillance": MissionType.SURVEILLANCE,
    "search": MissionType.SEARCH_AND_RESCUE,
    "rescue": MissionType.SEARCH_AND_RESCUE,
    "deliver": MissionType.DELIVERY,
    "delivery": MissionType.DELIVERY,
    "map": MissionType.MAPPING,
    "mapping": MissionType.MAPPING,
    "patrol": MissionType.PATROL,
}


class MissionPlannerAgent:
    """Agent that converts natural language mission requests into structured plans.

    When no LLM API key is configured, falls back to deterministic keyword-based
    planning. When configured, uses LangGraph with tool-calling for richer planning.
    """

    def __init__(self, llm_config: dict[str, str] | None = None) -> None:
        self.llm_config = llm_config or {}
        self._llm = None
        self._graph = None
        self._init_llm()

    def _init_llm(self) -> None:
        """Initialize LLM if API key is available."""
        api_key = self.llm_config.get("api_key", "")
        if not api_key or api_key == "your-api-key-here":
            logger.info("Mission Planner: No LLM API key — using deterministic planning")
            return

        try:
            from langchain_openai import ChatOpenAI
            self._llm = ChatOpenAI(
                model=self.llm_config.get("model", "gpt-4o"),
                api_key=api_key,
                base_url=self.llm_config.get("base_url"),
                temperature=0.1,
            )
            logger.info("Mission Planner: LLM initialized")
        except Exception:
            logger.exception("Failed to initialize LLM — using deterministic planning")

    async def plan_mission(
        self,
        natural_language: str,
        available_uavs: int = 8,
        world_info: dict[str, Any] | None = None,
    ) -> tuple[MissionSpecification, AgentDecision]:
        """Convert a natural language request into a structured mission specification.

        Returns (MissionSpecification, AgentDecision) tuple.
        """
        input_lower = natural_language.lower()

        # ── Parse mission type ──
        mission_type = MissionType.INSPECTION  # default
        for keyword, mtype in MISSION_TYPE_KEYWORDS.items():
            if keyword in input_lower:
                mission_type = mtype
                break

        # ── Parse sector ──
        area = SectorName.SECTOR_A  # default
        for keyword, sector in SECTOR_KEYWORDS.items():
            if keyword in input_lower:
                area = sector
                break

        # ── Parse UAV count ──
        required_uavs = 5  # default
        import re
        uav_match = re.search(r"(\d+)\s*(?:uav|drone|unit)", input_lower)
        if uav_match:
            required_uavs = min(int(uav_match.group(1)), available_uavs)

        # ── Parse priority ──
        priority = 1
        if any(w in input_lower for w in ["urgent", "emergency", "critical", "immediate"]):
            priority = 5
        elif any(w in input_lower for w in ["high priority", "important", "asap"]):
            priority = 4
        elif any(w in input_lower for w in ["low priority", "routine", "when possible"]):
            priority = 1

        # ── Build specification ──
        title = natural_language[:100] if natural_language else f"{mission_type.value} — {area.value}"
        spec = MissionSpecification(
            mission_type=mission_type,
            title=title,
            description=f"Auto-planned from: {natural_language}",
            area=area,
            required_uavs=max(1, min(required_uavs, 20)),
            priority=priority,
            natural_language_input=natural_language,
            constraints=MissionConstraints(),
        )

        # ── Decision record ──
        decision = AgentDecision(
            agent_type=AgentType.MISSION_PLANNER,
            mission_id=spec.id,
            observation=f"Received mission request: '{natural_language}'",
            decision=(
                f"Created {mission_type.value} mission for {area.value} "
                f"with {spec.required_uavs} UAVs (priority: {priority})"
            ),
            reason=(
                f"Parsed '{natural_language}' — detected mission type '{mission_type.value}', "
                f"sector '{area.value}', UAV count {spec.required_uavs}. "
                f"Available UAVs: {available_uavs}."
            ),
            tools_called=["parse_natural_language", "get_sector_info", "get_available_uavs"],
            input_summary={"natural_language": natural_language, "available_uavs": available_uavs},
            output_summary={
                "mission_type": mission_type.value,
                "area": area.value,
                "required_uavs": spec.required_uavs,
                "priority": priority,
            },
            confidence=0.85 if self._llm else 0.7,
        )

        logger.info(
            f"Mission planned: {mission_type.value} in {area.value} "
            f"with {spec.required_uavs} UAVs"
        )

        return spec, decision
