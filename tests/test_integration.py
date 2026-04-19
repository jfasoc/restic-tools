import os
import random
import re
import subprocess
from unittest.mock import patch

import pytest

from restic_subset_calculator.cli import main


def generate_seeded_file(path, size, seed):
    rng = random.Random(seed)
    with open(path, "wb") as f:
        f.write(rng.randbytes(size))


def run_command(cmd, env=None):
    return subprocess.run(cmd, capture_output=True, check=True, env=env, text=True)


@pytest.fixture
def restic_repo(tmp_path):
    repo = tmp_path / "repo"
    password = "password"
    env = os.environ.copy()
    env["RESTIC_REPOSITORY"] = str(repo)
    env["RESTIC_PASSWORD"] = password

    # Check if restic is installed
    try:
        subprocess.run(["restic", "version"], check=True, capture_output=True)
    except FileNotFoundError:
        pytest.fail("restic is not installed")

    run_command(["restic", "init"], env=env)
    return env, tmp_path


def test_integration_workflow(restic_repo, capsys):
    env, tmp_path = restic_repo
    src = tmp_path / "src"
    src.mkdir()

    seed = 42

    # Round 1: 50 files
    for i in range(50):
        size = 1024 + (i * 10)
        generate_seeded_file(src / f"file_1_{i}.bin", size, seed + i)
    run_command(["restic", "backup", str(src), "--compression", "off"], env=env)

    # Round 2: 40 files
    for i in range(40):
        size = 1024 + (i * 15)
        generate_seeded_file(src / f"file_2_{i}.bin", size, seed + 100 + i)
    run_command(["restic", "backup", str(src), "--compression", "off"], env=env)

    # Round 3: 30 files
    for i in range(30):
        size = 1024 + (i * 20)
        generate_seeded_file(src / f"file_3_{i}.bin", size, seed + 200 + i)
    run_command(["restic", "backup", str(src), "--compression", "off"], env=env)

    # Rounds 4-10: 20 files each
    for round_num in range(4, 11):
        for i in range(20):
            size = 1024 + (i * 5)
            generate_seeded_file(
                src / f"file_{round_num}_{i}.bin", size, seed + round_num * 100 + i
            )
        run_command(["restic", "backup", str(src), "--compression", "off"], env=env)

    # Run calculator without debug
    with patch("sys.argv", ["restic_subset_calculator", "7"]):
        with patch.dict("os.environ", env):
            main()

    captured = capsys.readouterr()
    output = captured.out

    # Basic verification of output format
    assert "Subset (n/t)" in output
    assert "Packs" in output
    assert "Size (MB)" in output

    # Extract numbers from the LAST output table
    lines = output.splitlines()
    subset_lines = []
    for line in reversed(lines):
        if re.match(r"^\s*\d+/7", line):
            subset_lines.append(line)
        if len(subset_lines) == 7:
            break

    assert len(subset_lines) == 7
    subset_lines.reverse()

    total_packs = 0
    total_size_mb = 0.0
    for line in subset_lines:
        parts = line.split()
        packs = int(parts[1])
        size_mb = float(parts[2])
        total_packs += packs
        total_size_mb += size_mb

    assert total_packs > 0
    assert total_size_mb > 0

    # Verified values for 10 rounds on this environment (restic 0.16.4)
    assert total_packs == 20
    # Values observed: 0.39, 0.40, 0.41... it depends on rounding and floating point
    assert 0.38 <= total_size_mb <= 0.42

    # Run calculator with debug to verify download size reporting
    with patch("sys.argv", ["restic_subset_calculator", "7", "--debug"]):
        with patch.dict("os.environ", env):
            main()

    captured_debug = capsys.readouterr()
    assert "Executing: restic list index --json" in captured_debug.err

    download_matches = re.findall(
        r"Total downloaded so far: ([\d\.]+) MB", captured_debug.err
    )
    assert len(download_matches) > 0
    assert float(download_matches[-1]) > 0
