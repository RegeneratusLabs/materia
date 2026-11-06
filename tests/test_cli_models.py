from types import SimpleNamespace

from materia.cli import cmd_models


def test_models_command_lists_local_cpu_config(capsys):
    assert cmd_models(SimpleNamespace(check=False)) == 0
    out = capsys.readouterr().out
    assert "models dir:" in out
    assert "llama-server:" in out
    assert "reason model:" in out
    assert "chat endpoint:" in out


def test_cli_version():
    import subprocess
    import sys
    from pathlib import Path

    root = Path(__file__).resolve().parent.parent
    result = subprocess.run(
        [sys.executable, "-m", "materia.cli", "--version"],
        cwd=root, capture_output=True, text=True, check=True,
    )
    assert result.stdout.strip().startswith("materia 1.0.0")


def test_doctor_reports_a_healthy_install(capsys):
    from materia.cli import cmd_doctor

    assert cmd_doctor(SimpleNamespace()) == 0
    out = capsys.readouterr().out
    assert "status  OK" in out
    assert "corpus" in out
    assert "patterns" in out
