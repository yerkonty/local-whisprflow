from unittest.mock import patch, MagicMock
import pytest
import main as main_module


def test_main_exits_with_error_when_app_fails_to_start(capsys):
    with patch("main.App", side_effect=RuntimeError("model load failed")):
        with pytest.raises(SystemExit) as exc_info:
            main_module.main()

        assert exc_info.value.code == 1
        captured = capsys.readouterr()
        assert "model load failed" in captured.out


def test_main_runs_app_when_construction_succeeds():
    with patch("main.App") as mock_app_cls:
        mock_app = MagicMock()
        mock_app_cls.return_value = mock_app

        main_module.main()

        mock_app.run.assert_called_once()
