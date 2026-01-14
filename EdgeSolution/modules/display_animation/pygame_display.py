"""Display animation app for PokePal conversation feedback."""

import pygame
import socket
import json
import math
from typing import Protocol


class Animation(Protocol):
    """Protocol for swappable animations (pulse, face, eyes, etc.)."""

    def set_state(self, state: str) -> None:
        """Set current animation state."""
        ...

    def update(self, dt: float) -> None:
        """Update and render animation frame."""
        ...


class StateReceiver:
    """Receives conversation state via UDP (non-blocking)."""

    def __init__(self, port: int = 9999) -> None:
        """Initialize UDP socket for state receiving."""
        self._sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self._sock.bind(("0.0.0.0", port))
        self._sock.setblocking(False)

    def get_state(self) -> str | None:
        """Get latest state if available, None otherwise."""
        try:
            data, _ = self._sock.recvfrom(1024)
            msg = json.loads(data.decode("utf-8"))
            return msg.get("state")
        except BlockingIOError:
            return None
        except (json.JSONDecodeError, UnicodeDecodeError):
            # Ignore malformed UDP packets
            return None

    def cleanup(self) -> None:
        """Close UDP socket."""
        self._sock.close()

    def __enter__(self) -> "StateReceiver":
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        self.cleanup()


class PulseAnimation(Animation):
    """Breathing/pulse circle animation."""

    PARAMS = {
        "idle": {"speed": 1.0, "min_r": 80, "max_r": 120, "color": (100, 180, 255)},
        "listening": {"speed": 3.0, "min_r": 60, "max_r": 140, "color": (255, 200, 100)},
        "speaking": {"speed": 2.0, "min_r": 90, "max_r": 130, "color": (100, 255, 150)},
    }

    def __init__(self, screen: pygame.Surface) -> None:
        """Initialize animation with pygame screen."""
        self._screen = screen
        self._state = "idle"
        self._time = 0.0

    def set_state(self, state: str) -> None:
        """Set current animation state (idle/listening/speaking)."""
        if state in self.PARAMS:
            self._state = state

    def update(self, dt: float) -> None:
        """Update animation and render to screen."""
        self._time += dt
        p = self.PARAMS[self._state]

        # サイン波でパルス（-1〜1 → 0〜1 に変換）
        phase = (math.sin(self._time * p["speed"] * 2 * math.pi) + 1) / 2
        radius = int(p["min_r"] + (p["max_r"] - p["min_r"]) * phase)

        # 画面中央を計算
        center = (self._screen.get_width() // 2, self._screen.get_height() // 2)

        # 背景を塗りつぶして円を描画
        self._screen.fill((20, 20, 30))
        pygame.draw.circle(self._screen, p["color"], center, radius)


class AnimationEngine:
    """Main animation loop controller."""

    def __init__(self, fullscreen: bool = True) -> None:
        """Initialize pygame and animation."""
        pygame.init()

        if fullscreen:
            self._screen = pygame.display.set_mode((0, 0), pygame.FULLSCREEN)
        else:
            self._screen = pygame.display.set_mode((800, 600))

        pygame.display.set_caption("PokePal Display")
        self._clock = pygame.time.Clock()
        self._animation = PulseAnimation(self._screen)

    def run(self, state_receiver: StateReceiver) -> None:
        """Main loop: receive state updates and render animation."""
        running = True
        last_state_time = 0.0
        timeout_seconds = 5.0

        while running:
            # イベント処理（終了判定）
            # TODO: 本番運用時は削除するか、systemdで自動再起動する設定を入れる
            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    running = False
                if event.type == pygame.KEYDOWN and event.key == pygame.K_ESCAPE:
                    running = False

            # 状態更新をチェック
            new_state = state_receiver.get_state()
            if new_state:
                self._animation.set_state(new_state)
                last_state_time = 0.0
            else:
                last_state_time += self._clock.get_time() / 1000.0
                # タイムアウト：5秒間データがなければidleに戻す
                if last_state_time > timeout_seconds:
                    self._animation.set_state("idle")
                    last_state_time = 0.0

            # アニメーション更新と描画
            dt = self._clock.tick(30) / 1000.0
            self._animation.update(dt)
            pygame.display.flip()

    def cleanup(self) -> None:
        """Cleanup pygame resources."""
        pygame.quit()

    def __enter__(self) -> "AnimationEngine":
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        self.cleanup()


def main() -> None:
    """Entry point for display animation app."""
    with StateReceiver() as receiver:
        with AnimationEngine(fullscreen=True) as engine:
            engine.run(receiver)


if __name__ == "__main__":
    main()
