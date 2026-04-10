# Autopilot Spec: Claude Code NVIDIA Account Manager

## Goal

Build a local desktop GUI for managing NVIDIA NIM accounts and their LiteLLM model routing for Claude Code.

## Chosen Implementation

- Language/UI: Python 3 + Tkinter
- Reason: available in the current environment, minimal dependencies, true desktop UI, easy Windows integration.
- App entrypoint: `model_account_manager.py`
- Data file: `%USERPROFILE%\.claude\nim-bridge\account-manager.json`
- Generated config: `C:\Users\prohibit\.claude\litellm.config.yaml`

## Core Features

- Account pool table.
- Add/edit/delete account.
- Assign each account to one model.
- Allow multiple accounts to select the same model.
- Enable/disable accounts.
- Generate LiteLLM config from enabled accounts.
- Back up existing config before overwrite.
- Restart LiteLLM via existing PowerShell scripts.
- Verify `/v1/models`.
- Health check an account and record:
  - last status
  - last checked time
  - suspected rate limit
  - estimated request count

## Secret Handling

- API keys are stored as Windows user environment variables.
- Account metadata stores only the environment variable name, not the key value.
- Generated YAML references `os.environ/<env_var>`.

## Minimum Acceptance

- The app launches.
- User can add account.
- User can assign model.
- User can apply config.
- Existing LiteLLM config is backed up.
- `/v1/models` verification works.
