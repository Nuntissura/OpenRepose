"""OpenRepose — desktop application supporting commercial adult production workflows.

First feature: 3D-rig-locked yaw-angle wireframe exporter.

See .gov/spec/openrepose_v0_1.md for the contract. See .gov/AGENTS.md and
.gov/CODEX.md for project-wide rules. Use the locked yaw terminology
(0, her-left N, her-right N) everywhere.
"""

__version__ = "0.1.0.dev0"

from .yaw_bin import YawBin, parse_bin, signed_deg_to_bin, standard_13_angle_bins  # noqa: F401
from .rig import Rig, OpenReposeRigFitError  # noqa: F401
from .rotation import rotate_yaw, RotatedRig  # noqa: F401
from .openpose_serialize import serialize, serialize_to_string  # noqa: F401
from .log import Logger, LogLevel, format_line  # noqa: F401
from .state import AppState  # noqa: F401
from .commands import CommandDispatcher, CommandResult, OpenReposeCommandError  # noqa: F401
from .app import App  # noqa: F401
