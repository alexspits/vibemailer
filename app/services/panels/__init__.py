"""Адаптеры панелей VPN и их сборка по конфигу сервера."""

from __future__ import annotations

from typing import TYPE_CHECKING

from app.core.servers import PanelKind
from app.services.panels.amnezia import AmneziaPanel
from app.services.panels.base import (
    Artifact,
    PanelClient,
    PanelError,
    PanelUnreachable,
    config_filename,
)
from app.services.panels.fake import FakePanel
from app.services.panels.wg_easy import WgEasyPanel
from app.services.panels.xui import XuiPanel
from app.services.transport import build_transport

if TYPE_CHECKING:
    from app.core.servers import ServerConfig

_PANELS = {
    PanelKind.AMNEZIA: AmneziaPanel,
    PanelKind.WG_EASY: WgEasyPanel,
    PanelKind.XUI: XuiPanel,
    PanelKind.FAKE: FakePanel,
}

__all__ = [
    "AmneziaPanel",
    "Artifact",
    "FakePanel",
    "PanelClient",
    "PanelError",
    "PanelUnreachable",
    "WgEasyPanel",
    "XuiPanel",
    "build_panel",
    "config_filename",
]


def build_panel(server: ServerConfig) -> PanelClient:
    """Адаптер панели под конфиг сервера, вместе с нужным транспортом."""
    return _PANELS[server.panel](server, build_transport(server))
