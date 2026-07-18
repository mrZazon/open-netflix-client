from __future__ import annotations

import logging
from typing import Any, Dict

from PySide6.QtCore import QObject, QTimer

log = logging.getLogger(__name__)

MPRIS_PATH = "/org/mpris/MediaPlayer2"
MPRIS_BUS_NAME = "org.mpris.MediaPlayer2.netflix"
PLAYER_IFACE = "org.mpris.MediaPlayer2.Player"

try:
    from dasbus.connection import SessionMessageBus
    from dasbus.server.interface import dbus_interface


    DASBUS_AVAILABLE = True
except ImportError:
    DASBUS_AVAILABLE = False

    def dbus_interface(name: str):
        def wrapper(cls):
            cls.__dbus_interface__ = name
            return cls
        return wrapper


@dbus_interface("org.mpris.MediaPlayer2")
class MprisRoot(object):
    def __init__(self, on_raise, on_quit):
        self._on_raise = on_raise
        self._on_quit = on_quit

    def Raise(self) -> None:
        self._on_raise()

    def Quit(self) -> None:
        self._on_quit()

    @property
    def CanQuit(self) -> bool:
        return True

    @property
    def CanRaise(self) -> bool:
        return True

    @property
    def HasTrackList(self) -> bool:
        return False

    @property
    def Identity(self) -> str:
        return "Netflix Client"

    @property
    def DesktopEntry(self) -> str:
        return "netflix-client"

    @property
    def SupportedUriSchemes(self) -> list:
        return []

    @property
    def SupportedMimeTypes(self) -> list:
        return []


def _format_metadata(meta: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "mpris:trackid": f"/com/netflix/track/{abs(hash(meta.get('title', '')) % 1000000)}",
        "mpris:length": int(meta.get("duration", 0) * 1000000),
        "xesam:title": meta.get("title", "Netflix"),
    }


@dbus_interface("org.mpris.MediaPlayer2.Player")
class MprisPlayer(object):
    def __init__(self, provider):
        self._provider = provider

    @property
    def PlaybackStatus(self) -> str:
        s = self._provider.get_state()
        return {"playing": "Playing", "paused": "Paused"}.get(s, "Stopped")

    @property
    def LoopStatus(self) -> str:
        return "None"

    @property
    def Rate(self) -> float:
        return 1.0

    @property
    def Shuffle(self) -> bool:
        return False

    @property
    def Metadata(self) -> Dict[str, Any]:
        return _format_metadata(self._provider.get_metadata())

    @property
    def Volume(self) -> float:
        return self._provider.get_volume()

    @Volume.setter
    def Volume(self, value: float) -> None:
        self._provider.set_volume(value)

    @property
    def Position(self) -> int:
        return int(self._provider.get_position() * 1000000)

    @property
    def MinimumRate(self) -> float:
        return 1.0

    @property
    def MaximumRate(self) -> float:
        return 1.0

    @property
    def CanGoNext(self) -> bool:
        return True

    @property
    def CanGoPrevious(self) -> bool:
        return True

    @property
    def CanPlay(self) -> bool:
        return True

    @property
    def CanPause(self) -> bool:
        return True

    @property
    def CanSeek(self) -> bool:
        return True

    @property
    def CanControl(self) -> bool:
        return True

    def Next(self) -> None:
        self._provider.next()

    def Previous(self) -> None:
        self._provider.previous()

    def Pause(self) -> None:
        self._provider.pause()

    def PlayPause(self) -> None:
        self._provider.play_pause()

    def Stop(self) -> None:
        self._provider.stop()

    def Play(self) -> None:
        self._provider.play()

    def Seek(self, offset: int) -> None:
        self._provider.seek(offset / 1000000)

    def SetPosition(self, track_id: str, position: int) -> None:
        self._provider.set_position(position / 1000000)

    def OpenUri(self, uri: str) -> None:
        pass

    def _emit_properties_changed(self) -> None:
        pass


