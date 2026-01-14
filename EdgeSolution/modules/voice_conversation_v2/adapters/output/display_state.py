"""Display state publisher for visual feedback animation."""

import socket
import json
from typing import Literal

DisplayState = Literal["idle", "listening", "speaking"]


class DisplayStatePublisher:
    """Publishes conversation state to display animation app via UDP."""

    def __init__(self, host: str = "127.0.0.1", port: int = 9999) -> None:
        """Initialize UDP socket for state publishing."""
        self._sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self._addr = (host, port)

    def publish(self, state: DisplayState) -> None:
        """Send state update to display app."""
        try:
            msg = json.dumps({"state": state}).encode("utf-8")
            self._sock.sendto(msg, self._addr)
        except OSError:
            pass  # Display failure should not interrupt voice interaction

    def cleanup(self) -> None:
        """Close UDP socket."""
        self._sock.close()
