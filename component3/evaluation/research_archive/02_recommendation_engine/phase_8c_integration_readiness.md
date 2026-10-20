# Phase 8C integration readiness

The selected JSON artifact reloads deterministically and the offline inference interface
returns product key, normalized name, score, model version, candidate source, mapping
status, navigation flag, mapped demo ID/location and only evidence-supported explanations.
Observed items are excluded and only four mapped candidates carry shelf/pickup data.

Phase 8C is **technically prepared but not approved for customer exposure**. Before UI
integration, explicitly accept the weak frozen-test quality and unknown-provenance risk,
define score/display thresholds, keep suggestions inert until customer acceptance, and
route only `navigation_eligible=true` outputs through the existing atomic mutation API.
Do not replace the demonstration suggestion or alter the dashboard in Phase 8B.
