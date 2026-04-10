import json
import os
import shutil
import subprocess
import threading
import time
import urllib.error
import urllib.request
import uuid
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from tkinter import messagebox

import customtkinter as ctk


CLAUDE_DIR = Path.home() / ".claude"
BRIDGE_DIR = CLAUDE_DIR / "nim-bridge"
DATA_PATH = BRIDGE_DIR / "account-manager.json"
CONFIG_PATH = CLAUDE_DIR / "litellm.config.yaml"
BACKUP_DIR = BRIDGE_DIR / "backups"
START_SCRIPT = BRIDGE_DIR / "start_litellm.ps1"
STOP_SCRIPT = BRIDGE_DIR / "stop_litellm.ps1"
GATEWAY_URL = "http://127.0.0.1:4000"
NVIDIA_API_BASE = "https://integrate.api.nvidia.com/v1"

DEFAULT_MODEL = "kimi-k2.5"
CLAUDE_ALIAS_OPTIONS = ["default", "sonnet", "opus", "haiku", "custom"]
CLAUDE_ALIAS_LABELS = {"default": "Default", "sonnet": "Sonnet", "opus": "Opus", "haiku": "Haiku", "custom": "Custom"}
CLAUDE_ALIAS_CONFIG_DEFAULTS = {"sonnet": "sonnet", "opus": "opus", "haiku": "haiku"}
CLAUDE_COMPAT_MODEL_NAMES = {
    "sonnet": ["sonnet", "sonnet-glm5"],
    "opus": ["opus", "opus-minimax"],
    "haiku": ["haiku", "haiku-kimi"],
}
MODEL_CATALOG = {
    "z-ai/glm5": "nvidia_nim/z-ai/glm5",
    "minimaxai/minimax-m2.5": "nvidia_nim/minimaxai/minimax-m2.5",
    "moonshotai/kimi-k2.5": "nvidia_nim/moonshotai/kimi-k2.5",
    "stepfun-ai/step-3.5-flash": "nvidia_nim/stepfun-ai/step-3.5-flash",
    "deepseek-ai/deepseek-v3.2": "nvidia_nim/deepseek-ai/deepseek-v3.2",
    "deepseek-ai/deepseek-r1": "nvidia_nim/deepseek-ai/deepseek-r1",
    "kimi-k2.5": "nvidia_nim/moonshotai/kimi-k2.5",
    "glm5": "nvidia_nim/z-ai/glm5",
    "minimax-m2.5": "nvidia_nim/minimaxai/minimax-m2.5",
    "step-3.5-flash": "nvidia_nim/stepfun-ai/step-3.5-flash",
}
DEFAULT_MODEL_LIBRARY = list(MODEL_CATALOG.keys())


@dataclass
class ModelMapping:
    id: str
    claude_alias: str = "default"
    custom_model_name: str = ""
    model_name: str = DEFAULT_MODEL
    weight: int = 1
    enabled: bool = True
    estimated_requests: int = 0
    last_status: str = "未检测"
    last_checked_at: str = ""
    suspected_rate_limit: bool = False

    @classmethod
    def from_dict(cls, data):
        return cls(
            id=data.get("id", str(uuid.uuid4())),
            claude_alias=data.get("claude_alias", infer_claude_alias(data.get("model_name", DEFAULT_MODEL))),
            custom_model_name=data.get("custom_model_name", ""),
            model_name=data.get("model_name", DEFAULT_MODEL),
            weight=int(data.get("weight", 1)),
            enabled=bool(data.get("enabled", True)),
            estimated_requests=int(data.get("estimated_requests", 0)),
            last_status=data.get("last_status", "未检测"),
            last_checked_at=data.get("last_checked_at", ""),
            suspected_rate_limit=bool(data.get("suspected_rate_limit", False)),
        )

    def to_dict(self):
        return {
            "id": self.id,
            "claude_alias": self.claude_alias,
            "custom_model_name": self.custom_model_name,
            "model_name": self.model_name,
            "weight": self.weight,
            "enabled": self.enabled,
            "estimated_requests": self.estimated_requests,
            "last_status": self.last_status,
            "last_checked_at": self.last_checked_at,
            "suspected_rate_limit": self.suspected_rate_limit,
        }


@dataclass
class Account:
    id: str
    name: str
    env_var: str
    claude_alias: str = "default"
    custom_model_name: str = ""
    model_name: str = DEFAULT_MODEL
    weight: int = 1
    enabled: bool = True
    estimated_requests: int = 0
    last_status: str = "未检测"
    last_checked_at: str = ""
    suspected_rate_limit: bool = False
    mappings: list[ModelMapping] = field(default_factory=list)

    @classmethod
    def from_dict(cls, data):
        mappings = [ModelMapping.from_dict(item) for item in data.get("mappings", [])]
        if not mappings:
            mappings = [
                ModelMapping(
                    id=str(uuid.uuid4()),
                    claude_alias=data.get("claude_alias", infer_claude_alias(data.get("model_name", DEFAULT_MODEL))),
                    custom_model_name=data.get("custom_model_name", ""),
                    model_name=data.get("model_name", DEFAULT_MODEL),
                    weight=int(data.get("weight", 1)),
                    enabled=bool(data.get("enabled", True)),
                )
            ]
        return cls(
            id=data["id"],
            name=data["name"],
            env_var=data["env_var"],
            claude_alias=data.get("claude_alias", infer_claude_alias(data.get("model_name", DEFAULT_MODEL))),
            custom_model_name=data.get("custom_model_name", ""),
            model_name=data.get("model_name", DEFAULT_MODEL),
            weight=int(data.get("weight", 1)),
            enabled=bool(data.get("enabled", True)),
            estimated_requests=int(data.get("estimated_requests", 0)),
            last_status=data.get("last_status", "未检测"),
            last_checked_at=data.get("last_checked_at", ""),
            suspected_rate_limit=bool(data.get("suspected_rate_limit", False)),
            mappings=mappings,
        )

    def to_dict(self):
        return {
            "id": self.id,
            "name": self.name,
            "env_var": self.env_var,
            "claude_alias": self.claude_alias,
            "custom_model_name": self.custom_model_name,
            "model_name": self.model_name,
            "weight": self.weight,
            "enabled": self.enabled,
            "estimated_requests": self.estimated_requests,
            "last_status": self.last_status,
            "last_checked_at": self.last_checked_at,
            "suspected_rate_limit": self.suspected_rate_limit,
            "mappings": [mapping.to_dict() for mapping in self.mappings],
        }

    def primary_mapping(self):
        if not self.mappings:
            self.mappings.append(ModelMapping(str(uuid.uuid4())))
        return self.mappings[0]


