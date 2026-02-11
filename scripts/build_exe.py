import PyInstaller.__main__
import os
import customtkinter

# Get CustomTkinter path for bundling themes/assets
ctk_path = os.path.dirname(customtkinter.__file__)

PyInstaller.__main__.run([
    '../src/gui_main.py',
    '--name=LOL_Tournament_Code_Creator',
    '--onefile',
    '--noconsole',
    '--clean',
    '--distpath=../dist',
    '--workpath=../build',
    # Include CustomTkinter assets
    f'--add-data={ctk_path}{os.path.pathsep}customtkinter',
    # Include default config and presets example
    f'--add-data=../config/presets.json.example{os.path.pathsep}.',
    f'--add-data=../config.json{os.path.pathsep}.',
    # Include documentation as reference
    f'--add-data=../legal/tos.md{os.path.pathsep}.',
    f'--add-data=../legal/privacy.md{os.path.pathsep}.',
])
