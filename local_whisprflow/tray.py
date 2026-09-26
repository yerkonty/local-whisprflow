from PIL import Image, ImageDraw
import pystray

_STATE_COLORS = {
    "idle": (128, 128, 128, 255),
    "recording": (220, 40, 40, 255),
    "transcribing": (230, 180, 30, 255),
}


def _make_icon_image(color):
    image = Image.new("RGBA", (64, 64), (0, 0, 0, 0))
    draw = ImageDraw.Draw(image)
    draw.ellipse((8, 8, 56, 56), fill=color)
    return image


class TrayIcon:
    def __init__(self, on_quit):
        self._on_quit = on_quit
        self._icon_images = {
            name: _make_icon_image(color) for name, color in _STATE_COLORS.items()
        }
        self._icon = pystray.Icon(
            "local_whisprflow",
            icon=self._icon_images["idle"],
            title="Local Whisprflow",
            menu=pystray.Menu(pystray.MenuItem("Quit", self._handle_quit)),
        )

    def set_state(self, state: str) -> None:
        self._icon.icon = self._icon_images[state]

    def _handle_quit(self, icon, item) -> None:
        try:
            self._on_quit()
        finally:
            icon.stop()

    def run(self) -> None:
        self._icon.run()

    def stop(self) -> None:
        self._icon.stop()

    def notify(self, message: str) -> None:
        try:
            self._icon.notify(message)
        except Exception:
            pass
