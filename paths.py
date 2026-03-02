import os

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
UI_DIR = os.path.join(BASE_DIR, "GUI")


def ui_file(filename: str) -> str:
    return os.path.join(UI_DIR, filename)
