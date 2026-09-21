"""Invitation accept schemas."""
from __future__ import annotations

from .common import ORMModel


class AcceptInvitation(ORMModel):
    """Body for POST /invitations/{token}/accept. Empty body OK."""
