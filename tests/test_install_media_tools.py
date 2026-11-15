#!/usr/bin/env python3
# Copyright 2026 Agent Skill Forge Contributors
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

"""Tests for installer ``--with-media-tools`` opt-in and legacy model cleanup.

Covers:
1. Syntax and AST parse validation for ``scripts/install.sh`` and ``scripts/install.ps1``.
2. Conflict guard (``--with-media-tools --offline`` exits 2 before fetch/sync/HOME writes).
3. Flag stripping before ``sync_skills.py``, opt-in ``curl`` installation into
   ``~/.local/bin``, fail-closed exit on install failure, non-fatal ``whoami``,
   and ``GEMINI_API_KEY`` shadowing differentiation (T1 + T4).
4. Default-mode 2-line readiness note differentiation (``--spine`` vs ``--content``;
   ``missing`` vs ``found``) with zero unprompted tool installation.
5. Zero ``sudo`` across both installers and PowerShell ``} else {`` invariant parity.
6. Cleanup of legacy ``"flash_medium"``, reviewer ``"flash"``, and stale skill names
   across prompt DAG templates, ``persona_roles.md``, ``codelab``, and ``atelier``.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import unittest
import zipfile
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
INSTALL_SH = REPO_ROOT / "scripts" / "install.sh"
INSTALL_PS1 = REPO_ROOT / "scripts" / "install.ps1"

DAG_JSON_FILES = [
    REPO_ROOT / "skills" / "prompt" / "references" / "dag_templates" / "coding_pipeline.json",
    REPO_ROOT / "skills" / "prompt" / "references" / "dag_templates" / "ui_design_pipeline.json",
    REPO_ROOT / "skills" / "prompt" / "references" / "dag_templates" / "verification_pipeline.json",
    REPO_ROOT / "skills" / "prompt" / "references" / "dag_templates" / "security_pipeline.json",
    REPO_ROOT / "skills" / "prompt" / "references" / "dag_templates" / "research_pipeline.json",
    REPO_ROOT / "skills" / "prompt" / "examples" / "example_dag_deck" / "task_graph.json",
]


def _write_executable(directory: Path, name: str, body: str) -> Path:
    path = directory / name
    path.write_text(body, encoding="utf-8")
    path.chmod(0o755)
    return path


def _make_stub_gemini_api(directory: Path, log_path: Path, whoami_exit: int = 0) -> Path:
    return _write_executable(
        directory,
        "gemini-api",
        f"""#!/bin/sh
printf '%s\\n' "$*" >> "{log_path}"
if [ "${{1:-}}" = "--version" ]; then
    echo "gemini-api 0.4.0-stub"
    exit 0
fi
    if [ "${{1:-}}" = "whoami" ]; then
        if [ "{whoami_exit}" -ne 0 ]; then
            echo '{{"authenticated": false}}'
            exit {whoami_exit}
        fi
        echo '{{"authenticated": true, "method": "keyring", "email": "sensitive-user@example.test"}}'
        exit 0
    fi
exit 0
""",
    )


def _make_stub_ffmpeg_tools(directory: Path) -> None:
    for tool in ("ffmpeg", "ffprobe"):
        _write_executable(
            directory,
            tool,
            f"#!/bin/sh\necho '{tool} 7.0-stub'\nexit 0\n",
        )


def _make_stub_python3(directory: Path, argv_log: Path) -> None:
    for py_name in ("python3", "python3.12", "python3.13", "python", "py"):
        _write_executable(
            directory,
            py_name,
            f"""#!/bin/sh