@dataclass
class Store:
    accounts: list[Account] = field(default_factory=list)
    models: list[str] = field(default_factory=lambda: DEFAULT_MODEL_LIBRARY.copy())

    @classmethod
    def load(cls):
        DATA_PATH.parent.mkdir(parents=True, exist_ok=True)
        if DATA_PATH.exists():
            data = json.loads(DATA_PATH.read_text(encoding="utf-8"))
            accounts = normalize_accounts([Account.from_dict(item) for item in data.get("accounts", [])])
            models = data.get("models") or DEFAULT_MODEL_LIBRARY.copy()
            return cls(accounts, normalize_models(models, accounts))
        return cls(seed_accounts_from_env(), DEFAULT_MODEL_LIBRARY.copy())

    def save(self):
        DATA_PATH.parent.mkdir(parents=True, exist_ok=True)
        DATA_PATH.write_text(json.dumps({"accounts": [a.to_dict() for a in self.accounts], "models": self.models}, ensure_ascii=False, indent=2), encoding="utf-8")


def now_text():
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def get_user_env(name):
    result = subprocess.run(
        ["powershell", "-NoProfile", "-Command", f"[Environment]::GetEnvironmentVariable('{name}','User')"],
        capture_output=True,
        text=True,
        encoding="utf-8",
    )
    return result.stdout.strip()


def set_user_env(name, value):
    escaped = value.replace("'", "''")
    subprocess.run(["powershell", "-NoProfile", "-Command", f"[Environment]::SetEnvironmentVariable('{name}','{escaped}','User')"], check=True)
    os.environ[name] = value


def mask_key(value):
    if not value:
        return "未设置"
    return "*" * len(value) if len(value) <= 12 else f"{value[:8]}...{value[-4:]}"


def infer_claude_alias(model_name):
    if model_name in ("sonnet", "opus", "haiku"):
        return model_name
    return "default" if model_name == DEFAULT_MODEL else "custom"


def claude_model_name(account):
    if account.claude_alias == "custom":
        return account.custom_model_name.strip() or account.model_name
    if account.claude_alias == "default":
        return account.model_name
    return CLAUDE_ALIAS_CONFIG_DEFAULTS.get(account.claude_alias, account.model_name)


def claude_alias_display(account):
    return f"{CLAUDE_ALIAS_LABELS.get(account.claude_alias, account.claude_alias)} -> {claude_model_name(account)}"


def availability_label(account):
    if account.last_status == "可用":
        return "可用"
    if account.last_status == "未检测":
        return "未检测"
    return "不可用"


def availability_color(account):
    return {"可用": "#22c55e", "未检测": "#f59e0b"}.get(availability_label(account), "#ef4444")


def mapping_availability_label(mapping):
    if mapping.last_status == "可用":
        return "可用"
    if mapping.last_status == "未检测":
        return "未检测"
    return "不可用"


def mapping_availability_color(mapping):
    return {"可用": "#22c55e", "未检测": "#f59e0b"}.get(mapping_availability_label(mapping), "#ef4444")


def refresh_account_status(account):
    statuses = [mapping_availability_label(mapping) for mapping in account.mappings]
    if "不可用" in statuses:
        account.last_status = "部分映射不可用"
    elif statuses and all(status == "可用" for status in statuses):
        account.last_status = "可用"
    elif statuses and all(status == "未检测" for status in statuses):
        account.last_status = "未检测"
    else:
        account.last_status = "部分映射未检测"
    checked = [mapping.last_checked_at for mapping in account.mappings if mapping.last_checked_at]
    account.last_checked_at = max(checked) if checked else ""
    account.estimated_requests = sum(mapping.estimated_requests for mapping in account.mappings)
    account.suspected_rate_limit = any(mapping.suspected_rate_limit for mapping in account.mappings)


def seed_accounts_from_env():
    accounts, seen = [], set()
    for index in range(1, 4):
        env_var = f"NVIDIA_NIM_API_KEY_{index}"
        value = get_user_env(env_var)
        if value and value not in seen:
            seen.add(value)
            accounts.append(Account(str(uuid.uuid4()), f"已导入 NVIDIA 账号（{env_var}）", env_var))
    if not accounts and get_user_env("NVIDIA_NIM_API_KEY"):
        accounts.append(Account(str(uuid.uuid4()), "已导入 NVIDIA 账号", "NVIDIA_NIM_API_KEY"))
    return accounts


def normalize_accounts(accounts):
    normalized, seen = [], set()
    for account in accounts:
        key = get_user_env(account.env_var) or account.env_var
        if key in seen:
            continue
        seen.add(key)
        if account.name.startswith("NVIDIA 账号 "):
            account.name = f"已导入 NVIDIA 账号（{account.env_var}）"
        if account.claude_alias != "custom":
            account.custom_model_name = ""
        if not account.mappings:
            account.mappings.append(
                ModelMapping(
                    id=str(uuid.uuid4()),
                    claude_alias=account.claude_alias,
                    custom_model_name=account.custom_model_name,
                    model_name=account.model_name,
                    weight=account.weight,
                    enabled=account.enabled,
                )
            )
        for mapping in account.mappings:
            if mapping.claude_alias != "custom":
                mapping.custom_model_name = ""
            elif not mapping.custom_model_name:
                mapping.custom_model_name = mapping.model_name
        refresh_account_status(account)
        normalized.append(account)
    return normalized


def normalize_models(models, accounts):
    normalized = []
    for model in models:
        if isinstance(model, str) and model.strip() and model.strip() not in normalized:
            normalized.append(model.strip())
    for account in accounts:
        for mapping in account.mappings:
            if mapping.model_name and mapping.model_name not in normalized:
                normalized.append(mapping.model_name)
    return normalized or DEFAULT_MODEL_LIBRARY.copy()


def safe_env_name(account_name):
    base = "".join(ch if ("A" <= ch <= "Z" or "0" <= ch <= "9") else "_" for ch in account_name.upper())
    base = "_".join(part for part in base.split("_") if part) or "ACCOUNT"
    return f"NIM_MANAGER_{base}_{uuid.uuid4().hex[:8]}_KEY"


