# Component 3 backend

The backend is grouped by runtime responsibility:

- `navigation/` contains routing, localization, AprilTag, camera, deviation,
  rerouting, simulation entry points, and navigation tests.
- `recommendation/` contains data preparation, ranking, artifact loading,
  guarded live inference, and recommendation tests.
- `shared/` contains API validation and shopping-session code used across both
  backend areas.
- `requirements.txt` defines the Component 3 Python dependencies.

Run backend tests from the repository root with:

```bash
component3/.venv/bin/python -m pytest component3/backend -q
```
