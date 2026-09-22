from unittest.mock import patch, MagicMock
import numpy as np
from local_whisprflow.recorder import AudioRecorder


def test_start_stop_returns_concatenated_audio():
    with patch("local_whisprflow.recorder.sd.InputStream") as mock_stream_cls:
        mock_stream = MagicMock()
        mock_stream_cls.return_value = mock_stream

        recorder = AudioRecorder(sample_rate=16000, channels=1, max_seconds=60)
        recorder.start()
        recorder._callback(np.array([[0.1], [0.2]], dtype="float32"), 2, None, None)
        recorder._callback(np.array([[0.3]], dtype="float32"), 1, None, None)
        audio = recorder.stop()

        assert audio.shape == (3,)
        np.testing.assert_allclose(audio, [0.1, 0.2, 0.3], atol=1e-6)
        mock_stream.start.assert_called_once()
        mock_stream.stop.assert_called_once()
        mock_stream.close.assert_called_once()


def test_stop_without_start_returns_empty_array():
    recorder = AudioRecorder()
    audio = recorder.stop()
    assert audio.shape == (0,)


def test_duration_seconds():
    recorder = AudioRecorder(sample_rate=16000)
    audio = np.zeros(8000, dtype="float32")
    assert recorder.duration_seconds(audio) == 0.5


def test_start_is_idempotent_while_already_recording():
    with patch("local_whisprflow.recorder.sd.InputStream") as mock_stream_cls:
        mock_stream = MagicMock()
        mock_stream_cls.return_value = mock_stream

        recorder = AudioRecorder()
        recorder.start()
        recorder.start()

        mock_stream_cls.assert_called_once()
