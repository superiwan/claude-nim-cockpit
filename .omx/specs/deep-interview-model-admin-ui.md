# Deep Interview Spec: Claude Code NVIDIA Account Manager

## Metadata

- Profile: standard
- Context type: greenfield application with brownfield integration points
- Rounds: 6
- Final ambiguity: 0.17
- Threshold: 0.20
- Context snapshot: `D:\claudecode_project\.omx\context\model-admin-ui-20260409T225709Z.md`

## Clarity Breakdown

| Dimension | Score |
| --- | --- |
| Intent | 0.86 |
| Outcome | 0.84 |
| Scope | 0.82 |
| Constraints | 0.80 |
| Success criteria | 0.70 |

## Intent

Build a desktop visual manager for the current Claude Code -> LiteLLM -> NVIDIA NIM setup so the user no longer needs to hand-edit YAML files, PowerShell scripts, or environment variables to manage NVIDIA accounts and model routing.

## Desired Outcome

The user wants a local desktop application that acts like a "Claude Code NVIDIA account manager".

Core user outcome:
- See an account pool.
- Add multiple NVIDIA accounts.
- Assign one or more accounts to models.
- Reassign accounts between models at any time.
- Generate/apply LiteLLM routing configuration.
- See estimated usage and health status per account.

## In Scope

- Desktop application.
- Local-only operation.
- NVIDIA account pool management.
- Add, edit, delete accounts.
- Store API keys locally.
- Bind accounts to supported NIM models.
- Allow multiple accounts to bind to the same model.
- Allow one account to move from one model to another.
- Support future new accounts beyond the current three.
- Generate/update `C:\Users\prohibit\.claude\litellm.config.yaml`.
- Keep Claude Code entrypoint unchanged: `http://127.0.0.1:4000`.
- Restart LiteLLM after applying config.
- Show model/account routing state.
- Show account status from local evidence:
  - estimated usage from LiteLLM logs or local request records where available
  - last success/failure
  - suspected rate limit
  - basic availability
- Provide a minimum viable UI for daily account/model management.

## Out Of Scope / Non-goals

First version should stay minimal.

Not required:
- Login or multi-user permissions.
- Cloud sync.
- Remote deployment.
- Multi-supplier management beyond NVIDIA NIM.
- Complex billing dashboard.
- Automatic recharge or purchasing.
- Production-grade telemetry platform.
- Exact NVIDIA official remaining balance if no stable API exists.
- Over-designed reporting or analytics.

## Decision Boundaries

The implementation may decide without asking:
- Desktop application technology stack.
- Local storage format and path.
- UI style and layout.
- How to back up generated configuration.
- How to update LiteLLM config.
- How to restart LiteLLM.
- How to estimate usage from local data.
- How to represent account health.
- Any other implementation detail needed for the minimum viable version.

Must preserve:
- Chinese user-facing communication where practical.
- Current Claude Code integration path.
- Local-only management.
- No accidental loss of existing config: back up before write.

## Constraints

- Existing real integration files:
  - `C:\Users\prohibit\.claude\litellm.config.yaml`
  - `C:\Users\prohibit\.claude\nim-bridge\start_litellm.ps1`
  - `C:\Users\prohibit\.claude\nim-bridge\stop_litellm.ps1`
  - `C:\Users\prohibit\.claude\nim-bridge\enable_nim_global.ps1`
- Current LiteLLM gateway:
  - `http://127.0.0.1:4000`
- Existing models:
  - `sonnet-glm5` -> `nvidia_nim/z-ai/glm5`
  - `opus-minimax` -> `nvidia_nim/minimaxai/minimax-m2.5`
  - `haiku-kimi` -> `nvidia_nim/moonshotai/kimi-k2.5`
  - `kimi-k2.5` -> `nvidia_nim/moonshotai/kimi-k2.5`
  - `glm5` -> `nvidia_nim/z-ai/glm5`
  - `minimax-m2.5` -> `nvidia_nim/minimaxai/minimax-m2.5`
  - `step-3.5-flash` -> `nvidia_nim/stepfun-ai/step-3.5-flash`
- Exact NVIDIA remaining quota is not required if no reliable API is available.

## Acceptance Criteria

1. The user can launch a desktop app from this workspace.
2. The app shows an account pool.
3. The user can add an account with a name and NVIDIA API key.
4. The user can edit or delete an account.
5. The user can assign accounts to one or more known models.
6. The app can generate LiteLLM config from those assignments.
7. The app backs up the previous LiteLLM config before writing.
8. The app can restart LiteLLM through existing scripts or equivalent local commands.
9. The app can query `/v1/models` to confirm LiteLLM is alive after applying changes.
10. The app displays account health fields such as last status, last checked time, estimated usage, and suspected rate limit.
11. The app does not require manual editing of YAML for the primary flow.
12. The README or app help explains where data/config is stored and how to run it.

## Assumptions And Resolutions

- Initial assumption: one NVIDIA account should manage only one model.
- Resolution: rejected. The user wants flexible assignment. Multiple accounts may bind to one model, and one account may be reassigned.

- Initial assumption: the app must show true remaining NVIDIA quota.
- Resolution: rejected as a hard requirement. Estimated usage plus health/status is acceptable.

- Initial assumption: the app might need broader supplier support.
- Resolution: first version should remain minimal and NVIDIA-focused.

## Pressure-pass Findings

The "remaining quota" requirement was pressure-tested. The user accepts fallback behavior based on local usage estimates and account health if NVIDIA does not expose a stable quota endpoint.

## Brownfield Evidence Vs Inference

Evidence:
- Existing LiteLLM and PowerShell integration is under `C:\Users\prohibit\.claude`.
- Existing gateway uses `http://127.0.0.1:4000`.
- Current config already supports multi-account style routing with `NVIDIA_NIM_API_KEY_1/2/3`.

Inference:
- The first version can be a standalone local desktop app rather than a web dashboard because the user explicitly preferred desktop and delegated stack choices.

## Transcript Summary

1. User wants a visual NVIDIA account manager for Claude Code instead of manual file editing.
2. User wants account pool management, model assignment, flexible reassignment, and future new accounts.
3. User wants usage/remaining quota display, but accepts estimated usage plus account health.
4. User wants minimal implementation only.
5. User chose desktop app and delegated other decisions.
