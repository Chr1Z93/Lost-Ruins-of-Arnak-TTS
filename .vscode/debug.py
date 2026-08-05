import json
import platform
import re
import sys
import subprocess
from pathlib import Path

PLATFORM = platform.system()


def load_config():
    """Loads configuration from build_config.json with defaults."""
    config_path = Path(__file__).parent / "build_config.json"
    data = {"GAME_NAME": "ArkhamSCE", "HOTKEY": "f13", "FORCE_GO": False}  # Defaults

    if config_path.is_file():
        try:
            with open(config_path, "r") as f:
                user_config = json.load(f)
                data.update(user_config)
        except Exception as e:
            print(f"Warning: Could not read build_config.json ({e}). Using defaults.")
    return data


# CONFIGURATION
CONFIG = load_config()
GAME_NAME = CONFIG["GAME_NAME"]
HOTKEY = CONFIG["HOTKEY"]
FORCE_GO = CONFIG["FORCE_GO"]
WINDOW_TITLE = "Tabletop Simulator"


def get_output_folder():
    home = Path.home()
    if PLATFORM == "Windows":
        return home / "Documents" / "My Games" / "Tabletop Simulator" / "Saves"
    else:
        return home / "Library" / "Tabletop Simulator" / "Saves"


# Recursive search for the GUID in ObjectStates
def find_script(objects, target_guid):
    for obj in objects:
        if obj.get("GUID") == target_guid:
            return obj.get("LuaScript", "")
        if "ContainedObjects" in obj:
            result = find_script(obj["ContainedObjects"], target_guid)
            if result:
                return result
    return None


def open_source_file(bundled_code, error_line):
    lines = bundled_code.splitlines()
    current_module = "Main / Wrapper"
    module_start_line = 0

    # Regex to find: __bundle_register("module/name", function(...)
    register_pattern = re.compile(r'__bundle_register\("([^"]+)"')

    # Step 1: Find which module the error line falls into
    for i, line in enumerate(lines):
        current_line_num = i + 1
        match = register_pattern.search(line)

        if match:
            # If the current error line is before this new register starts,
            # it belonged to the previous module.
            if current_line_num > error_line:
                break
            current_module = match.group(1)
            module_start_line = current_line_num

    # Step 2: Calculate the local line number within that module
    # We subtract the header lines added by the register:
    # Usually: __bundle_register(..., function(...) \n do
    local_line = (error_line - module_start_line) - 1

    print(f"Error found in module: {current_module} at local line: {local_line}")

    # Step 3: Find the file in your project
    # Assumes your source is in 'src' and this script is in '.vscode'
    possible_file = Path.cwd().parent / "src" / f"{current_module}.ttslua"

    print(possible_file)
    if possible_file.exists():
        print("Source file found, opening it.")
        # Offset of 1 needed for correct line number (due to "actual" script being one require line)
        subprocess.run(["code", "-g", f"{str(possible_file)}:{local_line + 1}"], shell=True)
    else:
        # Fallback: Open the temp bundled file if source not found
        print("Source file not found, opening bundled code instead.")
        temp_dir = Path(__file__).parent / "temp"
        temp_dir.mkdir(exist_ok=True)
        temp_path = temp_dir / f"debug.ttslua"
        with open(temp_path, "w", encoding="utf-8", newline='') as f:
            f.write(bundled_code)

        # Open in VS Code at the specific line: code -g file:line
        subprocess.run(["code", "-g", f"{temp_path}:{error_line}"], shell=True)


def open_bundled_script(target_guid, line_number):
    output_folder = get_output_folder()
    save_path = output_folder / f"{GAME_NAME}.json"

    with open(save_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    # Find Global or Object script
    if target_guid.lower() == "global":
        script_content = data.get("LuaScript", "")
    else:
        script_content = find_script(data.get("ObjectStates", []), target_guid)

    if script_content:
        open_source_file(script_content, int(line_number))
    else:
        print(f"Object {target_guid} not found.")


if __name__ == "__main__":
    if len(sys.argv) > 2:
        open_bundled_script(sys.argv[1], sys.argv[2])
