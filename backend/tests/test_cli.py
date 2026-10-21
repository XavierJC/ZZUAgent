from eduagent.cli import main
from eduagent.services.learning import LearningService
from eduagent.storage.sqlite import SQLiteRepository


def test_cli_synthetic_demo_and_status_restore(data_dir, tmp_path, capsys):
    database = tmp_path / "cli.sqlite3"
    args = ["--data-dir", str(data_dir), "--db", str(database), "--student", "cli-demo"]
    assert main(args + ["--demo", "--goal", "logistic_regression"]) == 0
    output = capsys.readouterr().out
    assert "合成演示" in output and "[finish]" in output
    assert "82.00%" in output and "待人工校验" in output
    assert main(args + ["--status"]) == 0
    assert "82.00%" in capsys.readouterr().out


def test_interactive_invalid_answer_and_exit_dont_update(data_dir, catalog, tmp_path, monkeypatch, capsys):
    database = tmp_path / "interactive.sqlite3"
    answers = iter(["invalid", "q"])
    monkeypatch.setattr("builtins.input", lambda prompt: next(answers))
    args = ["--data-dir", str(data_dir), "--db", str(database), "--student", "interactive"]
    assert main(args) == 0
    assert "未计入记录" in capsys.readouterr().out
    with SQLiteRepository(database) as repository:
        service = LearningService(catalog, repository)
        assert all(s.attempts == 0 for s in service.status("interactive").values())


def test_cli_missing_data_is_reported(tmp_path, capsys):
    assert main(["--data-dir", str(tmp_path / "missing")]) == 2
    assert "无法运行" in capsys.readouterr().out
