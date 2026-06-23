import customtkinter as ctk
import os
import queue
import threading
import pyperclip
import json
from datetime import datetime
from tkinter import messagebox
from api_client import RiotTournamentClient, should_stop_after_riot_failure, supabase_sign_in
from discord_helper import send_discord_webhook
import config_manager

ctk.set_appearance_mode("Dark")
ctk.set_default_color_theme("blue")

APP_FONT = "Malgun Gothic"
HEADER_FONT = (APP_FONT, 22, "bold")
SUBHEADER_FONT = (APP_FONT, 16, "bold")
BODY_FONT = (APP_FONT, 14)
SMALL_FONT = (APP_FONT, 11)
DISPLAY_FONT = (APP_FONT, 28, "bold")
CAPTION_FONT = (APP_FONT, 12, "bold")

BUTTON_HEIGHT_STD = 40
INPUT_HEIGHT = 35

HUD_BG = "#040812"
HUD_PANEL = "#07111F"
HUD_PANEL_ALT = "#0B1728"
HUD_INPUT = "#0A1524"
HUD_LOG_BG = "#050A14"
HUD_ACTION_BG = "#060D19"
HUD_STATUS_BG = "#081425"
HUD_LINE = "#24344E"
HUD_LINE_SOFT = "#152237"
HUD_PRIMARY = "#0F3457"
HUD_PRIMARY_HOVER = "#154A78"
HUD_GOLD = "#D5B45B"
HUD_GOLD_DIM = "#4C3F22"
HUD_GOLD_SOFT = "#2A2418"
HUD_GOLD_HOVER = "#E4C66C"
HUD_CYAN = "#38C7E8"
HUD_TEXT = "#F2F6FF"
HUD_MUTED = "#8EA0B8"
HUD_OK = "#35D18A"
HUD_OK_BG = "#123929"
HUD_OK_HOVER = "#174B36"
HUD_WARN = "#EAC15C"
HUD_DANGER = "#E36A6A"
HUD_DANGER_BG = "#4D2027"
HUD_DANGER_HOVER = "#74303A"

PANEL_STYLE = {
    "fg_color": HUD_PANEL,
    "border_width": 1,
    "border_color": HUD_LINE,
    "corner_radius": 8,
}
ENTRY_STYLE = {
    "fg_color": HUD_INPUT,
    "border_color": HUD_LINE,
    "text_color": HUD_TEXT,
    "placeholder_text_color": HUD_MUTED,
}
TEXTBOX_STYLE = {
    "fg_color": HUD_LOG_BG,
    "border_color": HUD_LINE,
    "text_color": HUD_TEXT,
    "scrollbar_button_color": HUD_LINE,
    "scrollbar_button_hover_color": HUD_GOLD_DIM,
}
COMBO_STYLE = {
    "fg_color": HUD_INPUT,
    "border_color": HUD_LINE,
    "button_color": HUD_LINE,
    "button_hover_color": HUD_GOLD_DIM,
    "dropdown_fg_color": HUD_PANEL_ALT,
    "dropdown_hover_color": HUD_LINE,
    "dropdown_text_color": HUD_TEXT,
    "text_color": HUD_TEXT,
}


def _button_style(kind="primary"):
    styles = {
        "primary": {
            "fg_color": HUD_PRIMARY,
            "hover_color": HUD_PRIMARY_HOVER,
            "border_color": HUD_CYAN,
            "text_color": HUD_TEXT,
        },
        "gold": {
            "fg_color": HUD_GOLD_SOFT,
            "hover_color": HUD_GOLD_DIM,
            "border_color": HUD_GOLD,
            "text_color": HUD_GOLD_HOVER,
        },
        "secondary": {
            "fg_color": HUD_STATUS_BG,
            "hover_color": HUD_PANEL_ALT,
            "border_color": HUD_LINE,
            "text_color": HUD_MUTED,
        },
        "danger": {
            "fg_color": HUD_DANGER_BG,
            "hover_color": HUD_DANGER_HOVER,
            "border_color": HUD_DANGER,
            "text_color": HUD_TEXT,
        },
        "success": {
            "fg_color": HUD_OK_BG,
            "hover_color": HUD_OK_HOVER,
            "border_color": HUD_OK,
            "text_color": HUD_TEXT,
        },
    }
    style = styles.get(kind, styles["primary"]).copy()
    style.update({"border_width": 1, "corner_radius": 8})
    return style


def _section_title(parent, text):
    return ctk.CTkLabel(parent, text=text, font=SUBHEADER_FONT, text_color=HUD_GOLD)


def _field_label(parent, text):
    return ctk.CTkLabel(parent, text=text, font=BODY_FONT, text_color=HUD_TEXT)


def _caption(parent, text, color=HUD_MUTED):
    return ctk.CTkLabel(parent, text=text, font=CAPTION_FONT, text_color=color)


def _accent_line(parent, color=HUD_GOLD, height=2):
    return ctk.CTkFrame(parent, height=height, fg_color=color, corner_radius=0)


DISPLAY_MESSAGE_REPLACEMENTS = (
    ("Supabase Edge Function", "보안 서버"),
    ("Supabase backend", "보안 서버"),
    ("Supabase request", "보안 서버 요청"),
    ("Supabase Project URL", "보안 서버 URL"),
    ("Supabase anon key", "보안 서버 공개 키"),
    ("signed in to Supabase", "보안 서버에 인증됨"),
    ("Supabase", "보안 서버"),
)


def _display_message(message):
    text = str(message or "")
    for source, replacement in DISPLAY_MESSAGE_REPLACEMENTS:
        text = text.replace(source, replacement)
    return text


BASE_DIR = os.path.dirname(os.path.abspath(__file__))
LEGACY_PRESETS_FILE = os.path.join(BASE_DIR, "presets.json")
PRESETS_FILE = os.path.join(config_manager.DEFAULT_APP_DATA_DIR, "presets.json")
PRESET_PLACEHOLDER = "(프리셋 없음)"
TOURNAMENT_ROUTING_OPTIONS = ["americas", "asia", "europe", "sea"]
LEGAL_NOTICE = (
    "LOL Tournament Code Creator is not endorsed by Riot Games and does not "
    "reflect the views or opinions of Riot Games or anyone officially involved "
    "in producing or managing Riot Games properties. Riot Games and all "
    "associated properties are trademarks or registered trademarks of Riot Games, Inc."
)


def _normalize_action(action):
    if not isinstance(action, dict):
        return None
    name = str(action.get("name") or "").strip()
    api_name = str(action.get("api_name") or name).strip()
    url = str(action.get("url") or "").strip()
    if not name:
        return None
    return {
        "name": name,
        "api_name": api_name or name,
        "url": url,
    }


def _normalize_preset(preset):
    if not isinstance(preset, dict):
        return None
    label = str(preset.get("label") or "").strip()
    actions = [_normalize_action(action) for action in preset.get("actions", [])]
    actions = [action for action in actions if action]
    if not label or not actions:
        return None
    return {"label": label, "actions": actions}


def _read_presets_file(path):
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        if not isinstance(data, list):
            raise ValueError("Preset root must be a list")
        return [preset for preset in (_normalize_preset(item) for item in data) if preset]
    except Exception as e:
        print(f"Error loading presets: {e}")
        return []


