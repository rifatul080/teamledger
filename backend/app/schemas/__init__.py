"""Pydantic v2 schemas shared across the API."""
from .auth import *  # noqa: F403
from .chat import *  # noqa: F403
from .common import *  # noqa: F403
from .files import *  # noqa: F403
from .goals import *  # noqa: F403
from .invitations import *  # noqa: F403
from .milestones import *  # noqa: F403
from .notifications import *  # noqa: F403
from .projects import *  # noqa: F403
from .schedules import *  # noqa: F403
from .scoring import *  # noqa: F403
from .tasks import *  # noqa: F403
from .teams import *  # noqa: F403

# `auth` and `users` both define ProfileUpdate (v1 vs v2 generations); the
# second star-import shadows the first in this namespace — direct module
# imports (`from .auth import ...`) disambiguate, so silence the type clash.
from .users import *  # type: ignore[assignment]  # noqa: F403
