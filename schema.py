"""JSON schema the Groq model must return (strict mode)."""

RESPONSE_SCHEMA = {
    "type": "object",
    "additionalProperties": False,
    "required": ["forecasts", "incidents", "advisories", "infrastructure", "summary"],
    "properties": {
        "summary": {"type": "string"},
        "forecasts": {
            "type": "array",
            "items": {
                "type": "object",
                "additionalProperties": False,
                "required": ["segment_id", "horizon_min", "speed_kmh", "confidence", "rationale"],
                "properties": {
                    "segment_id": {"type": "string"},
                    "horizon_min": {"type": "integer"},
                    "speed_kmh": {"type": "number"},
                    "confidence": {"type": "number"},
                    "rationale": {"type": "string"},
                },
            },
        },
        "incidents": {
            "type": "array",
            "items": {
                "type": "object",
                "additionalProperties": False,
                "required": ["segment_id", "incident_class", "confidence", "rationale"],
                "properties": {
                    "segment_id": {"type": "string"},
                    "incident_class": {
                        "type": "string",
                        "enum": [
                            "blockage_or_crash",
                            "event_surge",
                            "weather_effect",
                            "sensor_fault",
                            "unclassified_anomaly",
                        ],
                    },
                    "confidence": {"type": "number"},
                    "rationale": {"type": "string"},
                },
            },
        },
        "advisories": {
            "type": "array",
            "items": {
                "type": "object",
                "additionalProperties": False,
                "required": [
                    "title", "action", "affected_segments", "diversion",
                    "expected_saving_min", "confidence", "evidence",
                ],
                "properties": {
                    "title": {"type": "string"},
                    "action": {"type": "string"},
                    "affected_segments": {"type": "array", "items": {"type": "string"}},
                    "diversion": {"type": "array", "items": {"type": "string"}},
                    "expected_saving_min": {"type": "number"},
                    "confidence": {"type": "number"},
                    "evidence": {"type": "string"},
                },
            },
        },
        "infrastructure": {
            "type": "array",
            "items": {
                "type": "object",
                "additionalProperties": False,
                "required": [
                    "candidate_id", "segment_id", "intervention",
                    "rationale", "estimated_delay_reduction_pct",
                ],
                "properties": {
                    "candidate_id": {"type": "string"},
                    "segment_id": {"type": "string"},
                    "intervention": {"type": "string"},
                    "rationale": {"type": "string"},
                    "estimated_delay_reduction_pct": {"type": "number"},
                },
            },
        },
    },
}

ALLOWED_CLASSES = set(RESPONSE_SCHEMA["properties"]["incidents"]["items"]["properties"]["incident_class"]["enum"])
HORIZONS = (15, 30, 45, 60)
