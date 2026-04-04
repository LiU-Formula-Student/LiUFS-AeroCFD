"""UI package for LiU FS Viewer.

Use lazy imports so non-UI modules/tests can import subpackages without
requiring Qt system libraries at import time.
"""

__all__ = ["UIBuilder", "ViewerWindow"]


def __getattr__(name: str):
	if name == "UIBuilder":
		from aerocfd_app.ui.ui_builder import UIBuilder

		return UIBuilder
	if name == "ViewerWindow":
		from aerocfd_app.ui.viewer_window import ViewerWindow

		return ViewerWindow
	raise AttributeError(f"module {__name__!r} has no attribute {name!r}")