class PlaybackStateProvider(QObject):
    def __init__(self, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self._state: str = "stopped"
        self._metadata: Dict[str, Any] = {}
        self._volume: float = 1.0
        self._position: float = 0.0
        self._on_play = None
        self._on_pause = None
        self._on_play_pause = None
        self._on_stop = None
        self._on_next = None
        self._on_previous = None
        self._on_seek = None
        self._on_set_position = None
        self._on_set_volume = None

    def update_state(self, state: str) -> None:
        self._state = state

    def update_metadata(self, metadata: Dict[str, Any]) -> None:
        self._metadata = metadata
        self._position = metadata.get("position", 0.0)

    def update_position(self, position: float) -> None:
        self._position = position

    def get_state(self) -> str:
        return self._state

    def get_metadata(self) -> Dict[str, Any]:
        return self._metadata

    def get_volume(self) -> float:
        return self._volume

    def set_volume(self, vol: float) -> None:
        self._volume = max(0.0, min(1.0, vol))
        if self._on_set_volume:
            self._on_set_volume(self._volume)

    def get_position(self) -> float:
        return self._position

    def next(self) -> None:
        if self._on_next:
            self._on_next()

    def previous(self) -> None:
        if self._on_previous:
            self._on_previous()

    def pause(self) -> None:
        if self._on_pause:
            self._on_pause()

    def play_pause(self) -> None:
        if self._on_play_pause:
            self._on_play_pause()

    def stop(self) -> None:
        if self._on_stop:
            self._on_stop()

    def play(self) -> None:
        if self._on_play:
            self._on_play()

    def seek(self, offset: float) -> None:
        if self._on_seek:
            self._on_seek(offset)

    def set_position(self, position: float) -> None:
        if self._on_set_position:
            self._on_set_position(position)

    def set_callbacks(
        self,
        on_play=None,
        on_pause=None,
        on_play_pause=None,
        on_stop=None,
        on_next=None,
        on_previous=None,
        on_seek=None,
        on_set_position=None,
        on_set_volume=None,
    ) -> None:
        self._on_play = on_play
        self._on_pause = on_pause
        self._on_play_pause = on_play_pause
        self._on_stop = on_stop
        self._on_next = on_next
        self._on_previous = on_previous
        self._on_seek = on_seek
        self._on_set_position = on_set_position
        self._on_set_volume = on_set_volume


class MprisManager(QObject):
    def __init__(self, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self._provider = PlaybackStateProvider(self)
        self._bus = None
        self._root = None
        self._player = None
        self._available = DASBUS_AVAILABLE

    def start(self) -> None:
        if not self._available:
            log.warning("dasbus not available, MPRIS disabled")
            return
        try:
            self._bus = SessionMessageBus()
            self._root = MprisRoot(on_raise=lambda: None, on_quit=lambda: None)
            self._player = MprisPlayer(self._provider)

            self._bus.publish_object(MPRIS_PATH, self._root)
            self._bus.publish_object(MPRIS_PATH, self._player)
            self._bus.register_service(MPRIS_BUS_NAME)

            self._prop_timer = QTimer(self)
            self._prop_timer.setInterval(1000)
            self._prop_timer.timeout.connect(self._emit_properties_changed)
            self._prop_timer.start()

            log.info("MPRIS interface registered")
        except Exception as exc:
            log.warning("Failed to register MPRIS: %s", exc)
            self._available = False

    def stop(self) -> None:
        if self._bus and self._available:
            try:
                self._bus.disconnect()
            except Exception:
                pass

    @property
    def provider(self) -> PlaybackStateProvider:
        return self._provider

    def on_playback_state_changed(self, state: str) -> None:
        self._provider.update_state(state)
        self._emit_properties_changed()

    def on_metadata_changed(self, metadata: Dict[str, Any]) -> None:
        self._provider.update_metadata(metadata)
        self._emit_properties_changed()

    def _emit_properties_changed(self) -> None:
        if not self._available or not self._bus or not self._player:
            return
        try:
            self._bus.emit_signal(
                MPRIS_BUS_NAME,
                MPRIS_PATH,
                "org.freedesktop.DBus.Properties",
                "PropertiesChanged",
                "sa{sv}as",
                (
                    PLAYER_IFACE,
                    {
                        "PlaybackStatus": self._player.PlaybackStatus,
                        "Metadata": self._player.Metadata,
                        "Position": self._player.Position,
                    },
                    [],
                ),
            )
        except Exception:
            pass
