import json
import runpy
import subprocess
from unittest.mock import MagicMock, patch

import pytest

import restic_subset_calculator


def test_run_restic_success(mocker):
    mock_run = mocker.patch("subprocess.run")
    mock_run.return_value = MagicMock(stdout=b"output", returncode=0)

    result, size = restic_subset_calculator.run_restic(["list", "index"])

    assert result == b"output"
    assert size == len(b"output")
    mock_run.assert_called_once()


def test_run_restic_debug(mocker, capsys):
    mock_run = mocker.patch("subprocess.run")
    mock_run.return_value = MagicMock(stdout=b"output", returncode=0)

    restic_subset_calculator.run_restic(["list", "index"], debug=True)

    captured = capsys.readouterr()
    assert "Executing: restic list index" in captured.err
    assert "Downloaded: 0.00 MB" in captured.err


def test_run_restic_failure(mocker):
    mock_run = mocker.patch("subprocess.run")
    mock_run.side_effect = subprocess.CalledProcessError(
        returncode=1, cmd="restic", stderr="some error"
    )

    with pytest.raises(SystemExit) as e:
        restic_subset_calculator.run_restic(["list", "index"])

    assert e.value.code == 1


def test_main_invalid_t(mocker):
    mocker.patch("sys.argv", ["restic_subset_calculator.py", "0"])
    with pytest.raises(SystemExit) as e:
        restic_subset_calculator.main()
    assert e.value.code == 1

    mocker.patch("sys.argv", ["restic_subset_calculator.py", "257"])
    with pytest.raises(SystemExit) as e:
        restic_subset_calculator.main()
    assert e.value.code == 1


def test_main_success(mocker, capsys):
    # Mock index list using NDJSON-like format (multiple lines of IDs)
    index_output = b"index1\nindex2"
    mocker.patch(
        "restic_subset_calculator.run_restic",
        side_effect=[
            (index_output, len(index_output)),  # for list index
            (
                json.dumps(
                    {  # for index1
                        "packs": [
                            {
                                "id": "00aabb",  # byte 00 -> 0 % 2 = 0 -> subset 1
                                "blobs": [{"offset": 0, "length": 1000000}],
                            }
                        ]
                    }
                ).encode(),
                100,
            ),
            (
                json.dumps(
                    {  # for index2
                        "packs": [
                            {
                                "id": "01ccdd",  # byte 01 -> 1 % 2 = 1 -> subset 2
                                "blobs": [{"offset": 0, "length": 2000000}],
                            }
                        ]
                    }
                ).encode(),
                100,
            ),
        ],
    )

    mocker.patch("sys.argv", ["restic_subset_calculator.py", "2"])

    restic_subset_calculator.main()

    captured = capsys.readouterr()
    assert "Index 1/2" in captured.out
    assert "1/2             1                          1.00" in captured.out
    assert "Index 2/2" in captured.out
    assert "2/2             1                          2.00" in captured.out


def test_main_complex_index_and_duplicate_packs(mocker, capsys):
    # Restic index can be a list of dicts
    index1_content = [
        {
            "packs": [
                {
                    "id": "ff0011",  # byte ff (255) % 1 = 0 -> subset 1
                    "blobs": [
                        {"offset": 0, "length": 500000},
                        {"offset": 500000, "length": 500000},
                    ],
                }
            ]
        },
        {
            "packs": [
                {
                    "id": "ff0011",  # Duplicate pack
                    "blobs": [{"offset": 0, "length": 1000000}],
                },
                {
                    "id": "001122",  # byte 00 % 1 = 0 -> subset 1
                    "blobs": [{"offset": 100, "length": 900}],
                },
            ]
        },
    ]

    mocker.patch(
        "restic_subset_calculator.run_restic",
        side_effect=[
            (json.dumps(["index1"]).encode(), 10),
            (json.dumps(index1_content).encode(), 100),
        ],
    )

    mocker.patch("sys.argv", ["restic_subset_calculator.py", "1"])

    restic_subset_calculator.main()

    captured = capsys.readouterr()
    # 2 unique packs. ff... has size 1000000. 00... has size 1000.
    # Total size = 1001000 bytes = 1.00 MB (decimal)
    assert "1/1             2                          1.00" in captured.out


def test_main_alignment(mocker, capsys):
    # Mock index list for t=10 to test alignment
    mocker.patch(
        "restic_subset_calculator.run_restic",
        side_effect=[
            (b"idx1", 4),
            (
                json.dumps(
                    {"packs": [{"id": "00", "blobs": [{"offset": 0, "length": 0}]}]}
                ).encode(),
                10,
            ),
        ],
    )
    mocker.patch("sys.argv", ["restic_subset_calculator.py", "10"])
    restic_subset_calculator.main()
    captured = capsys.readouterr()
    # n=1 for t=10 should be " 1/10"
    assert " 1/10           1                          0.00" in captured.out


def test_main_debug_flag(mocker, capsys):
    mocker.patch(
        "restic_subset_calculator.run_restic",
        side_effect=[
            (json.dumps(["idx"]).encode(), 10),
            (json.dumps({"packs": []}).encode(), 10),
        ],
    )
    mocker.patch("sys.argv", ["restic_subset_calculator.py", "1", "--debug"])

    # We need to make sure run_restic is called with debug=True
    # The first call to run_restic in main is list index
    # The second is cat index

    with patch(
        "restic_subset_calculator.run_restic", wraps=restic_subset_calculator.run_restic
    ) as mock_run:
        restic_subset_calculator.main()
        assert mock_run.call_args_list[0][1]["debug"] is True
        assert mock_run.call_args_list[1][1]["debug"] is True

    captured = capsys.readouterr()
    assert "Total downloaded so far: 0.00 MB" in captured.err


def test_entry_point(mocker):
    mocker.patch("sys.argv", ["restic_subset_calculator.py", "1"])
    # We must patch subprocess.run instead of run_restic because runpy executes
    # the module, and we want to avoid actual subprocess calls during module
    # execution if it hits the main()
    mock_run = mocker.patch("subprocess.run")
    mock_run.side_effect = [
        MagicMock(stdout=b"idx", returncode=0),
        MagicMock(stdout=json.dumps({"packs": []}).encode(), returncode=0),
    ]

    # We don't patch main() here because we want to see it executed and covered.
    # Instead we verify that the module execution doesn't fail.
    runpy.run_path("restic_subset_calculator.py", run_name="__main__")


def test_parse_json_output_empty():
    assert restic_subset_calculator.parse_json_output("") == []


def test_parse_json_output_ndjson():
    ndjson = '{"a":1}\n{"b":2}'
    assert restic_subset_calculator.parse_json_output(ndjson) == [{"a": 1}, {"b": 2}]


def test_parse_json_output_mixed_with_empty_lines():
    ndjson = '{"a":1}\n\n  \n{"b":2}'
    assert restic_subset_calculator.parse_json_output(ndjson) == [{"a": 1}, {"b": 2}]
