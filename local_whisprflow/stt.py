from faster_whisper import WhisperModel

from . import config


class Transcriber:
    def __init__(
        self,
        model_size=config.MODEL_SIZE,
        device=config.DEVICE,
        compute_type=config.COMPUTE_TYPE,
    ):
        self._model = WhisperModel(model_size, device=device, compute_type=compute_type)

    def transcribe(self, audio) -> str:
        segments, _ = self._model.transcribe(audio, vad_filter=True, language="en")
        text = " ".join(segment.text.strip() for segment in segments)
        return text.strip()
