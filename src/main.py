# main.py

import polars as pl
import subprocess
import sys


def main():
    """Reads council data and launches a separate process for each one."""
    try:
        councils_df = pl.read_csv("data/postcodes_by_council.csv")
    except Exception as e:
        print(f"Error reading CSV file: {e}")
        return

    councils = councils_df.to_dicts()
    print(f"Found {len(councils)} councils to process.")

    for council in councils:
        # Ensure all required fields are present
        if council.get("postcode"):
            council_name = council.get("Authority Name")
            print(f"\n--- Starting process for: {council_name} ---")

            # Command to execute the worker script
            command = [
                sys.executable,  # Use the same python interpreter
                "src/run_single_council.py",
                "--council-name",
                council_name,
                "--url",
                council.get("URL"),
                "--postcode",
                council.get("postcode"),
            ]

            # Run the command in a separate process
            # `capture_output=True` and `text=True` help see the worker's output
            result = subprocess.run(
                command, capture_output=True, text=True, check=False
            )

            # Print the output from the subprocess
            print(result.stdout)
            if result.stderr:
                print("--- Errors ---")
                print(result.stderr)
        else:
            print(f"Skipping a row due to missing data: {council}")

    print("\nAll councils processed.")


if __name__ == "__main__":
    main()
