"""Live monitoring console for the Shift Buddy handover agent.

The console is a thin, honest viewer: it starts the real pipeline over a padded
inbox, tails the real ``audit.jsonl`` while it is being appended, and renders
only what those records say. Nothing on screen is a mock value.
"""

from .server import serve  # noqa: F401