def nvidia_model_id(model_name):
    return MODEL_CATALOG.get(model_name, model_name).replace("nvidia_nim/", "", 1)


def litellm_model_id(model_name):
    if model_name in MODEL_CATALOG:
        return MODEL_CATALOG[model_name]
    return model_name if model_name.startswith("nvidia_nim/") else f"nvidia_nim/{model_name}"


def generate_litellm_config(accounts):
    lines = ["model_list:"]
    generated_names = set()
    fallback_deployment = None
    for account in [item for item in accounts if item.enabled]:
        for mapping in [item for item in account.mappings if item.enabled]:
            if fallback_deployment is None:
                fallback_deployment = (account, mapping)
            for model_name in compat_model_names(mapping):
                generated_names.add(model_name)
                lines += [
                    f"  - model_name: {model_name}",
                    "    litellm_params:",
                    f"      model: {litellm_model_id(mapping.model_name)}",
                    f"      api_key: os.environ/{account.env_var}",
                    "      api_base: os.environ/NVIDIA_NIM_API_BASE",
                    f"      weight: {max(1, mapping.weight)}",
                    "      timeout: 120",
                    "",
                ]
    if fallback_deployment is not None:
        account, mapping = fallback_deployment
        required_aliases = ["sonnet", "sonnet-glm5", "opus", "opus-minimax", "haiku", "haiku-kimi", "step-3.5-flash"]
        for model_name in required_aliases:
            if model_name in generated_names:
                continue
            generated_names.add(model_name)
            lines += [
                f"  - model_name: {model_name}",
                "    litellm_params:",
                f"      model: {litellm_model_id(mapping.model_name)}",
                f"      api_key: os.environ/{account.env_var}",
                "      api_base: os.environ/NVIDIA_NIM_API_BASE",
                f"      weight: {max(1, mapping.weight)}",
                "      timeout: 120",
                "",
            ]
    if len(lines) == 1:
        lines += [
            "  - model_name: disabled-placeholder",
            "    litellm_params:",
            "      model: nvidia_nim/z-ai/glm5",
            "      api_key: os.environ/NVIDIA_NIM_API_KEY",
            "      api_base: os.environ/NVIDIA_NIM_API_BASE",
            "      timeout: 120",
            "",
        ]
    lines += [
        "general_settings:",
        "  master_key: os.environ/LITELLM_MASTER_KEY",
        "  disable_spend_logs: true",
        "  store_model_in_db: false",
        "",
        "litellm_settings:",
        "  drop_params: true",
        "",
        "router_settings:",
        "  routing_strategy: simple-shuffle",
        "  num_retries: 2",
        "  allowed_fails: 1",
        "  cooldown_time: 30",
        "",
    ]
    return "\n".join(lines)


def compat_model_names(mapping):
    names = CLAUDE_COMPAT_MODEL_NAMES.get(mapping.claude_alias, [claude_model_name(mapping)])
    if mapping.claude_alias == "default":
        names = [mapping.model_name]
        if mapping.model_name != "step-3.5-flash":
            names.append("step-3.5-flash")
    result = []
    for name in names:
        if name and name not in result:
            result.append(name)
    return result


def apply_claude_default_envs(accounts):
    set_user_env("ANTHROPIC_DEFAULT_SONNET_MODEL", "sonnet")
    set_user_env("ANTHROPIC_DEFAULT_OPUS_MODEL", "opus")
    set_user_env("ANTHROPIC_DEFAULT_HAIKU_MODEL", "haiku")
    for account in accounts:
        if account.enabled:
            for mapping in account.mappings:
                if mapping.enabled and mapping.claude_alias == "default":
                    set_user_env("ANTHROPIC_MODEL", claude_model_name(mapping))
                    return


def backup_config():
    BACKUP_DIR.mkdir(parents=True, exist_ok=True)
    if CONFIG_PATH.exists():
        target = BACKUP_DIR / f"litellm.config.{datetime.now().strftime('%Y%m%d_%H%M%S')}.yaml.bak"
        shutil.copy2(CONFIG_PATH, target)
        return target
    return None


def run_bridge_script(script, strict=True):
    result = subprocess.run(
        ["powershell", "-ExecutionPolicy", "Bypass", "-File", str(script)],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        timeout=45,
    )
    if strict and result.returncode != 0:
        raise RuntimeError(f"{script} returned {result.returncode}")
    return result.returncode, ""


def restart_litellm():
    messages = []
    if STOP_SCRIPT.exists():
        code, output = run_bridge_script(STOP_SCRIPT, strict=False)
        messages.append(f"stop_litellm: exit={code}" + (f"\n{output}" if output else ""))
        wait_for_litellm_process_exit()
    if START_SCRIPT.exists():
        code, output = run_bridge_script(START_SCRIPT, strict=True)
        messages.append(f"start_litellm: exit={code}" + (f"\n{output}" if output else ""))
    return "\n".join(messages)


def wait_for_litellm_process_exit(timeout=10):
    pattern = str(CONFIG_PATH).replace("\\", "\\\\")
    command = (
        "Get-CimInstance Win32_Process | "
        "Where-Object { ($_.Name -match 'litellm|python') -and "
        "$_.CommandLine -match 'litellm' -and "
        f"$_.CommandLine -match [regex]::Escape('{CONFIG_PATH}') }} | "
        "Select-Object -First 1 -ExpandProperty ProcessId"
    )
    deadline = time.time() + timeout
    while time.time() < deadline:
        result = subprocess.run(["powershell", "-NoProfile", "-Command", command], capture_output=True, text=True, encoding="utf-8")
        if not result.stdout.strip():
            return True
        time.sleep(0.5)
    return False


def get_master_key():
    return get_user_env("LITELLM_MASTER_KEY") or os.environ.get("LITELLM_MASTER_KEY", "")


def request_json(url, headers=None, body=None, timeout=30):
    data = json.dumps(body).encode("utf-8") if body is not None else None
    req = urllib.request.Request(url, data=data, headers=headers or {}, method="POST" if body else "GET")
    with urllib.request.urlopen(req, timeout=timeout) as response:
        return json.loads(response.read().decode("utf-8"))


