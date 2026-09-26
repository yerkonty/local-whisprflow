import keyboard


class PushToTalkHotkey:
    def __init__(self, key, on_press, on_release):
        self._key = key
        self._on_press = on_press
        self._on_release = on_release
        self._press_handle = None
        self._release_handle = None
        self._pressed = False

    def start(self) -> None:
        self._press_handle = keyboard.on_press_key(self._key, self._handle_press)
        self._release_handle = keyboard.on_release_key(self._key, self._handle_release)

    def stop(self) -> None:
        if self._press_handle is not None:
            try:
                keyboard.unhook(self._press_handle)
            except KeyError:
                pass
            self._press_handle = None
        if self._release_handle is not None:
            try:
                keyboard.unhook(self._release_handle)
            except KeyError:
                pass
            self._release_handle = None

    def _handle_press(self, event) -> None:
        if event is not None and getattr(event, "name", self._key) != self._key:
            return
        if self._pressed:
            return
        self._pressed = True
        self._on_press()

    def _handle_release(self, event) -> None:
        if event is not None and getattr(event, "name", self._key) != self._key:
            return
        if not self._pressed:
            return
        self._pressed = False
        self._on_release()
