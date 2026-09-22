"""Explanation generator for Evidence-Backed Pollution Events.

Generates human-readable, evidence-traceable explanations answering
'Why was this event created?' strictly based on supplied signals without speculation.
"""

from typing import Dict, List, Optional
from schemas.event import EventSeverity, EventStatus, EvidenceSignal


def generate_event_explanation(
    signals: Dict[str, EvidenceSignal],
    fusion_score: float,
    status: EventStatus,
    severity: EventSeverity,
    probable_source: Optional[str],
    corroboration_count: int,
) -> str:
    """Generate structured narrative explaining event creation rationale."""
    parts: List[str] = []

    # 1. Headline summary
    source_label = probable_source or "Unclassified combustion"
    parts.append(
        f"Pollution event classified as {status.value} ({severity.value} severity) "
        f"based on {corroboration_count} corroborating observation signal(s) "
        f"with a composite evidence score of {fusion_score:.2f}/1.0."
    )

    # 2. Citizen report evidence
    cit_signal = signals.get("citizen_report")
    if cit_signal and cit_signal.availability and cit_signal.score is not None:
        vis_ev = cit_signal.metadata.get("visual_evidence", "Visual smoke detected")
        conf = cit_signal.metadata.get("confidence", 0.0)
        smoke_int = cit_signal.metadata.get("smoke_intensity", "moderate")
        parts.append(
            f"Citizen photographic evidence confirmed {smoke_int} smoke "
            f"(visual confidence: {conf * 100:.0f}%): \"{vis_ev}\"."
        )

    # 3. Ground sensor anomaly evidence
    ground_signal = signals.get("ground_sensor")
    if ground_signal and ground_signal.availability and ground_signal.score is not None:
        station_id = ground_signal.metadata.get("station_id", "Nearby station")
        station_name = ground_signal.metadata.get("station_name", station_id)
        pm25 = ground_signal.metadata.get("pm25")
        dist = ground_signal.metadata.get("distance_km")
        z_score = ground_signal.metadata.get("z_score")

        dist_str = f" ({dist} km away)" if dist is not None else ""
        pm25_str = f" of {pm25} ug/m3" if pm25 is not None else ""
        z_str = f", z-score: {z_score:.2f}" if z_score is not None else ""

        parts.append(
            f"Ground monitoring station {station_name}{dist_str} registered a PM2.5 anomaly{pm25_str}{z_str}."
        )

    # 4. Satellite / Fire / Weather status (Decision D-007: explicit reporting of unavailable sources)
    unavailable_sources = [
        name.replace("_", " ").title()
        for name, sig in signals.items()
        if not sig.availability
    ]
    if unavailable_sources:
        parts.append(
            f"Note: {', '.join(unavailable_sources)} data was unavailable at detection time "
            "and excluded from the scoring denominator."
        )

    # 5. Probabilistic source attribution
    parts.append(
        f"Source attribution is probabilistic: {source_label}. "
        "Independent operational verification is required before administrative escalation."
    )

    return " ".join(parts)