printf '%s\\n' "$*" >> "{argv_log}"
exit 0
""",
        )


class InstallerSyntaxAndParityTests(unittest.TestCase):
    """Syntax, AST parse, zero-sudo, and usage-banner parity across installers."""

    @unittest.skipIf(sys.platform == "win32", "bash -n is POSIX-only")
    def test_install_sh_passes_bash_syntax_check(self):
        proc = subprocess.run(
            ["bash", "-n", str(INSTALL_SH)],
            capture_output=True,
            text=True,
        )
        self.assertEqual(proc.returncode, 0, proc.stderr)

    def test_install_ps1_passes_pwsh_ast_parse(self):
        pwsh = shutil.which("pwsh")
        if pwsh is None:
            self.skipTest("pwsh not installed on this host")
        ps_cmd = (
            "$ErrorActionPreference = 'Stop'; "
            "$tokens = $null; $errors = $null; "
            f"[System.Management.Automation.Language.Parser]::ParseFile('{INSTALL_PS1}', [ref]$tokens, [ref]$errors) | Out-Null; "
            "if ($errors.Count -gt 0) { $errors | ForEach-Object { [Console]::Error.WriteLine($_.Message) }; exit 1 }"
        )
        proc = subprocess.run([pwsh, "-NoProfile", "-Command", ps_cmd], capture_output=True, text=True)
        self.assertEqual(proc.returncode, 0, proc.stdout + proc.stderr)

    def test_installers_contain_zero_sudo_and_document_media_tools_flag(self):
        sh_src = INSTALL_SH.read_text(encoding="utf-8")
        ps_src = INSTALL_PS1.read_text(encoding="utf-8")

        self.assertIsNone(
            re.search(r"\bsudo\b", ps_src),
            "install.ps1 must never contain or invoke sudo",
        )
        # install.sh may mention sudo ONLY inside static informational echo hints (never executed).
        for lineno, line in enumerate(sh_src.splitlines(), start=1):
            stripped = line.strip()
            if stripped.startswith("#") or not re.search(r"\bsudo\b", line):
                continue
            self.assertRegex(
                stripped,
                r'^echo\s+"[^"]*"$',
                f"install.sh:{lineno} must never execute sudo (only static echo hints allowed): {line!r}",
            )
            self.assertNotIn("$(", line, f"install.sh:{lineno} sudo hint must not contain command substitution")
            self.assertNotIn("`", line, f"install.sh:{lineno} sudo hint must not contain backticks")

        for name, src in (("install.sh", sh_src), ("install.ps1", ps_src)):
            self.assertIn("--with-media-tools", src, f"{name} missing --with-media-tools")
            for seam in (
                "FORGE_GEMINI_API_INSTALL_CMD",
                "FORGE_GEMINI_API_INSTALL_URL",
                "FORGE_GEMINI_API_RELEASE_URL",
            ):
                self.assertIn(seam, src, f"{name} must document offline test seam {seam}")

        # Windows release SHA-256 verification and scheme enforcement contract in install.ps1
        self.assertIn("Assert-SafeMediaToolUrl", ps_src)
        self.assertIn("^(https|file)://", ps_src)
        self.assertNotIn("-match 'windows|win'", ps_src)
        self.assertIn("(^|[_.-])(windows|win32|win64)([_.-]|$)", ps_src)
        self.assertIn(r"\.(zip|exe)$", ps_src)
        self.assertIn("SecurityProtocolType]::Tls12", ps_src)
        self.assertIn("[System.IO.Path]::GetFileName", ps_src)
        self.assertIn("--scope user", ps_src)
        self.assertIn("checksums", ps_src)
        self.assertIn(".sha256", ps_src)
        self.assertIn("Get-FileHash -LiteralPath $dlFile -Algorithm SHA256", ps_src)
        self.assertIn("SHA-256 checksum mismatch", ps_src)
        self.assertIn("[Console]::Error.WriteLine", ps_src)
        # Cross-platform Join-Path hygiene: no backslash literals inside Join-Path or script calls
        self.assertIsNone(re.search(r"Join-Path\s+[^'\r\n]*'[^']*\\", ps_src))
        self.assertIsNone(re.search(r'"\$(?:ScriptDir|RepoRoot)\\', ps_src))

        # Preserve test_install_ownership.py invariant: last `} else {` in install.ps1
        # must still lead directly into the non-interactive sync_skills.py branch.
        tail = ps_src.split("} else {")[-1]
        self.assertIn("sync_skills.py", tail)
        self.assertNotIn("--prune", tail)


@unittest.skipIf(sys.platform == "win32", "install.sh is the POSIX entry point")
class PosixInstallerMediaToolsTests(unittest.TestCase):
    """Behavioral tests for install.sh --with-media-tools and default readiness."""

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory(prefix="forge_media_inst_")
        self.addCleanup(self._tmp.cleanup)
        self.root = Path(self._tmp.name)
        self.home = self.root / "home"
        self.home.mkdir()
        self.bin_dir = self.root / "bin"
        self.bin_dir.mkdir()
        # Expose real python3 explicitly in bin_dir unless overridden with a stub,
        # and exclude /opt/homebrew/bin so ambient ffmpeg does not leak into tests.
        py_link = self.bin_dir / "python3"
        os.symlink(sys.executable, py_link)

    def _base_env(self, extra: dict[str, str] | None = None) -> dict[str, str]:
        env = dict(os.environ)
        env["HOME"] = str(self.home)
        env["USERPROFILE"] = str(self.home)
        env["PATH"] = f"{self.bin_dir}{os.pathsep}/usr/bin{os.pathsep}/bin"
        env.pop("GEMINI_API_KEY", None)
        env.pop("AGENT_PERSONA_REPO", None)
        env.pop("FORGE_GEMINI_API_INSTALL_CMD", None)
        env.pop("FORGE_GEMINI_API_INSTALL_URL", None)
        env.pop("FORGE_GEMINI_API_RELEASE_URL", None)
        if extra:
            env.update(extra)
        return env

    def _run_install(self, *args: str, extra_env: dict[str, str] | None = None) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            ["bash", str(INSTALL_SH), *args],
            capture_output=True,
            text=True,
            stdin=subprocess.DEVNULL,
            env=self._base_env(extra_env),
        )

    def test_with_media_tools_and_offline_exits_2_before_fetch_or_sync(self):
        """T4 negative guard: conflicting flags exit 2 and touch nothing in HOME."""
        argv_log = self.root / "python_argv.log"
        (self.bin_dir / "python3").unlink()
        _make_stub_python3(self.bin_dir, argv_log)

        proc = self._run_install("--with-media-tools", "--offline")
        self.assertEqual(proc.returncode, 2, proc.stdout + proc.stderr)
        self.assertIn("--with-media-tools", proc.stderr)
        self.assertIn("--offline", proc.stderr)
        self.assertFalse(argv_log.exists(), "fetch_upstream.py or sync_skills.py ran despite conflict")
        self.assertEqual(list(self.home.iterdir()), [], "conflict guard touched HOME")

    def test_pwsh_with_media_tools_and_offline_exits_2(self):
        pwsh = shutil.which("pwsh")
        if pwsh is None:
            self.skipTest("pwsh not installed on this host")
        argv_log = self.root / "python_argv.log"
        (self.bin_dir / "python3").unlink()
        _make_stub_python3(self.bin_dir, argv_log)
        proc = subprocess.run(
            [pwsh, "-NoProfile", "-File", str(INSTALL_PS1), "--with-media-tools", "--offline"],
            capture_output=True,
            text=True,
            stdin=subprocess.DEVNULL,
            env=self._base_env(),
        )
        self.assertEqual(proc.returncode, 2, proc.stdout + proc.stderr)
        self.assertIn("--with-media-tools", proc.stdout + proc.stderr)
        self.assertFalse(argv_log.exists(), "install.ps1 invoked python despite conflict")

    def test_pwsh_with_media_tools_verifies_release_sha256_and_picks_windows_zip(self):
        """REV-001/REV-002: pwsh behavioral test over file:// release JSON + darwin-first trap + SHA-256."""
        pwsh = shutil.which("pwsh")
        if pwsh is None:
            self.skipTest("pwsh not installed on this host")

        bin_dir = self.root / "ps_bin"
        bin_dir.mkdir()
        artifacts = self.root / "ps_artifacts"
        artifacts.mkdir()
        py_log = self.root / "ps_python_argv.log"
        _make_stub_python3(bin_dir, py_log)
        _make_stub_ffmpeg_tools(bin_dir)

        darwin_tar = artifacts / "gemini-api_darwin_amd64.tar.gz"
        darwin_tar.write_bytes(b"FAKE-DARWIN-TARBALL-BYTES")
        darwin_sha = hashlib.sha256(darwin_tar.read_bytes()).hexdigest()

        win_exe_bytes = b"FAKE-WIN-EXE-BINARY-CONTENT"
        win_zip = artifacts / "gemini-api_windows_amd64.zip"
        with zipfile.ZipFile(win_zip, "w") as zf:
            zf.writestr("bin/gemini-api.exe", win_exe_bytes)
        win_sha = hashlib.sha256(win_zip.read_bytes()).hexdigest()

        def run_ps(release_uri: str, home_dir: Path) -> subprocess.CompletedProcess[str]:
            env = self._base_env({"FORGE_GEMINI_API_RELEASE_URL": release_uri})
            env["HOME"] = str(home_dir)
            env["USERPROFILE"] = str(home_dir)
            env["PATH"] = f"{bin_dir}{os.pathsep}/usr/bin{os.pathsep}/bin"
            return subprocess.run(
                [pwsh, "-NoProfile", "-File", str(INSTALL_PS1), "--no-fetch", "--content", "--with-media-tools"],
                capture_output=True,
                text=True,
                stdin=subprocess.DEVNULL,
                env=env,
            )

        # 0. Insecure http:// URL fails exit 2 before invoking python3 sync_skills.py
        home0 = self.root / "ps_home0"
        home0.mkdir()
        proc_http = run_ps("http://insecure.example.test/releases.json", home0)
        self.assertEqual(proc_http.returncode, 2, proc_http.stdout + proc_http.stderr)
        self.assertFalse(py_log.exists(), "http:// URL ran sync_skills.py before failing")

        # 1. Mismatched checksum -> non-zero exit and no binary written
        bad_sums = artifacts / "checksums_bad.txt"
        bad_sums.write_text(
            f"{darwin_sha}  {darwin_tar.name}\n{'0' * 64}  {win_zip.name}\n",
            encoding="utf-8",
        )
        rel_bad = artifacts / "release_bad.json"
        rel_bad.write_text(
            json.dumps(
                {
                    "assets": [
                        {"name": darwin_tar.name, "browser_download_url": darwin_tar.as_uri()},
                        {"name": win_zip.name, "browser_download_url": win_zip.as_uri()},
                        {"name": "checksums.txt", "browser_download_url": bad_sums.as_uri()},
                    ]
                }
            ),
            encoding="utf-8",
        )
        home1 = self.root / "ps_home1"
        home1.mkdir()
        proc_bad = run_ps(rel_bad.as_uri(), home1)
        self.assertNotEqual(proc_bad.returncode, 0, proc_bad.stdout + proc_bad.stderr)
        self.assertIn("SHA-256 checksum mismatch", proc_bad.stderr)
        self.assertFalse((home1 / ".local" / "bin" / "gemini-api.exe").exists())

        # 2. Matching checksum + darwin listed before windows -> picks windows.zip and installs exe
        good_sums = artifacts / "checksums_good.txt"
        good_sums.write_text(
            f"{darwin_sha}  {darwin_tar.name}\n{win_sha}  {win_zip.name}\n",
            encoding="utf-8",
        )
        rel_good = artifacts / "release_good.json"
        rel_good.write_text(
            json.dumps(
                {
                    "assets": [
                        {"name": darwin_tar.name, "browser_download_url": darwin_tar.as_uri()},
                        {"name": win_zip.name, "browser_download_url": win_zip.as_uri()},
                        {"name": "checksums.txt", "browser_download_url": good_sums.as_uri()},
                    ]
                }
            ),
            encoding="utf-8",
        )
        home2 = self.root / "ps_home2"
        home2.mkdir()
        proc_good = run_ps(rel_good.as_uri(), home2)
        self.assertEqual(proc_good.returncode, 0, proc_good.stdout + proc_good.stderr)
        installed_exe = home2 / ".local" / "bin" / "gemini-api.exe"
        self.assertTrue(installed_exe.is_file())
        self.assertEqual(installed_exe.read_bytes(), win_exe_bytes)
        self.assertIn("Verified SHA-256 checksum", proc_good.stdout)

        # 3. Missing checksum asset -> loud stderr WARNING and installs exe
        rel_nosum = artifacts / "release_nosum.json"
        rel_nosum.write_text(
            json.dumps(
                {
                    "assets": [
                        {"name": darwin_tar.name, "browser_download_url": darwin_tar.as_uri()},
                        {"name": win_zip.name, "browser_download_url": win_zip.as_uri()},
                    ]
                }
            ),
            encoding="utf-8",
        )
        home3 = self.root / "ps_home3"
        home3.mkdir()
        proc_nosum = run_ps(rel_nosum.as_uri(), home3)
        self.assertEqual(proc_nosum.returncode, 0, proc_nosum.stdout + proc_nosum.stderr)
        self.assertTrue((home3 / ".local" / "bin" / "gemini-api.exe").is_file())
        self.assertIn("WARNING:", proc_nosum.stderr)
        self.assertIn("no checksums.txt or .sha256 asset", proc_nosum.stderr)

    def test_with_media_tools_strips_flag_runs_whoami_and_differentiates_api_key_warning(self):
        """Real sync_skills.py runs without choking; T1 differentiates GEMINI_API_KEY set vs unset."""
        cli_log = self.root / "gemini_api.log"
        _make_stub_gemini_api(self.bin_dir, cli_log)
        _make_stub_ffmpeg_tools(self.bin_dir)

        # Case 1: GEMINI_API_KEY unset -> silent on shadowing warning
        proc_clean = self._run_install("--no-fetch", "--content", "--with-media-tools")
        self.assertEqual(proc_clean.returncode, 0, proc_clean.stdout + proc_clean.stderr)
        self.assertTrue(
            (self.home / ".agents" / "skills" / "image-gen" / "SKILL.md").is_file(),
            "real sync_skills.py --content did not link image-gen",
        )
        logged = cli_log.read_text(encoding="utf-8")
        self.assertIn("--version", logged)
        self.assertIn("whoami -o json", logged)
        self.assertIn("gemini-api auth (whoami): authenticated", proc_clean.stdout)
        self.assertNotIn("sensitive-user@example.test", proc_clean.stdout + proc_clean.stderr)
        self.assertNotIn("GEMINI_API_KEY", proc_clean.stdout + proc_clean.stderr)
        self.assertNotIn("shadow", proc_clean.stdout + proc_clean.stderr)

        # Case 2: GEMINI_API_KEY set -> clear shadowing warning pointing to aistudio docs
        cli_log.unlink()
        proc_keyed = self._run_install(
            "--no-fetch",
            "--content",
            "--with-media-tools",
            extra_env={"GEMINI_API_KEY": "dummy-test-key"},
        )
        self.assertEqual(proc_keyed.returncode, 0, proc_keyed.stdout + proc_keyed.stderr)
        combined = proc_keyed.stdout + proc_keyed.stderr
        self.assertIn("GEMINI_API_KEY", combined)
        self.assertIn("shadow", combined)
        self.assertIn("https://aistudio.google.com/docs/cli", combined)
        self.assertNotEqual(proc_clean.stdout, proc_keyed.stdout)

    def test_with_media_tools_installs_missing_gemini_api_via_curl_into_local_bin(self):
        """Missing gemini-api invokes official curl installer and resolves ~/.local/bin."""
        curl_log = self.root / "curl_args.log"
        cli_log = self.root / "installed_cli.log"
        _make_stub_ffmpeg_tools(self.bin_dir)
        _write_executable(
            self.bin_dir,
            "curl",
            f"""#!/bin/sh
printf '%s\\n' "$*" >> "{curl_log}"
cat <<'EOS'
mkdir -p "$HOME/.local/bin"
cat <<'EOB' > "$HOME/.local/bin/gemini-api"
#!/bin/sh
printf '%s\\n' "$*" >> "{cli_log}"
if [ "${{1:-}}" = "--version" ]; then
    echo "gemini-api 0.4.0-bootstrapped"
    exit 0
fi
if [ "${{1:-}}" = "whoami" ]; then
    echo '{{"authenticated": false}}'
    exit 1
fi
exit 0
EOB
chmod +x "$HOME/.local/bin/gemini-api"
EOS
""",
        )

        proc = self._run_install("--no-fetch", "--content", "--with-media-tools")
        self.assertEqual(proc.returncode, 0, proc.stdout + proc.stderr)
        self.assertIn(
            "https://raw.githubusercontent.com/google-gemini/gemini-api-cli/main/scripts/install.sh",
            curl_log.read_text(encoding="utf-8"),
        )
        installed_bin = self.home / ".local" / "bin" / "gemini-api"
        self.assertTrue(os.access(installed_bin, os.X_OK), "bootstrapped gemini-api is not executable")
        cli_calls = cli_log.read_text(encoding="utf-8")
        self.assertIn("--version", cli_calls)
        self.assertIn("whoami -o json", cli_calls)
        self.assertIn("not authenticated", proc.stdout)

    def test_with_media_tools_exits_nonzero_when_gemini_api_install_fails(self):
        """T4 negative test: explicit --with-media-tools fails non-zero if gemini-api cannot install."""
        _make_stub_ffmpeg_tools(self.bin_dir)
        _write_executable(self.bin_dir, "curl", "#!/bin/sh\nexit 22\n")

        proc = self._run_install("--no-fetch", "--content", "--with-media-tools")
        self.assertNotEqual(proc.returncode, 0, "expected non-zero exit when gemini-api install fails")
        self.assertIn("https://aistudio.google.com/docs/cli", proc.stderr)

    def test_with_media_tools_handles_missing_ffmpeg_per_platform_without_sudo(self):
        """T1: Darwin uses brew install ffmpeg; Linux prints apt/dnf/pacman without brew or sudo."""
        cli_log = self.root / "cli_ffmpeg.log"
        brew_log = self.root / "brew.log"
        _make_stub_gemini_api(self.bin_dir, cli_log)

        # Case A: Darwin -> runs brew install ffmpeg
        _write_executable(self.bin_dir, "uname", "#!/bin/sh\necho Darwin\n")
        _write_executable(
            self.bin_dir,
            "brew",
            f"""#!/bin/sh
printf '%s\\n' "$*" >> "{brew_log}"
exit 0
""",
        )
        proc_darwin = self._run_install("--no-fetch", "--content", "--with-media-tools")
        self.assertEqual(proc_darwin.returncode, 0, proc_darwin.stdout + proc_darwin.stderr)
        self.assertIn("install ffmpeg", brew_log.read_text(encoding="utf-8"))

        # Case B: Linux -> prints sudo apt/dnf/pacman guidance without calling brew or sudo
        brew_log.unlink()
        sudo_log = self.root / "sudo.log"
        _write_executable(
            self.bin_dir,
            "sudo",
            f"#!/bin/sh\nprintf '%s\\n' \"$*\" >> \"{sudo_log}\"\nexit 99\n",
        )
        _write_executable(self.bin_dir, "uname", "#!/bin/sh\necho Linux\n")
        proc_linux = self._run_install("--no-fetch", "--content", "--with-media-tools")
        self.assertEqual(proc_linux.returncode, 0, proc_linux.stdout + proc_linux.stderr)
        self.assertFalse(brew_log.exists(), "Linux path should not invoke brew")
        self.assertFalse(sudo_log.exists(), "Linux path must never execute sudo")
        self.assertIn("sudo apt install ffmpeg", proc_linux.stdout)
        self.assertIn("sudo dnf install ffmpeg", proc_linux.stdout)
        self.assertIn("sudo pacman -S ffmpeg", proc_linux.stdout)

    def test_with_media_tools_rejects_insecure_http_url_seams_and_accepts_file_scheme(self):
        """T4/REV-004: FORGE_GEMINI_API_INSTALL_URL/_RELEASE_URL reject http:// before sync_skills.py."""
        _make_stub_ffmpeg_tools(self.bin_dir)
        py_log = self.root / "python_argv.log"
        orig_py = self.bin_dir / "python3"
        curl_log = self.root / "curl_scheme.log"
        _write_executable(
            self.bin_dir,
            "curl",
            f"""#!/bin/sh
printf '%s\\n' "$*" >> "{curl_log}"
cat <<'EOS'
mkdir -p "$HOME/.local/bin"
cat <<'EOB' > "$HOME/.local/bin/gemini-api"
#!/bin/sh
exit 0
EOB
chmod +x "$HOME/.local/bin/gemini-api"
EOS
""",
        )

        # Swap python3 with stub to prove http:// fails BEFORE fetch_upstream/sync_skills write to HOME
        orig_py.unlink()
        _make_stub_python3(self.bin_dir, py_log)

        # Plain http:// on FORGE_GEMINI_API_INSTALL_URL exits 2 before python3 or curl
        proc_http_url = self._run_install(
            "--no-fetch",
            "--content",
            "--with-media-tools",
            extra_env={"FORGE_GEMINI_API_INSTALL_URL": "http://insecure.example.test/install.sh"},
        )
        self.assertEqual(proc_http_url.returncode, 2, proc_http_url.stdout + proc_http_url.stderr)
        self.assertIn("https:// or file://", proc_http_url.stderr)
        self.assertFalse(py_log.exists(), "http:// seam invoked fetch_upstream/sync_skills before failing")
        self.assertFalse(curl_log.exists(), "http:// seam reached curl")

        # Plain http:// on FORGE_GEMINI_API_RELEASE_URL exits 2 before python3 or curl
        proc_http_rel = self._run_install(
            "--no-fetch",
            "--content",
            "--with-media-tools",
            extra_env={"FORGE_GEMINI_API_RELEASE_URL": "http://insecure.example.test/releases/latest"},
        )
        self.assertEqual(proc_http_rel.returncode, 2, proc_http_rel.stdout + proc_http_rel.stderr)
        self.assertIn("https:// or file://", proc_http_rel.stderr)
        self.assertFalse(py_log.exists(), "http:// release seam invoked fetch_upstream/sync_skills")
        self.assertFalse(curl_log.exists(), "http:// release seam reached curl")

        # Restore real python3 for file:// end-to-end sync + curl pass check
        for py_name in ("python3", "python3.12", "python3.13", "python", "py"):
            (self.bin_dir / py_name).unlink(missing_ok=True)
        os.symlink(sys.executable, orig_py)

        # file:// scheme is accepted and passed through to curl
        local_url = f"file://{self.root}/local_install.sh"
        proc_file = self._run_install(
            "--no-fetch",
            "--content",
            "--with-media-tools",
            extra_env={"FORGE_GEMINI_API_INSTALL_URL": local_url},
        )
        self.assertEqual(proc_file.returncode, 0, proc_file.stdout + proc_file.stderr)
        self.assertIn(local_url, curl_log.read_text(encoding="utf-8"))

    def test_default_mode_readiness_note_differentiates_selection_and_tools_without_installing(self):
        """T1: default mode prints 2-line readiness note for C3/project/default, omits for --spine/--skills work."""
        trap_log = self.root / "trap_install.log"
        for installer_bin in ("curl", "brew"):
            _write_executable(
                self.bin_dir,
                installer_bin,
                f"#!/bin/sh\necho '{installer_bin} invoked' >> \"{trap_log}\"\nexit 99\n",
            )

        # Case 1: --spine only -> no readiness summary emitted
        proc_spine = self._run_install("--no-fetch", "--spine")
        self.assertEqual(proc_spine.returncode, 0, proc_spine.stdout + proc_spine.stderr)
        self.assertNotIn("gemini-api=", proc_spine.stdout)

        # Case 1b: --skills work -> non-media skill, no readiness summary emitted
        proc_work = self._run_install("--no-fetch", "--skills", "work")
        self.assertEqual(proc_work.returncode, 0, proc_work.stdout + proc_work.stderr)
        self.assertNotIn("gemini-api=", proc_work.stdout)

        # Case 2: --content without tools on PATH -> missing status + --with-media-tools hint
        proc_missing = self._run_install("--no-fetch", "--content")
        self.assertEqual(proc_missing.returncode, 0, proc_missing.stdout + proc_missing.stderr)
        self.assertIn("gemini-api=missing", proc_missing.stdout)
        self.assertIn("ffmpeg=missing", proc_missing.stdout)
        self.assertIn("ffprobe=missing", proc_missing.stdout)
        self.assertIn("--with-media-tools", proc_missing.stdout)

        # Case 2b: --project <dir> --clusters c3 -> project workspace links image-gen & emits readiness
        project_dir = self.root / "proj"
        project_dir.mkdir()
        proc_proj = self._run_install("--no-fetch", "--project", str(project_dir), "--clusters", "c3")
        self.assertEqual(proc_proj.returncode, 0, proc_proj.stdout + proc_proj.stderr)
        self.assertTrue((project_dir / ".gemini" / "skills" / "image-gen" / "SKILL.md").is_file())
        self.assertIn("gemini-api=missing", proc_proj.stdout)

        # Case 3: default sync (no selection flags) with tools on PATH -> found status (T1 opposite output)
        cli_log = self.root / "cli.log"
        _make_stub_gemini_api(self.bin_dir, cli_log)
        _make_stub_ffmpeg_tools(self.bin_dir)
        proc_found = self._run_install("--no-fetch")
        self.assertEqual(proc_found.returncode, 0, proc_found.stdout + proc_found.stderr)
        self.assertIn("gemini-api=found", proc_found.stdout)
        self.assertIn("ffmpeg=found", proc_found.stdout)
        self.assertIn("ffprobe=found", proc_found.stdout)
        self.assertNotEqual(proc_missing.stdout, proc_found.stdout)
        self.assertFalse(trap_log.exists(), "default mode attempted unprompted binary installation")
        self.assertFalse(cli_log.exists(), "default mode executed gemini-api beyond PATH readiness check")


