import customtkinter as ctk
import os
import threading
import pyperclip
import json
from api_client import RiotTournamentClient
from discord_helper import send_discord_webhook
import config_manager

# --- Configuration Constants ---
ctk.set_appearance_mode("Dark")
ctk.set_default_color_theme("blue")

HEADER_FONT = ("Roboto", 20, "bold")
SUBHEADER_FONT = ("Roboto", 16, "bold")
BODY_FONT = ("Roboto", 14)

# Standard Dimensions
BUTTON_HEIGHT_LG = 50
BUTTON_HEIGHT_STD = 40
INPUT_HEIGHT = 35

PRESETS_FILE = "presets.json"

def load_presets_file():
    # 1. Try loading actual presets
    if os.path.exists(PRESETS_FILE):
        try:
            with open(PRESETS_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception as e:
            print(f"Error loading presets: {e}")
            return []
            
    # 2. Fallback to example file if exists
    if os.path.exists("presets.json.example"):
        try:
            with open("presets.json.example", "r", encoding="utf-8") as f:
                data = json.load(f)
            # Auto-create presets.json from example for convenience
            save_presets_file(data)
            return data
        except:
            pass
            
    return []

def save_presets_file(data):
    try:
        with open(PRESETS_FILE, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
        return True
    except Exception as e:
        print(f"Error saving presets: {e}")
        return False

class ManualConfigWindow(ctk.CTkToplevel):
    def __init__(self, parent):
        super().__init__(parent)
        self.title("설정 (Settings)")
        self.geometry("600x850")
        self.parent = parent
        self.current_editing_index = 0
        
        # Grid Configuration
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(0, weight=1)
        
        # Mappings for API
        self.map_mapping = {
            "소환사의 협곡 (Summoner's Rift)": "SUMMONERS_RIFT",
            "칼바람 나락 (Howling Abyss)": "HOWLING_ABYSS"
        }
        self.pick_mapping = {
            "토너먼트 드래프트 (Tournament Draft)": "TOURNAMENT_DRAFT",
            "비공개 선택 (Blind Pick)": "BLIND_PICK",
            "무작위 총력전 (All Random)": "ALL_RANDOM"
        }
        
        # Tab View
        self.tab_view = ctk.CTkTabview(self)
        self.tab_view.pack(fill="both", expand=True, padx=20, pady=20)
        
        self.tab_general = self.tab_view.add("일반 설정")
        self.tab_manual = self.tab_view.add("수동 생성")
        self.tab_presets = self.tab_view.add("프리셋 관리")
        
        self._init_general_tab()
        self._init_manual_tab()
        self._init_presets_tab()
        
        self._load_current_settings()

    def _init_general_tab(self):
        # 1. Environment Settings
        ctk.CTkLabel(self.tab_general, text="환경 설정 (Environment)", font=SUBHEADER_FONT).pack(pady=(10, 5))
        
        self.switch_stub = ctk.CTkSwitch(self.tab_general, text="Stub API 사용 (테스트용)", font=BODY_FONT)
        self.switch_stub.pack(pady=5)
        
        ctk.CTkButton(self.tab_general, text="설정 저장 및 적용", height=BUTTON_HEIGHT_STD, command=self.save_general_settings).pack(pady=15)

        # 2. Provider Info
        ctk.CTkFrame(self.tab_general, height=2, fg_color="gray").pack(fill="x", padx=20, pady=10)
        ctk.CTkLabel(self.tab_general, text="공급자 (Provider)", font=SUBHEADER_FONT).pack(pady=5)
        
        self.lbl_provider = ctk.CTkLabel(self.tab_general, text="ID: 없음", font=BODY_FONT)
        self.lbl_provider.pack(pady=5)
        
        ctk.CTkButton(self.tab_general, text="Provider 새로 생성 (Region: KR)", height=BUTTON_HEIGHT_STD, command=self.create_new_provider).pack(pady=10)
        
        self.txt_gen_log = ctk.CTkTextbox(self.tab_general, height=100)
        self.txt_gen_log.pack(fill="x", padx=20, pady=10)

    def _init_manual_tab(self):
        ctk.CTkLabel(self.tab_manual, text="수동 코드 생성 (Manual Generation)", font=SUBHEADER_FONT).pack(pady=10)
        
        self.entry_tourn_name = ctk.CTkEntry(self.tab_manual, placeholder_text="토너먼트 이름 (예: My Tournament)", height=INPUT_HEIGHT)
        self.entry_tourn_name.pack(fill="x", padx=20, pady=5)
        
        btn_frame = ctk.CTkFrame(self.tab_manual, fg_color="transparent")
        btn_frame.pack(pady=5)
        
        self.combo_map = ctk.CTkComboBox(btn_frame, values=list(self.map_mapping.keys()), height=INPUT_HEIGHT, width=200)
        self.combo_map.pack(side="left", padx=5)
        self.combo_pick = ctk.CTkComboBox(btn_frame, values=list(self.pick_mapping.keys()), height=INPUT_HEIGHT, width=200)
        self.combo_pick.pack(side="left", padx=5)
        
        self.btn_manual_gen = ctk.CTkButton(
            self.tab_manual, 
            text="토너먼트 생성 및 코드 발급", 
            height=BUTTON_HEIGHT_STD, 
            fg_color="#E0A800", text_color="black", hover_color="#C69500", 
            font=BODY_FONT,
            command=self.manual_generate
        )
        self.btn_manual_gen.pack(pady=15)
        
        self.txt_manual_result = ctk.CTkTextbox(self.tab_manual, height=200)
        self.txt_manual_result.pack(fill="both", expand=True, padx=20, pady=10)

    def _init_presets_tab(self):
        # Load presets strictly from file for editing
        self.edit_presets_data = load_presets_file()
        
        # --- Top Section: Preset Selection & Management ---
        frame_top = ctk.CTkFrame(self.tab_presets, fg_color="transparent")
        frame_top.pack(fill="x", padx=10, pady=(10, 5))

        ctk.CTkLabel(frame_top, text="편집할 프리셋:", font=BODY_FONT).pack(side="left")
        
        self.preset_names = [p["label"] for p in self.edit_presets_data]
        self.combo_presets = ctk.CTkComboBox(frame_top, values=self.preset_names, command=self._on_preset_select, height=INPUT_HEIGHT, width=200)
        self.combo_presets.pack(side="left", padx=10)

        ctk.CTkButton(frame_top, text="+ 추가", width=60, height=INPUT_HEIGHT, command=self.add_preset).pack(side="left", padx=5)
        self.btn_del_preset = ctk.CTkButton(frame_top, text="- 삭제", width=60, height=INPUT_HEIGHT, fg_color="red", command=self.delete_preset)
        self.btn_del_preset.pack(side="left", padx=5)
        
        # --- Edit Form ---
        self.frame_edit = ctk.CTkFrame(self.tab_presets)
        self.frame_edit.pack(fill="both", expand=True, padx=10, pady=10)
        
        # Label Edit
        ctk.CTkLabel(self.frame_edit, text="프리셋 이름 (버튼 텍스트)", font=BODY_FONT).pack(anchor="w", padx=10, pady=(10,0))
        self.entry_preset_label = ctk.CTkEntry(self.frame_edit, height=INPUT_HEIGHT)
        self.entry_preset_label.pack(fill="x", padx=10, pady=5)
        
        # Actions List (Scrollable)
        ctk.CTkLabel(self.frame_edit, text="세부 액션 및 웹훅 설정", font=BODY_FONT).pack(anchor="w", padx=10, pady=(10,0))
        
        self.scroll_actions = ctk.CTkScrollableFrame(self.frame_edit, height=300)
        self.scroll_actions.pack(fill="both", expand=True, padx=10, pady=5)
        
        self.action_entries = [] # Stores widgets and references
        
        # Add Action Button
        ctk.CTkButton(self.frame_edit, text="+ 새 액션 추가", height=30, command=self.add_action).pack(pady=5)
        
        # Save Button (Bottom)
        ctk.CTkButton(self.tab_presets, text="프리셋 저장 (Save Changes)", height=BUTTON_HEIGHT_STD, fg_color="green", command=self.save_preset_changes).pack(pady=10)

        # Initialize
        if self.preset_names:
            self.combo_presets.set(self.preset_names[0])
            self._on_preset_select(self.preset_names[0])
        else:
            self.combo_presets.set("")
            self._clear_edit_form()

    def _clear_edit_form(self):
        self.entry_preset_label.delete(0, "end")
        for widget in self.scroll_actions.winfo_children():
            widget.destroy()
        self.action_entries = []
        self.current_editing_index = -1
        self.btn_del_preset.configure(state="disabled")

    def _on_preset_select(self, choice):
        if not choice: return
        
        # Find selected preset data
        selected = next((p for p in self.edit_presets_data if p["label"] == choice), None)
        if not selected: return
        
        self.current_editing_index = self.edit_presets_data.index(selected)
        self.btn_del_preset.configure(state="normal")
        
        # Fill Label
        self.entry_preset_label.delete(0, "end")
        self.entry_preset_label.insert(0, selected["label"])
        
        # Refresh Actions UI
        self._refresh_actions_ui(selected["actions"])

    def _refresh_actions_ui(self, actions):
        # Clear existing
        for widget in self.scroll_actions.winfo_children():
            widget.destroy()
        self.action_entries = []
        
        for i, action in enumerate(actions):
            f = ctk.CTkFrame(self.scroll_actions, fg_color="transparent")
            f.pack(fill="x", pady=5)
            
            # Action Name
            ctk.CTkLabel(f, text="액션명:", width=60).pack(side="left")
            name_entry = ctk.CTkEntry(f, width=120, height=INPUT_HEIGHT)
            name_entry.pack(side="left", padx=5)
            name_entry.insert(0, action.get("name", ""))
            
            # URL
            ctk.CTkLabel(f, text="웹훅:", width=40).pack(side="left")
            url_entry = ctk.CTkEntry(f, height=INPUT_HEIGHT)
            url_entry.pack(side="left", fill="x", expand=True, padx=5)
            url_entry.insert(0, action.get("url", ""))
            
            # Delete Action Button
            btn_del = ctk.CTkButton(f, text="X", width=30, height=INPUT_HEIGHT, fg_color="red", 
                                  command=lambda idx=i: self.delete_action(idx))
            btn_del.pack(side="right", padx=5)
            
            self.action_entries.append({
                "name_entry": name_entry,
                "url_entry": url_entry
            })

    def add_preset(self):
        new_preset = {
            "label": "새 프리셋",
            "actions": [{"name": "새 액션", "url": ""}]
        }
        self.edit_presets_data.append(new_preset)
        self._reload_combo(select_last=True)

    def delete_preset(self):
        if self.current_editing_index < 0 or self.current_editing_index >= len(self.edit_presets_data):
            return
            
        del self.edit_presets_data[self.current_editing_index]
        save_presets_file(self.edit_presets_data) # Auto save on delete for safety
        self.parent.refresh_presets() # Update main UI
        
        self._reload_combo(select_last=False)
        self.parent.log("프리셋이 삭제되었습니다.", "red")

    def add_action(self):
        if self.current_editing_index == -1: return
        
        # We need to temporarily save current UI state to memory to redraw
        self._sync_ui_to_memory()
        
        # Add new empty action
        self.edit_presets_data[self.current_editing_index]["actions"].append({
            "name": "새 액션",
            "url": ""
        })
        
        # Redraw
        self._refresh_actions_ui(self.edit_presets_data[self.current_editing_index]["actions"])

    def delete_action(self, idx):
        if self.current_editing_index == -1: return
        
        self._sync_ui_to_memory()
        
        actions = self.edit_presets_data[self.current_editing_index]["actions"]
        if len(actions) > 0:
            del actions[idx]
            
        self._refresh_actions_ui(actions)

    def _sync_ui_to_memory(self):
        """Syncs current entries back to memory object before re-rendering"""
        if self.current_editing_index == -1: return
        
        target = self.edit_presets_data[self.current_editing_index]
        target["label"] = self.entry_preset_label.get().strip()
        
        # Reconstruct actions list from UI
        new_actions = []
        for entry in self.action_entries:
            new_actions.append({
                "name": entry["name_entry"].get().strip(),
                "url": entry["url_entry"].get().strip()
            })
        target["actions"] = new_actions

    def _reload_combo(self, select_last=False):
        self.preset_names = [p["label"] for p in self.edit_presets_data]
        self.combo_presets.configure(values=self.preset_names)
        
        if self.preset_names:
            if select_last:
                self.combo_presets.set(self.preset_names[-1])
                self._on_preset_select(self.preset_names[-1])
            else:
                self.combo_presets.set(self.preset_names[0])
                self._on_preset_select(self.preset_names[0])
        else:
            self.combo_presets.set("")
            self._clear_edit_form()

    def save_preset_changes(self):
        if self.current_editing_index == -1: return
            
        self._sync_ui_to_memory() # Final sync
        
        # Write to file
        if save_presets_file(self.edit_presets_data):
            self.parent.log("프리셋이 저장되었습니다.", "green")
            # Refresh Main UI
            self.parent.refresh_presets()
            
            # Refresh Config Dropdown name (in case label changed)
            current_idx = self.current_editing_index
            self._reload_combo()
            
            # Reselect the saved item
            if current_idx < len(self.preset_names):
                self.combo_presets.set(self.preset_names[current_idx])
            
        else:
            self.parent.log("프리셋 저장 실패", "red")

    def _load_current_settings(self):
        # General Tab Loading
        config = config_manager.load_config()
        if config.get("use_stub", True):
            self.switch_stub.select()
        else:
            self.switch_stub.deselect()
            
        pid = config.get("provider_id")
        self.lbl_provider.configure(text=f"현재 Provider ID: {pid}" if pid else "Provider ID: 없음 (생성 필요)")

    def save_general_settings(self):
        use_stub = bool(self.switch_stub.get())
        
        config = config_manager.load_config()
        config["use_stub"] = use_stub
        config_manager.save_config(config)
        
        self.parent.init_client()
        self.parent.log("설정이 저장되었습니다.", "green")
        
        self.lbl_provider.configure(text=f"현재 Provider ID: {config.get('provider_id') or '없음'}")
        self.txt_gen_log.insert("end", "설정 저장 완료.\n")

    def create_new_provider(self):
        if not self.parent.client:
            self.txt_gen_log.insert("end", "오류: 클라이언트 미초기화.\n")
            return
            
        def run():
            self.txt_gen_log.insert("end", "Provider 생성 요청 중...\n")
            res = self.parent.client.create_provider(region="KR", url="http://example.com/callback")
            if res["success"]:
                pid = res["data"]
                self.parent.provider_id = pid
                
                conf = config_manager.load_config()
                conf["provider_id"] = pid
                config_manager.save_config(conf)
                
                self.lbl_provider.configure(text=f"현재 Provider ID: {pid}")
                self.txt_gen_log.insert("end", f"Provider 생성 성공: {pid}\n")
            else:
                self.txt_gen_log.insert("end", f"Provider 생성 실패: {res['error']}\n")
        threading.Thread(target=run).start()

    def manual_generate(self):
        if not self.parent.client: 
            self.txt_manual_result.insert("end", "오류: 클라이언트 미초기화.\n")
            return
        if not self.parent.provider_id:
            self.txt_manual_result.insert("end", "오류: Provider ID 없음.\n")
            return
            
        t_name = self.entry_tourn_name.get().strip() or "Manual Tournament"
        map_val = self.map_mapping.get(self.combo_map.get(), "SUMMONERS_RIFT")
        pick_val = self.pick_mapping.get(self.combo_pick.get(), "TOURNAMENT_DRAFT")
        
        def run():
            self.txt_manual_result.insert("end", f"토너먼트 '{t_name}' 생성 중...\n")
            t_res = self.parent.client.create_tournament(self.parent.provider_id, t_name)
            if not t_res["success"]:
                self.txt_manual_result.insert("end", f"토너먼트 생성 실패: {t_res['error']}\n")
                return
            
            tid = t_res["data"]
            self.txt_manual_result.insert("end", f"토너먼트 ID: {tid}\n")
            
            c_res = self.parent.client.create_codes(tid, count=1, map_type=map_val, pick_type=pick_val)
            if c_res["success"]:
                code = c_res["data"][0]
                self.txt_manual_result.insert("end", f"코드 생성 완료:\n{code}\n")
                pyperclip.copy(code)
                self.txt_manual_result.insert("end", "(복사됨)\n")
            else:
                self.txt_manual_result.insert("end", f"코드 생성 실패: {c_res['error']}\n")
                
        threading.Thread(target=run).start()


class LoLPresetApp(ctk.CTk):
    def __init__(self):
        super().__init__()
        self.title("LOL Tournament Code Generator")
        self.geometry("500x700")
        
        self.client = None
        self.provider_id = None
        self.presets = []
        
        self._init_ui()
        self.init_client() 
        self.refresh_presets()

    def init_client(self):
        config = config_manager.load_config()
        use_stub = config.get("use_stub", True)
        self.provider_id = config.get("provider_id")
        
        self.client = RiotTournamentClient(use_stub=use_stub)
        mode_text = "Stub/Test (테스트 서버)" if use_stub else "Production (라이브 서버)"
        self.log(f"Backend 연결됨: {mode_text}", "#00FF00" if use_stub else "#FF5500")

    def _init_ui(self):
        # Header
        self.header_frame = ctk.CTkFrame(self, fg_color="transparent")
        self.header_frame.pack(fill="x", padx=20, pady=20)
        
        ctk.CTkLabel(self.header_frame, text="토너먼트 자동 생성", font=HEADER_FONT).pack()
        self.status_label = ctk.CTkLabel(self.header_frame, text="초기화 중...", font=BODY_FONT, text_color="gray")
        self.status_label.pack(pady=5)
        
        # Scrollable Area for Presets
        self.scroll = ctk.CTkScrollableFrame(self)
        self.scroll.pack(fill="both", expand=True, padx=20, pady=10)
        
        # Footer
        self.frame_footer = ctk.CTkFrame(self, fg_color="transparent")
        self.frame_footer.pack(fill="x", side="bottom", padx=20, pady=20)
        
        self.btn_settings = ctk.CTkButton(
            self.frame_footer, 
            text="설정 / 프리셋 관리 (Settings)", 
            height=BUTTON_HEIGHT_STD, 
            fg_color="#555555", 
            hover_color="#333333",
            font=BODY_FONT,
            command=lambda: ManualConfigWindow(self)
        )
        self.btn_settings.pack(fill="x")

    def refresh_presets(self):
        """Reloads presets from file and rebuilds the buttons"""
        self.presets = load_presets_file()
        
        # Clear existing buttons
        for widget in self.scroll.winfo_children():
            widget.destroy()
            
        if not self.presets:
            ctk.CTkLabel(self.scroll, text="저장된 프리셋이 없습니다.\npresets.json을 확인하거나 복원하세요.", font=BODY_FONT).pack(pady=20)
            return
            
        # Rebuild buttons
        for preset in self.presets:
            ctk.CTkButton(
                self.scroll,
                text=preset["label"],
                height=BUTTON_HEIGHT_LG,
                font=SUBHEADER_FONT,
                command=lambda p=preset: self.run_preset(p)
            ).pack(fill="x", padx=10, pady=10)

    def log(self, msg, color="white"):
        self.status_label.configure(text=msg, text_color=color)
        print(f"[LOG] {msg}")

    def toggle_buttons(self, state="normal"):
        """Enable or disable all preset buttons"""
        for widget in self.scroll.winfo_children():
            if isinstance(widget, ctk.CTkButton):
                widget.configure(state=state)
        
        # Also disable settings button to prevent changing configs mid-process
        self.btn_settings.configure(state=state)

    def run_preset(self, preset):
        if not self.client:
            self.log("오류: 백엔드 클라이언트가 초기화되지 않았습니다.", "#FF5555")
            return
            
        self.log(f"진행 중: {preset['label']}... (버튼 잠금)", "#FFFF55")
        self.toggle_buttons("disabled")
        
        threading.Thread(target=self._process_preset, args=(preset,)).start()

    def _process_preset(self, preset):
        try:
            # 0. Provider Check
            if not self.provider_id:
                self.log("Provider 없음. 자동 생성 시도...", "yellow")
                res = self.client.create_provider()
                if res["success"]:
                    self.provider_id = res["data"]
                    # Save dynamically
                    conf = config_manager.load_config()
                    conf["provider_id"] = self.provider_id
                    config_manager.save_config(conf)
                else:
                    self.log(f"Provider 생성 실패: {res['error']}", "#FF5555")
                    return

            success_count = 0
            total_count = len(preset["actions"])
            
            for action in preset["actions"]:
                try:
                    t_name = action.get("api_name", action["name"]) 
                    t_res = self.client.create_tournament(self.provider_id, t_name)
                    
                    if not t_res["success"]:
                        print(f"[{action['name']}] 토너먼트 생성 실패: {t_res['error']}")
                        continue
                        
                    tid = t_res["data"]
                    c_res = self.client.create_codes(tid, count=1)
                    
                    if not c_res["success"]:
                        print(f"[{action['name']}] 코드 생성 실패: {c_res['error']}")
                        continue
                        
                    code = c_res["data"][0]
                    
                    if send_discord_webhook(action["url"], action["name"], code):
                        success_count += 1
                    else:
                        print(f"[{action['name']}] 웹훅 실패")
                        
                except Exception as e:
                    print(f"Error: {e}")
            
            if success_count == total_count:
                self.log(f"모든 작업 완료: {preset['label']}", "#00FF00")
            elif success_count > 0:
                self.log(f"일부 완료 ({success_count}/{total_count}): {preset['label']}", "orange")
            else:
                self.log(f"작업 실패: {preset['label']}", "#FF5555")
                
        except Exception as e:
            self.log(f"치명적 오류: {e}", "red")
            
        finally:
            # Re-enable buttons on main thread
            self.after(0, lambda: self.toggle_buttons("normal"))

if __name__ == "__main__":
    app = LoLPresetApp()
    app.mainloop()