def load_presets_file():
    if os.path.exists(PRESETS_FILE):
        return _read_presets_file(PRESETS_FILE)

    if os.path.exists(LEGACY_PRESETS_FILE):
        presets = _read_presets_file(LEGACY_PRESETS_FILE)
        if presets:
            save_presets_file(presets)
        return presets

    return []


def save_presets_file(data):
    try:
        normalized = [preset for preset in (_normalize_preset(item) for item in data) if preset]
        os.makedirs(os.path.dirname(PRESETS_FILE), exist_ok=True)
        with open(PRESETS_FILE, "w", encoding="utf-8") as f:
            json.dump(normalized, f, indent=2, ensure_ascii=False)
            f.write("\n")
        return True
    except Exception as e:
        print(f"Error saving presets: {e}")
        return False


class ManualConfigWindow(ctk.CTkToplevel):
    def __init__(self, parent):
        super().__init__(parent)
        self.title("설정")
        self.geometry("900x820")
        self.minsize(820, 720)
        self.configure(fg_color=HUD_BG)
        self.parent = parent
        self.manual_generation_in_progress = False

        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(0, weight=1)

        self.map_mapping = {
            "소환사의 협곡": "SUMMONERS_RIFT",
            "칼바람 나락": "HOWLING_ABYSS"
        }
        self.pick_mapping = {
            "토너먼트 드래프트": "TOURNAMENT_DRAFT",
            "비공개 선택": "BLIND_PICK",
            "무작위 총력전": "ALL_RANDOM"
        }

        settings_header = ctk.CTkFrame(self, fg_color=HUD_PANEL_ALT, border_width=1, border_color=HUD_GOLD_DIM, corner_radius=8)
        settings_header.pack(fill="x", padx=20, pady=(20, 10))
        _accent_line(settings_header, HUD_GOLD, 2).pack(fill="x", padx=18, pady=(10, 0))
        ctk.CTkLabel(
            settings_header,
            text="운영 설정",
            font=(APP_FONT, 23, "bold"),
            text_color=HUD_GOLD,
        ).pack(anchor="w", padx=18, pady=(10, 0))
        _caption(settings_header, "인증 · 수동 발급 · 프리셋 관리", HUD_CYAN).pack(anchor="w", padx=18, pady=(0, 14))

        self.tab_view = ctk.CTkTabview(
            self,
            fg_color=HUD_PANEL,
            border_width=1,
            border_color=HUD_LINE,
            segmented_button_fg_color=HUD_PANEL_ALT,
            segmented_button_selected_color=HUD_GOLD_DIM,
            segmented_button_selected_hover_color=HUD_GOLD_SOFT,
            segmented_button_unselected_color=HUD_LINE,
            segmented_button_unselected_hover_color=HUD_PANEL_ALT,
            text_color=HUD_TEXT,
        )
        self.tab_view.pack(fill="both", expand=True, padx=20, pady=(0, 20))

        self.tab_general = self.tab_view.add("일반 설정")
        self.tab_manual = self.tab_view.add("수동 생성")
        self.tab_presets = self.tab_view.add("프리셋 관리")
        for tab in (self.tab_general, self.tab_manual, self.tab_presets):
            tab.configure(fg_color=HUD_PANEL)

        self._init_general_tab()
        self._init_manual_tab()
        self._init_presets_tab()

        self._load_current_settings()

    def _init_general_tab(self):
        general_grid = ctk.CTkFrame(self.tab_general, fg_color="transparent")
        general_grid.pack(fill="both", expand=True, padx=14, pady=12)
        general_grid.grid_columnconfigure(0, weight=1, uniform="general")
        general_grid.grid_columnconfigure(1, weight=1, uniform="general")
        general_grid.grid_rowconfigure(0, weight=1)

        auth_panel = ctk.CTkFrame(general_grid, **PANEL_STYLE)
        auth_panel.grid(row=0, column=0, sticky="nsew", padx=(0, 8))

        _section_title(auth_panel, "운영자 인증").pack(anchor="w", padx=18, pady=(14, 8))

        self.switch_stub = ctk.CTkSwitch(
            auth_panel,
            text="테스트 API 사용",
            font=BODY_FONT,
            text_color=HUD_TEXT,
            fg_color=HUD_LINE,
            progress_color=HUD_GOLD,
            button_color=HUD_TEXT,
            button_hover_color=HUD_CYAN,
        )
        self.switch_stub.pack(anchor="w", padx=18, pady=(0, 8))

        self.lbl_auth_status = ctk.CTkLabel(auth_panel, text="인증 상태 확인 중", font=BODY_FONT, text_color=HUD_MUTED)
        self.lbl_auth_status.pack(anchor="w", padx=18, pady=(0, 12))

        self.auth_form_frame = ctk.CTkFrame(auth_panel, fg_color="transparent")
        self.auth_form_frame.pack(fill="x")

        _field_label(self.auth_form_frame, "운영자 이메일").pack(anchor="w", padx=18)
        self.entry_operator_email = ctk.CTkEntry(
            self.auth_form_frame,
            height=INPUT_HEIGHT,
            placeholder_text="operator@example.com",
            **ENTRY_STYLE,
        )
        self.entry_operator_email.pack(fill="x", padx=18, pady=(4, 10))

        _field_label(self.auth_form_frame, "비밀번호").pack(anchor="w", padx=18)
        self.entry_operator_password = ctk.CTkEntry(
            self.auth_form_frame,
            height=INPUT_HEIGHT,
            placeholder_text="처음 인증하거나 다시 인증할 때만 입력",
            **ENTRY_STYLE,
        )
        self.entry_operator_password.configure(show="*")
        self.entry_operator_password.pack(fill="x", padx=18, pady=(4, 10))

        self.routing_label = _field_label(auth_panel, "토너먼트 API 라우팅")
        self.routing_label.pack(anchor="w", padx=18)
        self.combo_routing = ctk.CTkComboBox(
            auth_panel,
            values=TOURNAMENT_ROUTING_OPTIONS,
            height=INPUT_HEIGHT,
            width=180,
            state="readonly",
            **COMBO_STYLE,
        )
        self.combo_routing.pack(anchor="w", padx=18, pady=(4, 12))
        _caption(
            auth_panel,
            "기본값은 현재 검증된 americas입니다. Riot 안내가 있을 때만 변경하세요.",
            HUD_MUTED,
        ).pack(anchor="w", padx=18, pady=(0, 12))

        self.btn_apply_settings = ctk.CTkButton(
            auth_panel,
            text="로그인 및 설정 적용",
            height=BUTTON_HEIGHT_STD,
            command=self.save_general_settings,
            **_button_style("gold"),
        )
        self.btn_apply_settings.pack(fill="x", padx=18, pady=(4, 8))
        self.btn_reauth = ctk.CTkButton(
            auth_panel,
            text="재인증 / 계정 변경",
            height=BUTTON_HEIGHT_STD,
            command=self.show_auth_form,
            **_button_style("secondary"),
        )
        self.btn_logout = ctk.CTkButton(
            auth_panel,
            text="로그아웃",
            height=BUTTON_HEIGHT_STD,
            command=self.logout_operator,
            **_button_style("secondary"),
        )
        self.btn_logout.pack(fill="x", padx=18, pady=(0, 16))

        provider_panel = ctk.CTkFrame(general_grid, **PANEL_STYLE)
        provider_panel.grid(row=0, column=1, sticky="nsew", padx=(8, 0))

        _section_title(provider_panel, "대회 공급자").pack(anchor="w", padx=18, pady=(14, 8))
        provider_readout = ctk.CTkFrame(provider_panel, fg_color=HUD_STATUS_BG, border_width=1, border_color=HUD_LINE_SOFT, corner_radius=8)
        provider_readout.pack(fill="x", padx=18, pady=(0, 12))
        _caption(provider_readout, "등록된 공급자 ID", HUD_MUTED).pack(anchor="w", padx=12, pady=(10, 0))
        self.lbl_provider = ctk.CTkLabel(provider_readout, text="-", font=(APP_FONT, 30, "bold"), text_color=HUD_GOLD)
        self.lbl_provider.pack(anchor="w", padx=12, pady=(0, 10))

        ctk.CTkButton(
            provider_panel,
            text="대회 공급자 새로 등록 (KR)",
            height=BUTTON_HEIGHT_STD,
            command=self.create_new_provider,
            **_button_style("primary"),
        ).pack(fill="x", padx=18, pady=(0, 12))

        _caption(provider_panel, "등록 로그", HUD_CYAN).pack(anchor="w", padx=18, pady=(0, 6))
        self.txt_gen_log = ctk.CTkTextbox(provider_panel, height=170, **TEXTBOX_STYLE)
        self.txt_gen_log.pack(fill="both", expand=True, padx=18, pady=(0, 16))

    def _init_manual_tab(self):
        manual_panel = ctk.CTkFrame(self.tab_manual, **PANEL_STYLE)
        manual_panel.pack(fill="both", expand=True, padx=14, pady=12)

        _section_title(manual_panel, "코드 수동 발급").pack(anchor="w", padx=18, pady=(14, 10))

        self.entry_tourn_name = ctk.CTkEntry(
            manual_panel,
            placeholder_text="토너먼트 이름 (예: 내전 결승전)",
            height=INPUT_HEIGHT,
            **ENTRY_STYLE,
        )
        self.entry_tourn_name.pack(fill="x", padx=18, pady=(0, 10))

        btn_frame = ctk.CTkFrame(manual_panel, fg_color="transparent")
        btn_frame.pack(fill="x", padx=18, pady=(0, 10))

        self.combo_map = ctk.CTkComboBox(
            btn_frame,
            values=list(self.map_mapping.keys()),
            height=INPUT_HEIGHT,
            width=245,
            **COMBO_STYLE,
        )
        self.combo_map.pack(side="left", fill="x", expand=True, padx=(0, 6))
        self.combo_pick = ctk.CTkComboBox(
            btn_frame,
            values=list(self.pick_mapping.keys()),
            height=INPUT_HEIGHT,
            width=245,
            **COMBO_STYLE,
        )
        self.combo_pick.pack(side="left", fill="x", expand=True, padx=(6, 0))

        self.btn_manual_gen = ctk.CTkButton(
            manual_panel,
            text="토너먼트 코드 발급",
            height=BUTTON_HEIGHT_STD,
            font=BODY_FONT,
            command=self.manual_generate,
            **_button_style("gold"),
        )
        self.btn_manual_gen.pack(fill="x", padx=18, pady=(0, 14))

        self.txt_manual_result = ctk.CTkTextbox(manual_panel, height=260, **TEXTBOX_STYLE)
        self.txt_manual_result.pack(fill="both", expand=True, padx=18, pady=(0, 16))

    def _init_presets_tab(self):
        self.edit_presets_data = load_presets_file()
        self.current_editing_index = None

        preset_panel = ctk.CTkFrame(self.tab_presets, **PANEL_STYLE)
        preset_panel.pack(fill="both", expand=True, padx=14, pady=12)

        _section_title(preset_panel, "프리셋 관리").pack(anchor="w", padx=18, pady=(14, 10))
        _field_label(preset_panel, "편집할 프리셋 선택").pack(anchor="w", padx=18)

        selector_frame = ctk.CTkFrame(preset_panel, fg_color="transparent")
        selector_frame.pack(fill="x", padx=18, pady=(4, 10))

        self.preset_names = [p["label"] for p in self.edit_presets_data]
        self.combo_presets = ctk.CTkComboBox(
            selector_frame,
            values=self.preset_names or [PRESET_PLACEHOLDER],
            command=self._on_preset_select,
            height=INPUT_HEIGHT,
            width=260,
            **COMBO_STYLE,
        )
        self.combo_presets.pack(side="left", fill="x", expand=True, padx=(0, 6))

        ctk.CTkButton(
            selector_frame,
            text="새 프리셋",
            width=96,
            height=INPUT_HEIGHT,
            command=self.add_preset,
            **_button_style("primary"),
        ).pack(side="left", padx=3)
        ctk.CTkButton(
            selector_frame,
            text="삭제",
            width=72,
            height=INPUT_HEIGHT,
            command=self.delete_selected_preset,
            **_button_style("danger"),
        ).pack(side="left", padx=(3, 0))

        self.frame_edit = ctk.CTkFrame(preset_panel, fg_color=HUD_PANEL_ALT, border_width=1, border_color=HUD_LINE_SOFT, corner_radius=8)
        self.frame_edit.pack(fill="both", expand=True, padx=18, pady=(0, 12))

        _field_label(self.frame_edit, "프리셋 이름").pack(anchor="w", padx=12, pady=(12, 0))
        self.entry_preset_label = ctk.CTkEntry(self.frame_edit, height=INPUT_HEIGHT, **ENTRY_STYLE)
        self.entry_preset_label.pack(fill="x", padx=12, pady=(4, 8))

        action_header = ctk.CTkFrame(self.frame_edit, fg_color="transparent")
        action_header.pack(fill="x", padx=12, pady=(8, 0))
        _field_label(action_header, "경기별 발급 설정").pack(side="left")
        ctk.CTkButton(
            action_header,
            text="경기 추가",
            width=96,
            height=30,
            command=self.add_action_row,
            **_button_style("secondary"),
        ).pack(side="right")

        self.scroll_actions = ctk.CTkScrollableFrame(
            self.frame_edit,
            height=300,
            fg_color=HUD_ACTION_BG,
            border_width=1,
            border_color=HUD_LINE,
            scrollbar_button_color=HUD_LINE,
            scrollbar_button_hover_color=HUD_GOLD_DIM,
        )
        self.scroll_actions.pack(fill="both", expand=True, padx=12, pady=(6, 10))

        self.action_entries = []

        ctk.CTkButton(
            preset_panel,
            text="프리셋 저장",
            height=BUTTON_HEIGHT_STD,
            command=self.save_preset_changes,
            **_button_style("success"),
        ).pack(fill="x", padx=18, pady=(0, 16))

        if self.preset_names:
            self.combo_presets.set(self.preset_names[0])
            self._on_preset_select(self.preset_names[0])
        else:
            self.combo_presets.set(PRESET_PLACEHOLDER)
            self._clear_preset_editor()

    def _on_preset_select(self, choice):
        selected = next((p for p in self.edit_presets_data if p["label"] == choice), None)
        if not selected:
            return

        self.current_editing_index = self.edit_presets_data.index(selected)

        self.entry_preset_label.delete(0, "end")
        self.entry_preset_label.insert(0, selected["label"])
        self._clear_action_rows()

        for action in selected["actions"]:
            self.add_action_row(action)

    def _clear_preset_editor(self):
        self.current_editing_index = None
        self.entry_preset_label.delete(0, "end")
        self._clear_action_rows()

    def _clear_action_rows(self):
        for widget in self.scroll_actions.winfo_children():
            widget.destroy()
        self.action_entries = []

    def _refresh_preset_selector(self, selected_index=None):
        self.preset_names = [p["label"] for p in self.edit_presets_data]
        self.combo_presets.configure(values=self.preset_names or [PRESET_PLACEHOLDER])
        if not self.edit_presets_data:
            self.combo_presets.set(PRESET_PLACEHOLDER)
            self._clear_preset_editor()
            return

        index = selected_index if selected_index is not None else self.current_editing_index
        if index is None:
            index = 0
        index = max(0, min(index, len(self.edit_presets_data) - 1))
        self.combo_presets.set(self.edit_presets_data[index]["label"])
        self._on_preset_select(self.edit_presets_data[index]["label"])

    def add_preset(self):
        next_number = len(self.edit_presets_data) + 1
        existing = {preset["label"] for preset in self.edit_presets_data}
        label = f"새 프리셋 {next_number}"
        while label in existing:
            next_number += 1
            label = f"새 프리셋 {next_number}"
        self.edit_presets_data.append({
            "label": label,
            "actions": [{"name": "새 경기", "api_name": "New_Match", "url": ""}]
        })
        self._refresh_preset_selector(len(self.edit_presets_data) - 1)

    def delete_selected_preset(self):
        if self.current_editing_index is None:
            self.parent.log("삭제할 프리셋이 없습니다.", HUD_WARN)
            return
        label = self.edit_presets_data[self.current_editing_index]["label"]
        if not messagebox.askyesno("프리셋 삭제", f"'{label}' 프리셋을 삭제할까요?"):
            return
        del self.edit_presets_data[self.current_editing_index]
        if save_presets_file(self.edit_presets_data):
            self.parent.refresh_presets()
            self.parent.log("프리셋이 삭제되었습니다.", HUD_OK)
            self._refresh_preset_selector(0)
        else:
            self.parent.log("프리셋 삭제 내용을 저장하지 못했습니다.", HUD_DANGER)

    def add_action_row(self, action=None):
        action = action or {"name": "", "api_name": "", "url": ""}
        frame = ctk.CTkFrame(self.scroll_actions, fg_color=HUD_STATUS_BG, border_width=1, border_color=HUD_LINE_SOFT, corner_radius=8)
        frame.pack(fill="x", pady=6)

        header = ctk.CTkFrame(frame, fg_color="transparent")
        header.pack(fill="x", padx=8, pady=(8, 2))
        ctk.CTkLabel(header, text="경기", font=(APP_FONT, 12, "bold"), text_color=HUD_GOLD).pack(side="left")
        ctk.CTkButton(
            header,
            text="삭제",
            width=58,
            height=26,
            command=lambda: self.remove_action_row(frame),
            **_button_style("danger"),
        ).pack(side="right")

        ctk.CTkLabel(frame, text="화면 표시 이름 / 디스코드 제목", font=(APP_FONT, 12), text_color=HUD_TEXT).pack(anchor="w", padx=8)
        name_entry = ctk.CTkEntry(frame, height=INPUT_HEIGHT, placeholder_text="예: 1경기", **ENTRY_STYLE)
        name_entry.pack(fill="x", padx=8, pady=(0, 6))
        name_entry.insert(0, action.get("name", ""))

        ctk.CTkLabel(frame, text="라이엇에 등록할 토너먼트 이름", font=(APP_FONT, 12), text_color=HUD_TEXT).pack(anchor="w", padx=8)
        api_name_entry = ctk.CTkEntry(frame, height=INPUT_HEIGHT, placeholder_text="비우면 표시 이름 사용", **ENTRY_STYLE)
        api_name_entry.pack(fill="x", padx=8, pady=(0, 6))
        api_name_entry.insert(0, action.get("api_name") or action.get("name", ""))

        ctk.CTkLabel(frame, text="디스코드 알림 URL", font=(APP_FONT, 12), text_color=HUD_TEXT).pack(anchor="w", padx=8)
        url_entry = ctk.CTkEntry(frame, height=INPUT_HEIGHT, placeholder_text="https://discord.com/api/webhooks/...", **ENTRY_STYLE)
        url_entry.pack(fill="x", padx=8, pady=(0, 8))
        url_entry.insert(0, action.get("url", ""))

        self.action_entries.append({
            "frame": frame,
            "name_entry": name_entry,
            "api_name_entry": api_name_entry,
            "url_entry": url_entry,
        })

    def remove_action_row(self, frame):
        self.action_entries = [entry for entry in self.action_entries if entry["frame"] is not frame]
        frame.destroy()

    def save_preset_changes(self):
        if self.current_editing_index is None:
            self.parent.log("저장할 프리셋이 없습니다. 새 프리셋을 먼저 만드세요.", HUD_WARN)
            return

        new_label = self.entry_preset_label.get().strip()
        if not new_label:
            self.parent.log("프리셋 이름을 입력하세요.", HUD_WARN)
            return

        actions = []
        for item in self.action_entries:
            name = item["name_entry"].get().strip()
            api_name = item["api_name_entry"].get().strip() or name
            url = item["url_entry"].get().strip()
            if not name and not api_name and not url:
                continue
            if not name:
                self.parent.log("경기 이름을 입력하세요.", HUD_WARN)
                return
            actions.append({"name": name, "api_name": api_name, "url": url})

        if not actions:
            self.parent.log("프리셋에는 최소 1개 경기가 필요합니다.", HUD_WARN)
            return

        self.edit_presets_data[self.current_editing_index] = {
            "label": new_label,
            "actions": actions,
        }

        if save_presets_file(self.edit_presets_data):
            self.parent.log("프리셋이 저장되었습니다.", HUD_OK)
            self.parent.refresh_presets()
            self._refresh_preset_selector(self.current_editing_index)
        else:
            self.parent.log("프리셋을 저장하지 못했습니다.", HUD_DANGER)

    def _load_current_settings(self):
        config = config_manager.load_config()
        if config.get("use_stub", True):
            self.switch_stub.select()
        else:
            self.switch_stub.deselect()
        self.entry_operator_email.delete(0, "end")
        self.entry_operator_email.insert(0, config.get("supabase_user_email", ""))
        self.entry_operator_password.delete(0, "end")
        self.combo_routing.set(config.get("routing_value", "americas"))
        self._update_auth_status(config)

        pid = config.get("provider_id")
        self.lbl_provider.configure(text=str(pid) if pid else "-")

    def _ui_insert(self, widget, text):
        self.parent.call_on_ui(widget.insert, "end", text)

    def _ui_configure(self, widget, **kwargs):
        self.parent.call_on_ui(widget.configure, **kwargs)

    def _set_auth_form_visible(self, visible, signed_in=False):
        if not hasattr(self, "auth_form_frame"):
            return

        if visible:
            if not self.auth_form_frame.winfo_ismapped():
                self.auth_form_frame.pack(fill="x", before=self.routing_label)
            label = "재인증 및 설정 적용" if signed_in else "로그인 및 설정 적용"
            self.btn_apply_settings.configure(text=label)
            self.btn_reauth.pack_forget()
            if signed_in:
                if not self.btn_logout.winfo_ismapped():
                    self.btn_logout.pack(fill="x", padx=18, pady=(0, 16))
            else:
                self.btn_logout.pack_forget()
            return

        self.entry_operator_password.delete(0, "end")
        self.auth_form_frame.pack_forget()
        self.btn_apply_settings.configure(text="설정 적용")
        if signed_in:
            if not self.btn_logout.winfo_ismapped():
                self.btn_logout.pack(fill="x", padx=18, pady=(0, 16))
            if not self.btn_reauth.winfo_ismapped():
                self.btn_reauth.pack(fill="x", padx=18, pady=(0, 8), before=self.btn_logout)
        else:
            self.btn_reauth.pack_forget()
            self.btn_logout.pack_forget()

    def show_auth_form(self):
        config = config_manager.load_config()
        signed_in = bool(config.get("supabase_access_token"))
        self._set_auth_form_visible(True, signed_in=signed_in)
        self.entry_operator_email.delete(0, "end")
        self.entry_operator_email.insert(0, config.get("supabase_user_email", ""))
        self.entry_operator_password.delete(0, "end")
        self.entry_operator_password.focus_set()
        email = config.get("supabase_user_email", "")
        status_text = f"재인증 대기: {email}" if email else "재인증 대기"
        self.lbl_auth_status.configure(text=status_text, text_color=HUD_WARN)

    def _update_auth_status(self, config=None):
        config = config or config_manager.load_config()
        email = config.get("supabase_user_email", "")
        signed_in = bool(config.get("supabase_access_token"))
        if signed_in and email:
            self.lbl_auth_status.configure(text=f"인증됨: {email}", text_color=HUD_OK)
            self._set_auth_form_visible(False, signed_in=True)
        elif email:
            self.lbl_auth_status.configure(text=f"인증 필요: {email}", text_color=HUD_WARN)
            self._set_auth_form_visible(True, signed_in=False)
        else:
            self.lbl_auth_status.configure(text="인증 필요", text_color=HUD_MUTED)
            self._set_auth_form_visible(True, signed_in=False)

    def logout_operator(self):
        config = config_manager.load_config()
        config["supabase_access_token"] = ""
        config["supabase_refresh_token"] = ""
        config["provider_id"] = None
        config_manager.save_config(config)
        self.entry_operator_password.delete(0, "end")
        self.parent.init_client()
        self.parent._update_dashboard_metrics()
        self._update_auth_status(config)
        self.lbl_provider.configure(text="-")
        self.txt_gen_log.insert("end", "로그아웃되었습니다.\n")

    def save_general_settings(self):
        use_stub = bool(self.switch_stub.get())
        routing_value = self.combo_routing.get().strip().lower() or "americas"
        if routing_value not in TOURNAMENT_ROUTING_OPTIONS:
            routing_value = "americas"
        supabase_settings = config_manager.get_supabase_client_settings()
        supabase_url = supabase_settings["supabase_url"]
        supabase_anon_key = supabase_settings["supabase_anon_key"]
        supabase_client_id = config_manager.get_supabase_client_id(supabase_settings)
        operator_email = self.entry_operator_email.get().strip()
        operator_password = self.entry_operator_password.get()

        if not config_manager.is_valid_supabase_url(supabase_url):
            self.parent.log("보안 서버 정보가 프로그램에 포함되어 있지 않습니다.", HUD_DANGER)
            self.txt_gen_log.insert("end", "저장하지 못했습니다: 프로그램에 보안 서버 URL이 없습니다.\n")
            return
        if not supabase_anon_key:
            self.parent.log("보안 서버 정보가 프로그램에 포함되어 있지 않습니다.", HUD_DANGER)
            self.txt_gen_log.insert("end", "저장하지 못했습니다: 프로그램에 보안 서버 공개 키가 없습니다.\n")
            return

        config = config_manager.load_config()
        access_token = config.get("supabase_access_token", "")
        refresh_token = config.get("supabase_refresh_token", "")
        previous_user_email = config.get("supabase_user_email", "")
        user_email = operator_email or previous_user_email
        auth_config_changed = (
            supabase_client_id != config.get("supabase_client_id", "")
            or user_email != previous_user_email
        )

        if operator_password:
            login_result = supabase_sign_in(
                supabase_url,
                supabase_anon_key,
                operator_email,
                operator_password,
            )
            if not login_result.get("success"):
                self.parent.log("운영자 인증 실패", HUD_DANGER)
                self.txt_gen_log.insert("end", f"저장하지 못했습니다: {_display_message(login_result.get('error'))}\n")
                return
            access_token = login_result.get("access_token", "")
            refresh_token = login_result.get("refresh_token", "")
            user_email = login_result.get("user_email", operator_email)
        elif auth_config_changed:
            self.parent.log("다시 로그인해야 합니다.", HUD_DANGER)
            self.txt_gen_log.insert("end", "저장하지 못했습니다: 계정 또는 프로그램 설정이 바뀌었습니다. 다시 로그인해 주세요.\n")
            return
        elif not access_token:
            self.parent.log("로그인이 필요합니다.", HUD_DANGER)
            self.txt_gen_log.insert("end", "저장하지 못했습니다: 비밀번호를 입력해 로그인해 주세요.\n")
            return

        provider_config_changed = (
            use_stub != config.get("use_stub", True)
            or routing_value != config.get("routing_value", "americas")
            or supabase_client_id != config.get("supabase_client_id", "")
            or user_email != config.get("supabase_user_email", "")
        )
        config["use_stub"] = use_stub
        config["routing_value"] = routing_value
        config["api_transport"] = "supabase"
        config["supabase_url"] = supabase_url
        config["supabase_anon_key"] = supabase_anon_key
        config["supabase_client_id"] = supabase_client_id
        config["supabase_access_token"] = access_token
        config["supabase_refresh_token"] = refresh_token
        config["supabase_user_email"] = user_email
        if provider_config_changed:
            config["provider_id"] = None

        config_manager.save_config(config)
        self.entry_operator_password.delete(0, "end")
        self._update_auth_status(config)

        self.parent.init_client()
        self.parent._update_dashboard_metrics()
        self.parent.log("설정을 저장했습니다.", HUD_OK)

        self.lbl_provider.configure(text=str(config.get("provider_id") or "-"))
        if provider_config_changed:
            self.txt_gen_log.insert("end", "연결 정보가 바뀌어 대회 공급자 ID를 비웠습니다. 새로 등록해 주세요.\n")
        self.txt_gen_log.insert("end", "설정을 저장했습니다.\n")

    def create_new_provider(self):
        if not self.parent.client:
            self.txt_gen_log.insert("end", "API 연결이 준비되지 않았습니다.\n")
            return

        def run():
            config = config_manager.load_config()
            self._ui_insert(self.txt_gen_log, "대회 공급자를 등록하는 중...\n")
            res = self.parent.client.create_provider(
                region=config.get("region", "KR"),
            )
            if res["success"]:
                pid = res["data"]
                self.parent.provider_id = pid

                conf = config_manager.load_config()
                conf["provider_id"] = pid
                config_manager.save_config(conf)

                self._ui_configure(self.lbl_provider, text=str(pid))
                self._ui_insert(self.txt_gen_log, f"대회 공급자 등록 완료: {pid}\n")
                self.parent.call_on_ui(self.parent._update_dashboard_metrics)
            else:
                self._ui_insert(self.txt_gen_log, f"대회 공급자 등록 실패: {_display_message(res['error'])}\n")
        threading.Thread(target=run, daemon=True).start()

    def manual_generate(self):
        if self.manual_generation_in_progress:
            return
        if not self.parent.client:
            self.txt_manual_result.insert("end", "API 연결이 준비되지 않았습니다.\n")
            return
        if not self.parent.provider_id:
            self.txt_manual_result.insert("end", "대회 공급자 ID가 없습니다.\n")
            return

        t_name = self.entry_tourn_name.get().strip() or "수동 생성 토너먼트"
        map_val = self.map_mapping.get(self.combo_map.get(), "SUMMONERS_RIFT")
        pick_val = self.pick_mapping.get(self.combo_pick.get(), "TOURNAMENT_DRAFT")
        self.manual_generation_in_progress = True
        self.btn_manual_gen.configure(state="disabled", text="발급 중...")

        def run():
            try:
                self._ui_insert(self.txt_manual_result, f"토너먼트 등록 중: {t_name}\n")
                t_res = self.parent.client.create_tournament(self.parent.provider_id, t_name)
                if not t_res["success"]:
                    self._ui_insert(self.txt_manual_result, f"토너먼트 등록 실패: {_display_message(t_res['error'])}\n")
                    return

                tid = t_res["data"]
                self._ui_insert(self.txt_manual_result, f"토너먼트 ID: {tid}\n")

                c_res = self.parent.client.create_codes(tid, count=1, map_type=map_val, pick_type=pick_val)
                if c_res["success"]:
                    code = c_res["data"][0]
                    self._ui_insert(self.txt_manual_result, f"코드 발급 완료:\n{code}\n")
                    try:
                        pyperclip.copy(code)
                        self._ui_insert(self.txt_manual_result, "(클립보드에 복사됨)\n")
                    except Exception:
                        self._ui_insert(self.txt_manual_result, "(클립보드 복사 실패)\n")
                else:
                    self._ui_insert(self.txt_manual_result, f"코드 발급 실패: {_display_message(c_res['error'])}\n")
            finally:
                self.manual_generation_in_progress = False
                self.parent.call_on_ui(self.btn_manual_gen.configure, state="normal", text="토너먼트 코드 발급")

        threading.Thread(target=run, daemon=True).start()