class LegacyModelAndSkillReferenceCleanupTests(unittest.TestCase):
    """Verify legacy model tiers and stale skill references are replaced cleanly."""

    ALLOWED_DAG_MODEL_TIERS = {"pro", "inherit", "flash"}

    def test_dag_templates_and_example_parse_cleanly_and_drop_flash_medium(self):
        for path in DAG_JSON_FILES:
            with self.subTest(file=path.name):
                raw = path.read_text(encoding="utf-8")
                self.assertNotIn("flash_medium", raw, f"obsolete tier flash_medium found in {path}")
                data = json.loads(raw)
                nodes = data.get("nodes", [])
                self.assertGreater(len(nodes), 0, f"no DAG nodes in {path}")
                for node in nodes:
                    tier = node.get("model_tier")
                    self.assertIn(tier, self.ALLOWED_DAG_MODEL_TIERS, f"{path.name}:{node.get('id')} bad tier {tier!r}")
                    role = (node.get("subagent_role") or "").lower()
                    # ENGINEERING_STANDARD §10.5: reviewers, auditors, builders, designers, analysts
                    # must not run on flash; only purely mechanical scouts / test runners may.
                    is_mechanical_only = ("scout" in role) or ("test runner" in role)
                    if not is_mechanical_only:
                        self.assertIn(
                            tier,
                            {"pro", "inherit"},
                            f"{path.name}:{node.get('id')} ({node.get('subagent_role')}) must use pro/inherit, got {tier!r}",
                        )

    def test_persona_roles_dispatches_sentry_gatekeeper_on_inherit_without_legacy_subagents_wrapper(self):
        persona_doc = (REPO_ROOT / "skills" / "verify" / "references" / "persona_roles.md").read_text(encoding="utf-8")
        self.assertNotIn('"Model": "flash"', persona_doc)
        self.assertNotIn("Subagents=[", persona_doc)
        self.assertIn('Model="inherit"', persona_doc)
        self.assertIn('Role="Sentry-Gatekeeper"', persona_doc)

    def test_codelab_and_atelier_reference_current_media_skills_within_line_budget(self):
        codelab = (REPO_ROOT / "skills" / "codelab" / "SKILL.md").read_text(encoding="utf-8")
        atelier = (REPO_ROOT / "skills" / "atelier" / "SKILL.md").read_text(encoding="utf-8")
        catalog = (REPO_ROOT / "docs" / "catalog_reference.md").read_text(encoding="utf-8")
        spec_doc = (REPO_ROOT / "docs" / "design" / "image-gen-cli-spec.md").read_text(encoding="utf-8")

        self.assertNotIn("image-gen-expert", codelab)
        self.assertIn("skills/image-gen/SKILL.md", codelab)
        self.assertLessEqual(len(codelab.splitlines()), 200)

        self.assertIn("skills/image-gen/SKILL.md", atelier)
        self.assertLessEqual(len(atelier.splitlines()), 200)

        self.assertIn("legacy alias: `/image-gen-expert`", catalog)
        if (REPO_ROOT / "skills" / "video-gen" / "SKILL.md").is_file():
            self.assertIn("`video-gen`", catalog)
            self.assertIn("skills/video-gen/SKILL.md", codelab)
            self.assertIn("skills/video-gen/SKILL.md", atelier)
        else:
            self.assertIsNone(re.search(r"video[-_]gen", catalog, re.IGNORECASE))
        if (REPO_ROOT / "skills" / "audio-gen" / "SKILL.md").is_file():
            self.assertIn("`audio-gen`", catalog)

        for seam in (
            "FORGE_GEMINI_API_INSTALL_CMD",
            "FORGE_GEMINI_API_INSTALL_URL",
            "FORGE_GEMINI_API_RELEASE_URL",
        ):
            self.assertIn(seam, spec_doc)


if __name__ == "__main__":
    unittest.main()
