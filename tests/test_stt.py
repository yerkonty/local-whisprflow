from unittest.mock import patch, MagicMock
import numpy as np
from local_whisprflow.stt import Transcriber


def test_transcribe_joins_segments_and_strips():
    with patch("local_whisprflow.stt.WhisperModel") as mock_model_cls:
        mock_model = MagicMock()
        segment1 = MagicMock(text=" Hello ")
        segment2 = MagicMock(text="world.")
        mock_model.transcribe.return_value = ([segment1, segment2], MagicMock())
        mock_model_cls.return_value = mock_model

        transcriber = Transcriber(model_size="base.en", device="cpu", compute_type="int8")
        result = transcriber.transcribe(np.zeros(16000, dtype="float32"))

        assert result == "Hello world."
        mock_model_cls.assert_called_once_with("base.en", device="cpu", compute_type="int8")
        _, kwargs = mock_model.transcribe.call_args
        assert kwargs.get("vad_filter") is True
        assert kwargs.get("language") == "en"


def test_transcribe_returns_empty_string_for_no_segments():
    with patch("local_whisprflow.stt.WhisperModel") as mock_model_cls:
        mock_model = MagicMock()
        mock_model.transcribe.return_value = ([], MagicMock())
        mock_model_cls.return_value = mock_model

        transcriber = Transcriber()
        result = transcriber.transcribe(np.zeros(1600, dtype="float32"))

        assert result == ""
