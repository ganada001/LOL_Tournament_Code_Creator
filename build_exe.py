import PyInstaller.__main__
import os
import customtkinter

# Get CustomTkinter path for bundling themes/assets
ctk_path = os.path.dirname(customtkinter.__file__)

PyInstaller.__main__.run([
    'gui_main.py',
    '--name=LOL_Tournament_Code_Creator',
    '--onefile',
    '--noconsole',
    '--clean',
    # Include CustomTkinter assets
    f'--add-data={ctk_path}{os.path.pathsep}customtkinter',
    # Include default config and presets example
    f'--add-data=presets.json.example{os.path.pathsep}.',
    f'--add-data=config.json{os.path.pathsep}.',
    # Include documentation as reference
    f'--add-data=tos.md{os.path.pathsep}.',
    f'--add-data=privacy.md{os.path.pathsep}.',
])
