# main.py — The Orb multitool entry point.
# Hardware comes from touch_setup (ILI9341 + FT6336). The UI lives in screens.py,
# which hosts the frozen agentic Supervisor as a background task.

import touch_setup  # noqa: F401  creates `display`; sets up ssd/tpad
from gui.core.tgui import Screen
import screens

Screen.change(screens.BaseScreen)