class AccountManagerApp(ctk.CTk):
    def __init__(self):
        super().__init__()
        ctk.set_appearance_mode("light")
        ctk.set_default_color_theme("blue")
        self.title("Claude NVIDIA Cockpit")
        self.geometry("1360x820")
        self.minsize(1180, 720)
        self.store = Store.load()
        self.store.save()
        self.selected_account_id = self.store.accounts[0].id if self.store.accounts else None
        account = self.selected_account()
        self.selected_mapping_id = account.primary_mapping().id if account else None
        self.name_var = ctk.StringVar()
        self.key_var = ctk.StringVar()
        self.alias_var = ctk.StringVar(value="default")
        self.custom_var = ctk.StringVar()
        self.model_var = ctk.StringVar(value=DEFAULT_MODEL)
        self.weight_var = ctk.StringVar(value="1")
        self.enabled_var = ctk.BooleanVar(value=True)
        self.build_layout()
        self.refresh_all()
        self.log("Cockpit 已启动。")

    def build_layout(self):
        self.grid_columnconfigure(1, weight=1)
        self.grid_rowconfigure(0, weight=1)
        self.sidebar = ctk.CTkFrame(self, width=230, corner_radius=0, fg_color="#e8f0ff")
        self.sidebar.grid(row=0, column=0, sticky="nsew")
        self.sidebar.grid_propagate(False)
        ctk.CTkLabel(self.sidebar, text="NVIDIA\nCockpit", font=("Segoe UI", 28, "bold"), text_color="#0f172a", justify="left").pack(anchor="w", padx=24, pady=(28, 10))
        ctk.CTkLabel(self.sidebar, text="Claude Code 模型账号驾驶舱", text_color="#64748b", justify="left").pack(anchor="w", padx=24)
        self.sidebar_status = ctk.CTkLabel(self.sidebar, text="", justify="left", text_color="#1f2937")
        self.sidebar_status.pack(anchor="w", padx=24, pady=(28, 10))
        ctk.CTkButton(self.sidebar, text="验证 LiteLLM", command=self.verify_gateway, height=38, fg_color="#2563eb").pack(fill="x", padx=20, pady=(10, 6))
        ctk.CTkButton(self.sidebar, text="应用配置并重启", command=self.apply_config, height=42, fg_color="#16a34a").pack(fill="x", padx=20, pady=6)
        ctk.CTkButton(self.sidebar, text="检测全部账号", command=self.check_all_accounts, height=38, fg_color="#475569").pack(fill="x", padx=20, pady=6)
        ctk.CTkButton(self.sidebar, text="删除选中账号", command=self.delete_account, height=38, fg_color="#7f1d1d", hover_color="#991b1b").pack(fill="x", padx=20, pady=6)

        self.main = ctk.CTkFrame(self, fg_color="#f4f7fb", corner_radius=0)
        self.main.grid(row=0, column=1, sticky="nsew")
        self.main.grid_rowconfigure(2, weight=1)
        self.main.grid_columnconfigure(0, weight=1)
        self.header = ctk.CTkFrame(self.main, fg_color="transparent")
        self.header.grid(row=0, column=0, sticky="ew", padx=28, pady=(24, 8))
        self.header.grid_columnconfigure(0, weight=1)
        ctk.CTkLabel(self.header, text="账号与模型路由", font=("Segoe UI", 30, "bold"), text_color="#0f172a").grid(row=0, column=0, sticky="w")
        ctk.CTkLabel(self.header, text="卡片式账号池、配额状态、Claude 档位映射、快速应用。", text_color="#64748b").grid(row=1, column=0, sticky="w", pady=(6, 0))
        ctk.CTkButton(self.header, text="+ 新增账号", width=130, height=38, command=self.add_account, fg_color="#2563eb").grid(row=0, column=1, rowspan=2, sticky="e")

        self.stats = ctk.CTkFrame(self.main, fg_color="transparent")
        self.stats.grid(row=1, column=0, sticky="ew", padx=28, pady=(8, 14))
        for i in range(4):
            self.stats.grid_columnconfigure(i, weight=1)
        self.stat_cards = {}
        for i, key in enumerate(["accounts", "available", "routes", "gateway"]):
            card = ctk.CTkFrame(self.stats, height=92, fg_color="#ffffff", corner_radius=18)
            card.grid(row=0, column=i, padx=(0 if i == 0 else 10, 0), sticky="ew")
            card.grid_propagate(False)
            title = ctk.CTkLabel(card, text="", font=("Segoe UI", 12), text_color="#64748b")
            value = ctk.CTkLabel(card, text="", font=("Segoe UI", 26, "bold"), text_color="#0f172a")
            title.pack(anchor="w", padx=18, pady=(16, 0))
            value.pack(anchor="w", padx=18, pady=(4, 0))
            self.stat_cards[key] = (title, value)

        self.content = ctk.CTkFrame(self.main, fg_color="transparent")
        self.content.grid(row=2, column=0, sticky="nsew", padx=28, pady=(0, 14))
        self.content.grid_columnconfigure(0, weight=3)
        self.content.grid_columnconfigure(1, weight=3)
        self.content.grid_columnconfigure(2, weight=2)
        self.content.grid_rowconfigure(0, weight=1)
        self.accounts_panel = ctk.CTkFrame(self.content, fg_color="#f4f7fb")
        self.accounts_panel.grid(row=0, column=0, sticky="nsew", padx=(0, 14))
        self.accounts_panel.grid_rowconfigure(1, weight=1)
        self.accounts_panel.grid_columnconfigure(0, weight=1)
        ctk.CTkLabel(self.accounts_panel, text="账号池", font=("Segoe UI", 20, "bold"), text_color="#0f172a").grid(row=0, column=0, sticky="w", pady=(0, 10))
        self.account_list = ctk.CTkScrollableFrame(self.accounts_panel, fg_color="#f4f7fb")
        self.account_list.grid(row=1, column=0, sticky="nsew")
        self.routes_panel = ctk.CTkFrame(self.content, fg_color="#f4f7fb")
        self.routes_panel.grid(row=0, column=1, sticky="nsew", padx=(0, 14))
        self.routes_panel.grid_rowconfigure(1, weight=1)
        self.routes_panel.grid_columnconfigure(0, weight=1)
        ctk.CTkLabel(self.routes_panel, text="Claude Code 映射总览", font=("Segoe UI", 20, "bold"), text_color="#0f172a").grid(row=0, column=0, sticky="w", pady=(0, 10))
        self.route_list = ctk.CTkScrollableFrame(self.routes_panel, fg_color="#f4f7fb")
        self.route_list.grid(row=1, column=0, sticky="nsew")
        self.editor = ctk.CTkScrollableFrame(self.content, fg_color="#ffffff", corner_radius=20)
        self.editor.grid(row=0, column=2, sticky="nsew")
        self.editor.grid_columnconfigure(0, weight=1)
        ctk.CTkLabel(self.editor, text="映射编辑", font=("Segoe UI", 22, "bold"), text_color="#0f172a").grid(row=0, column=0, sticky="w", padx=22, pady=(22, 4))
        self.editing_label = ctk.CTkLabel(self.editor, text="未选择映射", text_color="#64748b")
        self.editing_label.grid(row=1, column=0, sticky="w", padx=22, pady=(0, 14))
        self.build_editor_fields()
        self.log_box = ctk.CTkTextbox(self.main, height=96, fg_color="#ffffff", border_color="#cbd5e1", border_width=1)
        self.log_box.grid(row=3, column=0, sticky="ew", padx=28, pady=(0, 18))

    def build_editor_fields(self):
        row = 2
        self.name_entry = self.field("账号名称", self.name_var, row)
        row += 2
        self.key_entry = self.field("NVIDIA API Key", self.key_var, row, password=True)
        row += 2
        ctk.CTkLabel(self.editor, text="映射到 Claude 档位", text_color="#1f2937").grid(row=row, column=0, sticky="w", padx=22, pady=(12, 4))
        self.alias_menu = ctk.CTkOptionMenu(self.editor, values=[CLAUDE_ALIAS_LABELS[x] for x in CLAUDE_ALIAS_OPTIONS], command=self.on_alias_label_changed)
        self.alias_menu.grid(row=row + 1, column=0, sticky="ew", padx=22)
        row += 2
        self.custom_entry = self.field("Custom 档位名称", self.custom_var, row)
        row += 2
        self.model_entry = self.field("NVIDIA 实际模型", self.model_var, row)
        row += 2
        ctk.CTkLabel(self.editor, text="模型库", text_color="#1f2937").grid(row=row, column=0, sticky="w", padx=22, pady=(8, 4))
        row += 1
        self.quick_models_frame = ctk.CTkFrame(self.editor, fg_color="transparent")
        self.quick_models_frame.grid(row=row, column=0, sticky="ew", padx=22, pady=(0, 4))
        row += 1
        model_actions = ctk.CTkFrame(self.editor, fg_color="transparent")
        model_actions.grid(row=row, column=0, sticky="ew", padx=22, pady=(4, 4))
        model_actions.grid_columnconfigure((0, 1), weight=1)
        ctk.CTkButton(model_actions, text="新增当前模型到库", height=30, fg_color="#2563eb", command=self.add_current_model_to_library).grid(row=0, column=0, padx=(0, 6), sticky="ew")
        ctk.CTkButton(model_actions, text="删除当前模型", height=30, fg_color="#7f1d1d", hover_color="#991b1b", command=self.remove_current_model_from_library).grid(row=0, column=1, padx=(6, 0), sticky="ew")
        row += 1
        weight = ctk.CTkFrame(self.editor, fg_color="transparent")
        weight.grid(row=row, column=0, sticky="ew", padx=22, pady=(8, 4))
        weight.grid_columnconfigure(1, weight=1)
        ctk.CTkLabel(weight, text="权重", text_color="#1f2937").grid(row=0, column=0, sticky="w")
        ctk.CTkEntry(weight, textvariable=self.weight_var, width=80).grid(row=0, column=1, sticky="e")
        row += 1
        ctk.CTkSwitch(self.editor, text="启用这个账号", variable=self.enabled_var).grid(row=row, column=0, sticky="w", padx=22, pady=(12, 8))
        row += 1
        actions = ctk.CTkFrame(self.editor, fg_color="transparent")
        actions.grid(row=row, column=0, sticky="ew", padx=22, pady=(10, 4))
        actions.grid_columnconfigure((0, 1), weight=1)
        ctk.CTkButton(actions, text="保存", command=self.save_current_account, fg_color="#2563eb").grid(row=0, column=0, padx=(0, 6), sticky="ew")
        ctk.CTkButton(actions, text="检测", command=self.check_selected_account, fg_color="#0891b2").grid(row=0, column=1, padx=(6, 0), sticky="ew")
        row += 1
        ctk.CTkButton(self.editor, text="保存并应用配置", command=self.save_and_apply_current_account, fg_color="#16a34a").grid(row=row, column=0, sticky="ew", padx=22, pady=(8, 4))
        row += 1
        ctk.CTkButton(self.editor, text="删除当前映射", command=self.delete_current_mapping, fg_color="#b45309", hover_color="#92400e").grid(row=row, column=0, sticky="ew", padx=22, pady=(8, 4))
        row += 1
        ctk.CTkButton(self.editor, text="删除当前账号", command=self.delete_account, fg_color="#7f1d1d", hover_color="#991b1b").grid(row=row, column=0, sticky="ew", padx=22, pady=(8, 12))

    def field(self, label, variable, row, password=False):
        ctk.CTkLabel(self.editor, text=label, text_color="#1f2937").grid(row=row, column=0, sticky="w", padx=22, pady=(12, 4))
        entry = ctk.CTkEntry(self.editor, textvariable=variable, show="*" if password else None)
        entry.grid(row=row + 1, column=0, sticky="ew", padx=22)
        return entry

    def refresh_all(self):
        self.refresh_sidebar()
        self.refresh_stats()
        self.refresh_model_library()
        self.refresh_account_cards()
        self.refresh_route_cards()
        self.load_selected_account()

    def refresh_sidebar(self):
        self.sidebar_status.configure(text=f"配置\n{CONFIG_PATH}\n\n数据\n{DATA_PATH}\n\n网关\n{GATEWAY_URL}")

    def refresh_stats(self):
        accounts = self.store.accounts
        enabled = [a for a in accounts if a.enabled]
        available = [a for a in accounts if availability_label(a) == "可用"]
        routes = sorted({claude_model_name(mapping) for account in enabled for mapping in account.mappings if mapping.enabled})
        stats = {
            "accounts": ("账号总数", str(len(accounts))),
            "available": ("可用账号", f"{len(available)}/{len(accounts)}"),
            "routes": ("启用路由", str(len(routes))),
            "gateway": ("LiteLLM", "127.0.0.1:4000"),
        }
        for key, (title, value) in stats.items():
            self.stat_cards[key][0].configure(text=title)
            self.stat_cards[key][1].configure(text=value)

    def refresh_model_library(self):
        if not hasattr(self, "quick_models_frame"):
            return
        for child in self.quick_models_frame.winfo_children():
            child.destroy()
        self.quick_models_frame.grid_columnconfigure((0, 1), weight=1)
        for i, model in enumerate(self.store.models):
            ctk.CTkButton(
                self.quick_models_frame,
                text=model,
                height=28,
                fg_color="#475569",
                command=lambda m=model: self.model_var.set(m),
            ).grid(row=i // 2, column=i % 2, padx=4, pady=4, sticky="ew")

    def add_current_model_to_library(self):
        model = self.model_var.get().strip()
        if not model:
            messagebox.showerror("模型为空", "请先填写 NVIDIA 实际模型。")
            return
        if model not in self.store.models:
            self.store.models.append(model)
            self.store.save()
            self.refresh_model_library()
            self.log(f"已加入模型库：{model}")

    def remove_current_model_from_library(self):
        model = self.model_var.get().strip()
        if not model:
            return
        if model not in self.store.models:
            messagebox.showinfo("无需删除", "当前模型不在模型库里。")
            return
        if not messagebox.askyesno("确认删除模型", f"确定从模型库删除 {model} 吗？不会影响已保存账号，只是不再作为快捷按钮显示。"):
            return
        self.store.models = [item for item in self.store.models if item != model]
        self.store.save()
        self.refresh_model_library()
        self.log(f"已从模型库删除：{model}")

    def refresh_account_cards(self):
        for child in self.account_list.winfo_children():
            child.destroy()
        if not self.store.accounts:
            ctk.CTkLabel(self.account_list, text="还没有账号。点击右上角新增账号。", text_color="#64748b").pack(anchor="w", padx=12, pady=18)
            return
        for index, account in enumerate(self.store.accounts):
            card = self.account_card(account)
            card.grid(row=index, column=0, sticky="ew", padx=0, pady=5)
        self.account_list.grid_columnconfigure(0, weight=1)

    def refresh_route_cards(self):
        for child in self.route_list.winfo_children():
            child.destroy()
        account = self.selected_account()
        if not account:
            ctk.CTkLabel(self.route_list, text="请先在账号池选择一个账号。", text_color="#64748b").pack(anchor="w", padx=12, pady=18)
            return
        add_button = ctk.CTkButton(self.route_list, text="+ 新增此账号的映射", height=36, fg_color="#2563eb", command=self.add_mapping_to_selected_account)
        add_button.grid(row=0, column=0, sticky="ew", padx=0, pady=(0, 8))
        if not account.mappings:
            ctk.CTkLabel(self.route_list, text="当前账号还没有映射。", text_color="#64748b").grid(row=1, column=0, sticky="w", padx=12, pady=18)
            return
        for index, mapping in enumerate(account.mappings, start=1):
            card = self.route_card(account, mapping)
            card.grid(row=index, column=0, sticky="ew", padx=0, pady=5)
        self.route_list.grid_columnconfigure(0, weight=1)

    def route_card(self, account, mapping):
        card = ctk.CTkFrame(self.route_list, fg_color="#ffffff", corner_radius=18, border_width=1, border_color="#d6dee9")
        card.grid_columnconfigure(0, weight=1)
        card.grid_columnconfigure(1, weight=0)
        card.grid_columnconfigure(2, weight=0)
        ctk.CTkLabel(card, text=claude_model_name(mapping), font=("Segoe UI", 18, "bold"), text_color="#0f172a").grid(row=0, column=0, sticky="w", padx=14, pady=(10, 0))
        ctk.CTkLabel(card, text=mapping_availability_label(mapping), fg_color=mapping_availability_color(mapping), corner_radius=14, width=64, height=24, text_color="#020617").grid(row=0, column=1, sticky="e", padx=(8, 14), pady=(10, 0))
        alias = CLAUDE_ALIAS_LABELS.get(mapping.claude_alias, mapping.claude_alias)
        summary = f"{alias} | {mapping.model_name}\n{account.name}  w={mapping.weight}  请求={mapping.estimated_requests}"
        ctk.CTkLabel(card, text=summary, justify="left", text_color="#1f2937").grid(row=1, column=0, columnspan=2, sticky="ew", padx=14, pady=(2, 10))
        ctk.CTkButton(card, text="编辑", height=34, width=86, fg_color="#475569", command=lambda: self.select_mapping(account.id, mapping.id)).grid(row=0, column=2, rowspan=2, sticky="e", padx=(0, 14), pady=12)
        return card

    def account_card(self, account):
        selected = account.id == self.selected_account_id
        card = ctk.CTkFrame(self.account_list, fg_color="#ffffff" if selected else "#f8fafc", corner_radius=18, border_width=1, border_color="#2563eb" if selected else "#d6dee9")
        card.grid_columnconfigure(0, weight=1)
        card.grid_columnconfigure(1, weight=0)
        ctk.CTkLabel(card, text=account.name, font=("Segoe UI", 17, "bold"), text_color="#0f172a").grid(row=0, column=0, sticky="ew", padx=14, pady=(10, 0))
        ctk.CTkLabel(card, text=availability_label(account), fg_color=availability_color(account), corner_radius=14, width=64, height=24, text_color="#020617").grid(row=0, column=1, sticky="e", padx=14, pady=(10, 0))
        detail = f"映射数: {len(account.mappings)}  请求={account.estimated_requests}  {'启用' if account.enabled else '停用'}\n当前: {claude_alias_display(account.primary_mapping())}"
        ctk.CTkLabel(card, text=detail, justify="left", text_color="#1f2937").grid(row=1, column=0, columnspan=2, sticky="ew", padx=14, pady=(2, 6))
        footer = ctk.CTkFrame(card, fg_color="transparent")
        footer.grid(row=2, column=0, columnspan=2, sticky="w", padx=14, pady=(0, 10))
        ctk.CTkButton(footer, text="编辑", width=64, height=30, fg_color="#475569", command=lambda: self.select_account(account.id)).pack(side="left")
        ctk.CTkButton(footer, text="检测", width=64, height=30, fg_color="#0891b2", command=lambda: self.run_background(f"开始检测账号：{account.name}", lambda account_id=account.id, mapping_id=account.primary_mapping().id: self.check_account_worker(account_id, mapping_id), "检测完成")).pack(side="left", padx=8)
        ctk.CTkButton(footer, text="删除", width=64, height=30, fg_color="#7f1d1d", hover_color="#991b1b", command=lambda: self.delete_account_by_id(account.id)).pack(side="left")
        return card

    def select_account(self, account_id):
        self.selected_account_id = account_id
        account = self.selected_account()
        self.selected_mapping_id = account.primary_mapping().id if account else None
        self.refresh_all()

    def select_mapping(self, account_id, mapping_id):
        self.selected_account_id = account_id
        self.selected_mapping_id = mapping_id
        self.refresh_all()

    def selected_account(self):
        for account in self.store.accounts:
            if account.id == self.selected_account_id:
                return account
        return None

    def selected_mapping(self):
        account = self.selected_account()
        if not account:
            return None
        for mapping in account.mappings:
            if mapping.id == self.selected_mapping_id:
                return mapping
        mapping = account.primary_mapping()
        self.selected_mapping_id = mapping.id
        return mapping

    def add_mapping_to_selected_account(self):
        account = self.selected_account()
        if not account:
            return
        used_aliases = {mapping.claude_alias for mapping in account.mappings if mapping.claude_alias != "custom"}
        next_alias = next((alias for alias in ["default", "sonnet", "opus", "haiku"] if alias not in used_aliases), "custom")
        mapping = ModelMapping(id=str(uuid.uuid4()), claude_alias=next_alias, custom_model_name="", model_name=DEFAULT_MODEL, weight=1, enabled=True)
        account.mappings.append(mapping)
        refresh_account_status(account)
        self.selected_mapping_id = mapping.id
        self.store.save()
        self.refresh_all()
        self.log(f"已为 {account.name} 新增映射。")

    def add_account(self):
        account = Account(str(uuid.uuid4()), "新的 NVIDIA 账号", safe_env_name("NVIDIA_ACCOUNT"))
        account.mappings.append(ModelMapping(id=str(uuid.uuid4()), claude_alias="default", model_name=DEFAULT_MODEL))
        self.store.accounts.append(account)
        self.selected_account_id = account.id
        self.selected_mapping_id = account.primary_mapping().id
        self.store.save()
        self.refresh_all()
        self.log("已创建新账号草稿，请在右侧填写 Key 并保存。")

    def load_selected_account(self):
        account = self.selected_account()
        mapping = self.selected_mapping()
        if not account:
            self.name_var.set("")
            self.key_var.set("")
            self.alias_var.set("default")
            self.custom_var.set("")
            self.model_var.set(DEFAULT_MODEL)
            self.weight_var.set("1")
            self.enabled_var.set(True)
            self.editing_label.configure(text="未选择映射")
            return
        self.name_var.set(account.name)
        self.key_var.set(get_user_env(account.env_var))
        self.alias_var.set(mapping.claude_alias)
        self.alias_menu.set(CLAUDE_ALIAS_LABELS.get(mapping.claude_alias, "Default"))
        self.custom_var.set(mapping.custom_model_name)
        self.model_var.set(mapping.model_name)
        self.weight_var.set(str(mapping.weight))
        self.enabled_var.set(mapping.enabled)
        self.update_custom_state()
        self.editing_label.configure(text=f"正在编辑：{account.name} / {claude_model_name(mapping)} -> {mapping.model_name}")

    def on_alias_label_changed(self, label):
        for alias, alias_label in CLAUDE_ALIAS_LABELS.items():
            if alias_label == label:
                self.alias_var.set(alias)
                break
        self.update_custom_state()

    def update_custom_state(self):
        self.custom_entry.configure(state="normal" if self.alias_var.get() == "custom" else "disabled")

    def save_current_account(self):
        account = self.selected_account()
        mapping = self.selected_mapping()
        if not account or not mapping:
            return
        if not self.name_var.get().strip() or not self.key_var.get().strip() or not self.model_var.get().strip():
            messagebox.showerror("输入不完整", "请填写账号名称、API Key 和 NVIDIA 实际模型。")
            return
        if self.alias_var.get() == "custom" and not self.custom_var.get().strip():
            messagebox.showerror("输入不完整", "Custom 档位需要填写自定义 Claude 模型名。")
            return
        try:
            weight = max(1, int(self.weight_var.get()))
        except ValueError:
            messagebox.showerror("输入错误", "权重必须是数字。")
            return
        new_alias = self.alias_var.get()
        if new_alias != "custom":
            for item in account.mappings:
                if item.id != mapping.id and item.claude_alias == new_alias:
                    messagebox.showerror("重复映射", f"当前账号下已经有 {CLAUDE_ALIAS_LABELS.get(new_alias, new_alias)} 映射。")
                    return
        account.name = self.name_var.get().strip()
        mapping.claude_alias = new_alias
        mapping.custom_model_name = self.custom_var.get().strip() if new_alias == "custom" else ""
        mapping.model_name = self.model_var.get().strip()
        mapping.weight = weight
        mapping.enabled = self.enabled_var.get()
        set_user_env(account.env_var, self.key_var.get().strip())
        self.store.save()
        self.refresh_all()
        self.log(f"已保存但尚未应用：{account.name} / {claude_model_name(mapping)} -> {mapping.model_name}。如需 Claude Code 生效，请点“应用配置并重启”或“保存并应用配置”。")

    def save_and_apply_current_account(self):
        self.save_current_account()
        self.apply_config()

    def delete_account(self):
        account = self.selected_account()
        if not account:
            return
        self.delete_account_by_id(account.id)

    def delete_current_mapping(self):
        account = self.selected_account()
        mapping = self.selected_mapping()
        if not account or not mapping:
            return
        if len(account.mappings) <= 1:
            messagebox.showinfo("不能删除", "每个账号至少保留一条映射；你可以改它或删除整个账号。")
            return
        if not messagebox.askyesno("确认删除映射", f"确定删除 {claude_model_name(mapping)} -> {mapping.model_name} 吗？"):
            return
        account.mappings = [item for item in account.mappings if item.id != mapping.id]
        self.selected_mapping_id = account.primary_mapping().id
        self.store.save()
        self.refresh_all()
        self.log(f"已删除映射：{account.name}")

    def delete_account_by_id(self, account_id):
        account = next((item for item in self.store.accounts if item.id == account_id), None)
        if not account:
            return
        if not messagebox.askyesno("确认删除", f"确定删除 {account.name} 吗？不会删除用户环境变量。"):
            return
        self.store.accounts = [item for item in self.store.accounts if item.id != account.id]
        self.selected_account_id = self.store.accounts[0].id if self.store.accounts else None
        selected = self.selected_account()
        self.selected_mapping_id = selected.primary_mapping().id if selected else None
        self.store.save()
        self.refresh_all()
        self.log(f"已删除：{account.name}")

    def account_by_id(self, account_id):
        return next((item for item in self.store.accounts if item.id == account_id), None)

    def run_background(self, start_message, worker, success_title=None):
        self.log(start_message)
        thread = threading.Thread(target=self.background_runner, args=(worker, success_title), daemon=True)
        thread.start()

    def background_runner(self, worker, success_title):
        try:
            message = worker()
            self.after(0, self.refresh_all)
            self.after(0, self.log, message)
            if success_title:
                self.after(0, messagebox.showinfo, success_title, message)
        except Exception as exc:
            message = str(exc)
            self.after(0, self.refresh_all)
            self.after(0, self.log, f"后台任务失败：{message}")
            self.after(0, messagebox.showerror, "操作失败", message)

    def apply_config(self):
        if not [a for a in self.store.accounts if a.enabled]:
            messagebox.showerror("无法应用", "至少需要启用一个账号。")
            return
        self.run_background("开始应用配置并重启 LiteLLM。", self.apply_config_worker, None)

    def apply_config_worker(self):
        try:
            set_user_env("NVIDIA_NIM_API_BASE", NVIDIA_API_BASE)
            apply_claude_default_envs(self.store.accounts)
            backup = backup_config()
            CONFIG_PATH.write_text(generate_litellm_config(self.store.accounts), encoding="utf-8")
            self.store.save()
            messages = [f"已写入 LiteLLM 配置：{CONFIG_PATH}"]
            if backup:
                messages.append(f"旧配置已备份：{backup}")
            restart_output = restart_litellm()
            if restart_output:
                messages.append(restart_output)
            models = self.get_gateway_models()
            messages.append("LiteLLM 可用：" + "、".join(models))
            return "\n".join(messages)
        except Exception:
            raise

    def verify_gateway(self):
        self.run_background("开始验证 LiteLLM。", self.verify_gateway_worker, "验证完成")

    def get_gateway_models(self):
        master_key = get_master_key()
        headers = {"Authorization": f"Bearer {master_key}"} if master_key else {}
        data = request_json(f"{GATEWAY_URL}/v1/models", headers=headers, timeout=10)
        return [item["id"] for item in data.get("data", [])]

    def verify_gateway_worker(self):
        models = self.get_gateway_models()
        return "LiteLLM 可用：" + "、".join(models)

    def check_selected_account(self):
        account = self.selected_account()
        mapping = self.selected_mapping()
        if account and mapping:
            self.run_background(f"开始检测映射：{account.name} / {claude_model_name(mapping)}", lambda: self.check_account_worker(account.id, mapping.id), "检测完成")

    def check_all_accounts(self):
        if not self.store.accounts:
            messagebox.showinfo("没有账号", "账号池为空。")
            return
        self.run_background("开始检测全部账号。", self.check_all_accounts_worker, "检测完成")

    def check_all_accounts_worker(self):
        ok_count = 0
        total = 0
        for account in self.store.accounts:
            for mapping in [item for item in account.mappings if item.enabled]:
                total += 1
                ok, _message = self.check_account_by_object(account, mapping)
                if ok:
                    ok_count += 1
        return f"{ok_count}/{total} 条映射可用。"

    def check_account_worker(self, account_id, mapping_id):
        account = self.account_by_id(account_id)
        if not account:
            return "账号不存在，可能已被删除。"
        mapping = next((item for item in account.mappings if item.id == mapping_id), None)
        if not mapping:
            return "映射不存在，可能已被删除。"
        _ok, message = self.check_account_by_object(account, mapping)
        return message

    def check_account_by_object(self, account, mapping):
        key = get_user_env(account.env_var)
        if not key:
            mapping.last_checked_at = now_text()
            mapping.last_status = "不可用：缺少 Key"
            mapping.suspected_rate_limit = False
            refresh_account_status(account)
            self.store.save()
            return False, f"{account.name} 不可用：缺少 Key。"
        try:
            body = {
                "model": nvidia_model_id(mapping.model_name),
                "messages": [{"role": "user", "content": "请只回复 OK"}],
                "max_tokens": 8,
                "temperature": 0,
            }
            headers = {"Authorization": f"Bearer {key}", "Content-Type": "application/json"}
            request_json(f"{NVIDIA_API_BASE}/chat/completions", headers=headers, body=body, timeout=45)
            mapping.estimated_requests += 1
            mapping.last_status = "可用"
            mapping.suspected_rate_limit = False
            mapping.last_checked_at = now_text()
            refresh_account_status(account)
            self.store.save()
            return True, f"{account.name} 可用。"
        except urllib.error.HTTPError as exc:
            mapping.last_checked_at = now_text()
            mapping.suspected_rate_limit = exc.code == 429
            if exc.code == 404:
                mapping.last_status = "不可用：模型不存在或无权限"
            elif exc.code == 429:
                mapping.last_status = "不可用：疑似限流"
            else:
                mapping.last_status = f"不可用：HTTP {exc.code}"
            refresh_account_status(account)
            self.store.save()
            return False, f"{account.name} {mapping.last_status}。当前检测的 NVIDIA 模型：{mapping.model_name}"
        except Exception as exc:
            mapping.last_checked_at = now_text()
            mapping.last_status = "不可用"
            refresh_account_status(account)
            self.store.save()
            return False, f"{account.name} 不可用：{exc}"

    def log(self, message):
        self.log_box.insert("end", f"[{now_text()}] {message}\n")
        self.log_box.see("end")
        self.update_idletasks()


def main():
    app = AccountManagerApp()
    app.mainloop()


if __name__ == "__main__":
    main()

