import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
SETUP_PS1 = REPO_ROOT / "setup.ps1"


class SetupPs1StaticTests(unittest.TestCase):
    def test_windows_setup_helper_exists_with_expected_interface(self):
        script = SETUP_PS1.read_text(encoding="utf-8")

        self.assertIn("[string]$Example", script)
        self.assertIn("[switch]$Run", script)
        self.assertIn("$PSScriptRoot", script)

    def test_windows_setup_helper_matches_bash_safety_behaviors(self):
        script = SETUP_PS1.read_text(encoding="utf-8")

        self.assertIn("Test-Path", script)
        self.assertIn(".env.example", script)
        self.assertIn("-not (Test-Path", script)
        self.assertIn("requirements.txt", script)
        for entry_file in ("agent.py", "main.py", "workflow.py", "app.py"):
            self.assertIn(entry_file, script)

    def test_windows_setup_helper_checks_python_and_uses_venv_python(self):
        script = SETUP_PS1.read_text(encoding="utf-8")

        self.assertIn("python", script)
        self.assertIn("py", script)
        self.assertIn("[version]", script)
        self.assertIn("3.10", script)
        self.assertIn("Scripts", script)
        self.assertIn("python.exe", script)


if __name__ == "__main__":
    unittest.main()
