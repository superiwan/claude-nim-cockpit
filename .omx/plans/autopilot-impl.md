# Autopilot Implementation Plan

## Files

- `model_account_manager.py`
- `README.md`
- `.omx/specs/deep-interview-model-admin-ui.md`
- `.omx/plans/autopilot-spec.md`
- `.omx/plans/autopilot-impl.md`

## Steps

1. Implement account model and JSON storage.
2. Implement Windows user environment variable get/set helpers.
3. Implement LiteLLM YAML generation.
4. Implement Tkinter UI:
   - account table
   - account editor
   - actions panel
   - status panel
5. Implement apply flow:
   - save account metadata
   - write env vars
   - back up config
   - write generated YAML
   - restart LiteLLM
   - verify `/v1/models`
6. Implement health check:
   - call NIM OpenAI-compatible endpoint with selected model and account key
   - mark success/failure/rate-limit
   - update estimated request count
7. Run syntax and basic import checks.
8. Update README.
