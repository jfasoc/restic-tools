#!/usr/bin/env python3
"""
CLI tool to calculate restic check data subset statistics.
"""

import argparse
import json
import os
import subprocess
import sys


def run_restic(args, debug=False):
    """Executes a restic command and returns the output and its size.

    Args:
        args (list): List of command-line arguments for restic.
        debug (bool): If True, prints the executed command and download size.

    Returns:
        tuple: A tuple containing the stdout bytes and the length of the stdout.
    """
    cmd = ["restic"] + args
    if debug:
        print(f"Executing: {' '.join(cmd)}", file=sys.stderr)
    try:
        # Use bytes to get accurate download size
        result = subprocess.run(cmd, capture_output=True, check=True, env=os.environ)
        if debug:
            size_mb = len(result.stdout) / 1_000_000
            print(f"Downloaded: {size_mb:.2f} MB", file=sys.stderr)
        return result.stdout, len(result.stdout)
    except subprocess.CalledProcessError as e:
        print(f"Error executing restic: {e.stderr.decode()}", file=sys.stderr)
        sys.exit(1)


def parse_json_output(output):
    """Parses restic JSON output which might be NDJSON or raw IDs.

    Args:
        output (str): The raw output string from restic.

    Returns:
        list|dict: Parsed JSON data, either as a list or a dictionary.
    """
    output = output.strip()
    if not output:
        return []

    try:
        return json.loads(output)
    except json.JSONDecodeError:
        results = []
        for line in output.splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                results.append(json.loads(line))
            except json.JSONDecodeError:
                # Fallback for non-JSON lines (raw IDs)
                results.append(line)
        return results


def print_table(t, subset_stats, current_index, total_indices):
    """Prints a formatted table of subset statistics.

    Args:
        t (int): Total number of subsets.
        subset_stats (dict): Dictionary containing pack counts and sizes per subset.
        current_index (int): The current index being processed.
        total_indices (int): The total number of indices to process.
    """
    print(f"\nIndex {current_index}/{total_indices}")
    header = f"{'Subset (n/t)':<15} {'Packs':<15} {'Size (MB)':<15}"
    print(header)
    print("-" * len(header))
    t_str = str(t)
    t_width = len(t_str)
    for n in range(1, t + 1):
        packs = subset_stats[n]["packs"]
        size_mb = subset_stats[n]["size_bytes"] / 1_000_000
        n_str = str(n).rjust(t_width)
        n_t = f"{n_str}/{t_str}"
        print(f"{n_t:<15} {packs:>15} {size_mb:>15.2f}")


def get_parser():
    """Creates the argument parser for the CLI.

    Returns:
        argparse.ArgumentParser: The configured argument parser.
    """
    parser = argparse.ArgumentParser(
        description="Calculate restic check --read-data-subset stats."
    )
    parser.add_argument("t", type=int, help="Total number of subsets (1-256)")
    parser.add_argument(
        "--debug", action="store_true", help="Print restic commands executed"
    )
    return parser


def run(args):
    """Orchestrates the subset calculation process.

    Args:
        args (argparse.Namespace): The parsed command-line arguments.
    """
    if not (1 <= args.t <= 256):
        print("Error: t must be between 1 and 256.", file=sys.stderr)
        sys.exit(1)

    # Get index IDs
    total_downloaded = 0
    index_list_raw, dl_size = run_restic(["list", "index", "--json"], debug=args.debug)
    total_downloaded += dl_size
    index_ids = parse_json_output(index_list_raw.decode())
    total_indices = len(index_ids)

    seen_packs = {}  # pack_id -> size
    subset_stats = {n: {"packs": 0, "size_bytes": 0} for n in range(1, args.t + 1)}

    for i, index_id in enumerate(index_ids, 1):
        index_content_raw, dl_size = run_restic(
            ["cat", "index", index_id], debug=args.debug
        )
        total_downloaded += dl_size
        index_data = parse_json_output(index_content_raw.decode())

        # restic cat index returns a list of objects, one of which has "packs"
        # actually, usually it's a single object with "packs"
        if isinstance(index_data, dict):
            packs_list = index_data.get("packs", [])
        else:
            # Handle list of objects if necessary (sometimes restic output varies)
            packs_list = []
            for item in index_data:
                packs_list.extend(item.get("packs", []))

        for pack in packs_list:
            pack_id = pack["id"]
            if pack_id not in seen_packs:
                # Calculate pack size: max(offset + length)
                max_end = 0
                for blob in pack.get("blobs", []):
                    end = blob["offset"] + blob["length"]
                    if end > max_end:
                        max_end = end

                seen_packs[pack_id] = max_end

                # Determine subset
                first_byte = int(pack_id[:2], 16)
                subset_n = (first_byte % args.t) + 1

                subset_stats[subset_n]["packs"] += 1
                subset_stats[subset_n]["size_bytes"] += max_end

        print_table(args.t, subset_stats, i, total_indices)
        if args.debug:
            print(
                f"Total downloaded so far: {total_downloaded / 1_000_000:.2f} MB",
                file=sys.stderr,
            )


def main():
    """Main entry point for the CLI."""
    run(get_parser().parse_args())


if __name__ == "__main__":
    main()