class LoLPresetApp(ctk.CTk):
    def __init__(self):
        super().__init__()
        self.title("LOL 토너먼트 코드 콘솔")
        self.geometry("1040x720")
        self.minsize(920, 640)
        self.configure(fg_color=HUD_BG)

        self.ui_queue = queue.Queue()
        self.client = None
        self.provider_id = None
        self.presets = []
        self.preset_cards = []
        self.controls_enabled = True
        self.latest_status_color = HUD_MUTED

        self._init_ui()
        self._drain_ui_queue()
        self.init_client()
        self.refresh_presets()

    def init_client(self):
        config = config_manager.load_config()
        config["api_transport"] = "supabase"
        use_stub = config.get("use_stub", True)
        self.provider_id = config.get("provider_id")

        warnings = config_manager.production_config_warnings(config)
        if warnings:
            self.client = None
            self.log(f"보안 서버 설정을 확인해 주세요: {_display_message(warnings[0])}", HUD_DANGER)
            self._update_dashboard_metrics()
            return
        try:
            self.client = RiotTournamentClient(
                use_stub=use_stub,
                platform_routing=config.get("routing_value", "americas"),
                supabase_url=config.get("supabase_url", ""),
                supabase_anon_key=config.get("supabase_anon_key", ""),
                supabase_access_token=config.get("supabase_access_token", ""),
                supabase_refresh_token=config.get("supabase_refresh_token", ""),
                supabase_function_name=config_manager.get_supabase_client_settings()["supabase_function_name"],
                on_session_refresh=self._save_refreshed_supabase_session,
            )
            mode_text = "테스트 API" if use_stub else "라이브 API"
            self.log(f"API 연결됨: {mode_text}", HUD_OK if use_stub else HUD_WARN)
            self._update_dashboard_metrics()
        except Exception as e:
            self.client = None
            self.log(f"API 연결 실패: {e}", HUD_DANGER)
            self._update_dashboard_metrics()

    def _save_refreshed_supabase_session(self, session):
        config = config_manager.load_config()
        config["supabase_access_token"] = session.get("access_token", "")
        config["supabase_refresh_token"] = session.get("refresh_token") or config.get("supabase_refresh_token", "")
        config["supabase_user_email"] = session.get("user_email") or config.get("supabase_user_email", "")
        config["supabase_client_id"] = config_manager.get_supabase_client_id()
        config_manager.save_config(config)

    def _update_dashboard_metrics(self):
        if not hasattr(self, "mode_metric"):
            return
        config = config_manager.load_config()
        use_stub = config.get("use_stub", True)
        mode_text = "테스트" if use_stub else "라이브"
        auth_text = "인증됨" if config.get("supabase_access_token") else "인증 필요"
        provider_text = str(config.get("provider_id") or "-")
        preset_count = len(self.presets)

        self.mode_metric.configure(text=mode_text, text_color=HUD_OK if use_stub else HUD_WARN)
        self.provider_metric.configure(text=provider_text, text_color=HUD_TEXT if provider_text != "-" else HUD_WARN)
        self.preset_metric.configure(text=str(preset_count), text_color=HUD_CYAN)
        self.auth_metric.configure(text=auth_text, text_color=HUD_OK if auth_text == "인증됨" else HUD_WARN)

    def _init_ui(self):
        self.shell = ctk.CTkFrame(self, fg_color=HUD_BG)
        self.shell.pack(fill="both", expand=True, padx=18, pady=18)

        self.header_frame = ctk.CTkFrame(
            self.shell,
            fg_color=HUD_PANEL_ALT,
            border_width=1,
            border_color=HUD_GOLD_DIM,
            corner_radius=8,
        )
        self.header_frame.pack(fill="x", pady=(0, 14))
        _accent_line(self.header_frame, HUD_GOLD, 2).pack(fill="x", padx=18, pady=(12, 0))

        title_row = ctk.CTkFrame(self.header_frame, fg_color="transparent")
        title_row.pack(fill="x", padx=18, pady=(10, 12))
        title_row.grid_columnconfigure(0, weight=1)

        title_stack = ctk.CTkFrame(title_row, fg_color="transparent")
        title_stack.grid(row=0, column=0, sticky="w")
        ctk.CTkLabel(
            title_stack,
            text="LOL 토너먼트 코드 콘솔",
            font=DISPLAY_FONT,
            text_color=HUD_GOLD,
        ).pack(anchor="w")
        _caption(title_stack, "대회 코드 발급 운영", HUD_CYAN).pack(anchor="w", pady=(2, 0))

        status_stack = ctk.CTkFrame(title_row, fg_color="transparent")
        status_stack.grid(row=0, column=1, sticky="e")
        self.status_pill = ctk.CTkFrame(
            status_stack,
            fg_color=HUD_PANEL,
            border_width=1,
            border_color=HUD_LINE_SOFT,
            corner_radius=8,
        )
        self.status_pill.pack(anchor="e", fill="x")
        self.status_label = ctk.CTkLabel(
            self.status_pill,
            text="초기화 중...",
            font=BODY_FONT,
            text_color=HUD_MUTED,
            wraplength=380,
        )
        self.status_label.pack(padx=14, pady=9)

        self.body_frame = ctk.CTkFrame(self.shell, fg_color="transparent")
        self.body_frame.pack(fill="both", expand=True)
        self.body_frame.grid_columnconfigure(0, weight=7, uniform="ops")
        self.body_frame.grid_columnconfigure(1, weight=4, uniform="ops")
        self.body_frame.grid_rowconfigure(0, weight=1)

        deck_panel = ctk.CTkFrame(self.body_frame, **PANEL_STYLE)
        deck_panel.grid(row=0, column=0, sticky="nsew", padx=(0, 12))
        deck_panel.grid_rowconfigure(2, weight=1)
        deck_panel.grid_columnconfigure(0, weight=1)

        deck_header = ctk.CTkFrame(deck_panel, fg_color="transparent")
        deck_header.grid(row=0, column=0, sticky="ew", padx=16, pady=(16, 8))
        deck_header.grid_columnconfigure(0, weight=1)
        _section_title(deck_header, "프리셋 목록").grid(row=0, column=0, sticky="w")
        self.preset_summary_label = _caption(deck_header, "프리셋 0개", HUD_MUTED)
        self.preset_summary_label.grid(row=0, column=1, sticky="e")
        _accent_line(deck_panel, HUD_GOLD_DIM, 1).grid(row=1, column=0, sticky="ew", padx=16)

        self.scroll = ctk.CTkScrollableFrame(
            deck_panel,
            fg_color=HUD_ACTION_BG,
            border_width=1,
            border_color=HUD_LINE_SOFT,
            corner_radius=8,
            scrollbar_button_color=HUD_LINE,
            scrollbar_button_hover_color=HUD_GOLD_DIM,
        )
        self.scroll.grid(row=2, column=0, sticky="nsew", padx=16, pady=14)

        deck_footer = ctk.CTkFrame(deck_panel, fg_color=HUD_STATUS_BG, border_width=1, border_color=HUD_LINE_SOFT, corner_radius=8)
        deck_footer.grid(row=3, column=0, sticky="ew", padx=16, pady=(0, 14))
        deck_footer.grid_columnconfigure((0, 1, 2), weight=1, uniform="deck_footer")
        self.queue_state_label = _caption(deck_footer, "대기 중", HUD_OK)
        self.queue_state_label.grid(row=0, column=0, sticky="w", padx=12, pady=9)
        self.deck_preset_count_label = _caption(deck_footer, "프리셋 0개", HUD_MUTED)
        self.deck_preset_count_label.grid(row=0, column=1, pady=9)
        self.deck_action_count_label = _caption(deck_footer, "코드 0개", HUD_CYAN)
        self.deck_action_count_label.grid(row=0, column=2, sticky="e", padx=12, pady=9)

        side_panel = ctk.CTkFrame(self.body_frame, **PANEL_STYLE)
        side_panel.grid(row=0, column=1, sticky="nsew")
        side_panel.grid_columnconfigure(0, weight=1)
        side_panel.grid_rowconfigure(3, weight=1)

        _section_title(side_panel, "운영 상태").grid(row=0, column=0, sticky="w", padx=16, pady=(16, 10))
        metrics = ctk.CTkFrame(side_panel, fg_color="transparent")
        metrics.grid(row=1, column=0, sticky="ew", padx=16, pady=(0, 12))
        metrics.grid_columnconfigure((0, 1), weight=1, uniform="metric")
        self.mode_metric = self._make_metric(metrics, "API 모드", "대기", 0, 0)
        self.provider_metric = self._make_metric(metrics, "대회 공급자", "-", 0, 1)
        self.preset_metric = self._make_metric(metrics, "프리셋", "0", 1, 0)
        self.auth_metric = self._make_metric(metrics, "운영자", "확인 중", 1, 1)

        _accent_line(side_panel, HUD_GOLD_DIM, 1).grid(row=2, column=0, sticky="ew", padx=16, pady=(0, 12))
        log_frame = ctk.CTkFrame(side_panel, fg_color="transparent")
        log_frame.grid(row=3, column=0, sticky="nsew", padx=16, pady=(0, 12))
        log_frame.grid_columnconfigure(0, weight=1)
        log_frame.grid_rowconfigure(1, weight=1)
        _caption(log_frame, "진행 로그", HUD_CYAN).grid(row=0, column=0, sticky="w", pady=(0, 6))
        self.activity_log = ctk.CTkTextbox(log_frame, height=180, **TEXTBOX_STYLE)
        self.activity_log.grid(row=1, column=0, sticky="nsew")

        self.btn_settings = ctk.CTkButton(
            side_panel,
            text="설정 및 프리셋",
            height=BUTTON_HEIGHT_STD,
            font=BODY_FONT,
            command=lambda: ManualConfigWindow(self),
            **_button_style("gold"),
        )
        self.btn_settings.grid(row=4, column=0, sticky="ew", padx=16, pady=(0, 12))

        self.legal_footer = ctk.CTkFrame(self.shell, fg_color="transparent")
        self.legal_footer.pack(fill="x", pady=(10, 0))
        self.legal_label = ctk.CTkLabel(
            self.legal_footer,
            text=LEGAL_NOTICE,
            font=SMALL_FONT,
            text_color=HUD_MUTED,
            wraplength=820,
            justify="left",
        )
        self.legal_label.pack(anchor="w", padx=4)

    def _make_metric(self, parent, label, value, row, column):
        frame = ctk.CTkFrame(parent, fg_color=HUD_STATUS_BG, border_width=1, border_color=HUD_LINE_SOFT, corner_radius=8)
        frame.grid(row=row, column=column, sticky="ew", padx=(0 if column == 0 else 6, 6 if column == 0 else 0), pady=(0, 8))
        _caption(frame, label, HUD_MUTED).pack(anchor="w", padx=12, pady=(10, 0))
        value_label = ctk.CTkLabel(frame, text=value, font=(APP_FONT, 18, "bold"), text_color=HUD_TEXT)
        value_label.pack(anchor="w", padx=12, pady=(0, 10))
        return value_label

    def refresh_presets(self):
        self.presets = load_presets_file()
        self.preset_cards = []
        total_actions = sum(len(preset.get("actions", [])) for preset in self.presets)
        if hasattr(self, "preset_summary_label"):
            self.preset_summary_label.configure(text=f"프리셋 {len(self.presets)}개")
        if hasattr(self, "deck_preset_count_label"):
            self.deck_preset_count_label.configure(text=f"프리셋 {len(self.presets)}개")
            self.deck_action_count_label.configure(text=f"코드 {total_actions}개")
        self._update_dashboard_metrics()

        for widget in self.scroll.winfo_children():
            widget.destroy()

        if not self.presets:
            empty_panel = ctk.CTkFrame(self.scroll, fg_color=HUD_STATUS_BG, border_width=1, border_color=HUD_LINE_SOFT, corner_radius=8)
            empty_panel.pack(fill="x", padx=10, pady=14)
            ctk.CTkLabel(
                empty_panel,
                text="저장된 프리셋이 없습니다.",
                font=SUBHEADER_FONT,
                text_color=HUD_GOLD,
            ).pack(pady=(18, 4))
            ctk.CTkLabel(
                empty_panel,
                text="설정 화면에서 프리셋을 추가할 수 있습니다.",
                font=BODY_FONT,
                text_color=HUD_MUTED,
                wraplength=460,
            ).pack(padx=18, pady=(0, 18))
            return

        for index, preset in enumerate(self.presets, start=1):
            self._add_preset_card(index, preset)

    def _add_preset_card(self, index, preset):
        action_count = len(preset.get("actions", []))
        action_names = [action.get("name", "") for action in preset.get("actions", []) if action.get("name")]
        preview = " / ".join(action_names[:3])
        if len(action_names) > 3:
            preview = f"{preview} / +{len(action_names) - 3}"
        if not preview:
            preview = "등록된 경기가 없습니다"
        card = ctk.CTkFrame(
            self.scroll,
            height=108,
            fg_color=HUD_STATUS_BG,
            border_width=1,
            border_color=HUD_LINE_SOFT,
            corner_radius=8,
        )
        card.pack(fill="x", padx=10, pady=(8, 4))
        card.pack_propagate(False)

        accent = ctk.CTkFrame(card, width=3, fg_color=HUD_GOLD, corner_radius=0)
        accent.pack(side="left", fill="y", padx=(0, 0), pady=12)

        index_label = ctk.CTkLabel(
            card,
            text=f"{index:02d}",
            font=(APP_FONT, 16, "bold"),
            text_color=HUD_GOLD,
            width=48,
        )
        index_label.pack(side="left", fill="y", padx=(14, 10), pady=12)

        content_frame = ctk.CTkFrame(card, fg_color="transparent")
        content_frame.pack(side="left", fill="both", expand=True, padx=(0, 14), pady=14)

        title_label = ctk.CTkLabel(
            content_frame,
            text=preset["label"],
            font=(APP_FONT, 17, "bold"),
            text_color=HUD_TEXT,
            anchor="w",
        )
        title_label.pack(anchor="w", fill="x")
        preview_label = ctk.CTkLabel(
            content_frame,
            text=preview,
            font=SMALL_FONT,
            text_color=HUD_MUTED,
            anchor="w",
        )
        preview_label.pack(anchor="w", fill="x", pady=(5, 0))
        status_label = _caption(content_frame, f"코드 {action_count}개 준비", HUD_CYAN)
        status_label.pack(anchor="w", pady=(9, 0))

        self._bind_preset_card(card, preset)
        for child in (accent, index_label, content_frame, title_label, preview_label, status_label):
            self._bind_preset_card(child, preset)
        self.preset_cards.append(card)

    def _bind_preset_card(self, widget, preset):
        widget.bind("<Button-1>", lambda _event, p=preset: self.run_preset(p))

    def log(self, msg, color=HUD_TEXT):
        def update():
            self.latest_status_color = color
            self.status_label.configure(text=msg, text_color=color)
            if hasattr(self, "activity_log"):
                timestamp = datetime.now().strftime("%H:%M:%S")
                self.activity_log.insert("end", f"[{timestamp}] {msg}\n")
                self.activity_log.see("end")
            print(f"[LOG] {msg}")
        self.call_on_ui(update)

    def call_on_ui(self, callback, *args, **kwargs):
        if threading.current_thread() is threading.main_thread():
            return callback(*args, **kwargs)
        self.ui_queue.put((callback, args, kwargs))
        return None

    def _drain_ui_queue(self):
        try:
            while True:
                callback, args, kwargs = self.ui_queue.get_nowait()
                try:
                    callback(*args, **kwargs)
                except Exception as e:
                    print(f"[UI] update failed: {e}")
        except queue.Empty:
            pass
        self.after(50, self._drain_ui_queue)

    def toggle_buttons(self, state="normal"):
        self.controls_enabled = state == "normal"
        border_color = HUD_LINE_SOFT if self.controls_enabled else HUD_LINE
        fg_color = HUD_STATUS_BG if self.controls_enabled else HUD_LOG_BG
        for widget in self.preset_cards:
            widget.configure(border_color=border_color, fg_color=fg_color)
        self.btn_settings.configure(state=state)

    def run_preset(self, preset):
        if not self.controls_enabled:
            return
        if not self.client:
            self.log("보안 서버 설정 또는 로그인이 필요합니다.", HUD_DANGER)
            return

        self.log(f"{preset['label']} 실행 중...", HUD_WARN)
        self.toggle_buttons("disabled")

        threading.Thread(target=self._process_preset, args=(preset,), daemon=True).start()

    def _process_preset(self, preset):
        try:
            config = config_manager.load_config()
            if not self.provider_id:
                self.log("대회 공급자 ID가 없어 자동 등록을 시도합니다.", HUD_WARN)
                res = self.client.create_provider(
                    region=config.get("region", "KR"),
                )
                if res["success"]:
                    self.provider_id = res["data"]
                    conf = config_manager.load_config()
                    conf["provider_id"] = self.provider_id
                    config_manager.save_config(conf)
                    self.call_on_ui(self._update_dashboard_metrics)
                else:
                    self.log(f"대회 공급자 등록 실패: {_display_message(res['error'])}", HUD_DANGER)
                    return

            success_count = 0
            total_count = len(preset["actions"])

            for action in preset["actions"]:
                try:
                    t_name = action.get("api_name", action["name"])
                    t_res = self.client.create_tournament(self.provider_id, t_name)

                    if not t_res["success"]:
                        print(f"[{action['name']}] 토너먼트 등록 실패: {t_res['error']}")
                        if should_stop_after_riot_failure(t_res):
                            self.log("Riot API 응답이 불안정해 남은 작업을 중단했습니다.", HUD_WARN)
                            break
                        continue

                    tid = t_res["data"]
                    c_res = self.client.create_codes(tid, count=1)

                    if not c_res["success"]:
                        print(f"[{action['name']}] 코드 발급 실패: {c_res['error']}")
                        if should_stop_after_riot_failure(c_res):
                            self.log("Riot API 응답이 불안정해 남은 작업을 중단했습니다.", HUD_WARN)
                            break
                        continue

                    code = c_res["data"][0]

                    if send_discord_webhook(action["url"], action["name"], code):
                        success_count += 1
                    else:
                        print(f"[{action['name']}] 디스코드 알림 실패")

                except Exception as e:
                    print(f"Error: {e}")

            if success_count == total_count:
                self.log(f"발급 완료: {preset['label']}", HUD_OK)
            elif success_count > 0:
                self.log(f"일부 발급 완료 ({success_count}/{total_count}): {preset['label']}", HUD_WARN)
            else:
                self.log(f"발급 실패: {preset['label']}", HUD_DANGER)

        except Exception as e:
            self.log(f"예상치 못한 오류: {e}", HUD_DANGER)

        finally:
            self.call_on_ui(self.toggle_buttons, "normal")

if __name__ == "__main__":
    app = LoLPresetApp()
    app.mainloop()
