"""
ARC Prize 2026 -- QOR-Lang Agent Submission
"""
import subprocess
import os
import shutil
import stat
import glob
import zipfile
import pandas as pd

# -- 0. Create submission.parquet FIRST (so Kaggle always has it) --
submission = pd.DataFrame(
    data=[['1_0', '1', True, 1]],
    columns=['row_id', 'game_id', 'end_of_game', 'score'])
submission.to_parquet('/kaggle/working/submission.parquet', index=False)
print("submission.parquet created (placeholder)")

is_competition = bool(os.getenv('KAGGLE_IS_COMPETITION_RERUN'))
print(f"Competition rerun: {is_competition}")

# -- 1. Find the dataset --
print("Searching for agent files...")
INPUT = "/kaggle/input"
WORK_DIR = "/kaggle/working/arc3"
binary_src = None
dna_zip = None

for root, dirs, files in os.walk(INPUT):
    for f in files:
        full = os.path.join(root, f)
        if f == "arc3":
            binary_src = full
            print(f"  Found binary: {full}")
        if f == "dna.zip":
            dna_zip = full
            print(f"  Found DNA zip: {full}")

if not binary_src:
    print(f"\nContents of {INPUT}:")
    for root, dirs, files in os.walk(INPUT):
        for f in files:
            print(f"  {os.path.join(root, f)}")
    print("ERROR: arc3 binary not found in dataset!")
else:
    try:
        # -- 2. Copy to working dir --
        print(f"\nSetting up working directory: {WORK_DIR}")
        if os.path.exists(WORK_DIR):
            shutil.rmtree(WORK_DIR)
        os.makedirs(os.path.join(WORK_DIR, "dna", "puzzle_solver"), exist_ok=True)

        shutil.copy2(binary_src, os.path.join(WORK_DIR, "arc3"))
        os.chmod(os.path.join(WORK_DIR, "arc3"), 0o755)
        print(f"  Binary: {os.path.getsize(os.path.join(WORK_DIR, 'arc3')) / 1024 / 1024:.1f}MB")

        # Extract DNA zip (contains all .qor files + game_rules.json + library/)
        dna_dest = os.path.join(WORK_DIR, "dna", "puzzle_solver")
        if dna_zip:
            print(f"  Extracting {dna_zip}...")
            with zipfile.ZipFile(dna_zip, 'r') as z:
                z.extractall(WORK_DIR)
            # Move files if they ended up in wrong location
            for root, dirs, files in os.walk(WORK_DIR):
                for f in files:
                    if f.endswith(('.qor', '.json')) and root != dna_dest and 'puzzle_solver' not in root:
                        target = os.path.join(dna_dest, f)
                        if not os.path.exists(target):
                            shutil.move(os.path.join(root, f), target)
                            print(f"  Moved {f} to {dna_dest}")
        else:
            # Copy DNA files directly from input
            for root, dirs, files in os.walk(INPUT):
                for f in files:
                    if f.endswith(('.qor', '.json')) and f != 'dataset-metadata.json':
                        shutil.copy2(os.path.join(root, f), os.path.join(dna_dest, f))
                        print(f"  Copied {f}")

        # Show what DNA we have
        print("\n  DNA files loaded:")
        for f in sorted(os.listdir(dna_dest)):
            fp = os.path.join(dna_dest, f)
            if os.path.isfile(fp):
                print(f"    {f} ({os.path.getsize(fp):,} bytes)")
            elif os.path.isdir(fp):
                print(f"    {f}/ (dir)")

        # -- 3. Detect API endpoint --
        if is_competition:
            # Wait for gateway to be ready (can take minutes)
            print("\n  Waiting for gateway...")
            subprocess.run(
                ["curl", "--fail", "--retry", "999", "--retry-all-errors",
                 "--retry-delay", "5", "--retry-max-time", "600",
                 "http://gateway:8001/api/games"],
                capture_output=True, timeout=660
            )
            api_base = "http://gateway:8001/api"
            api_key = "competition"
            print(f"  Gateway ready: {api_base}")
        else:
            api_base = "https://three.arcprize.org/api"
            api_key = os.environ.get("ARC_API_KEY", "")
            if not api_key:
                try:
                    from kaggle_secrets import UserSecretsClient
                    api_key = UserSecretsClient().get_secret("ARC_API_KEY")
                except Exception:
                    pass
            if not api_key:
                api_key = "REDACTED_CREDENTIAL"
            print(f"  Public API: {api_base}")

        # Clear stale scorecard so agent creates fresh one
        stale_sc = os.path.join(dna_dest, "active_scorecard.txt")
        if os.path.exists(stale_sc):
            os.remove(stale_sc)

        # -- 4. Run agent --
        print(f"\n{'='*60}")
        print(f"QOR ARC-AGI-3 Agent | API: {api_base}")
        print(f"{'='*60}\n")

        result = subprocess.run(
            [os.path.join(WORK_DIR, "arc3"), "--api-key", api_key],
            cwd=WORK_DIR,
            env={**os.environ, "QOR_DNA_DIR": dna_dest, "ARC_API_BASE": api_base},
            timeout=7200,
        )
        print(f"\nAgent exit code: {result.returncode}")

        # -- 5. Show results --
        scorecard_file = os.path.join(dna_dest, "active_scorecard.txt")
        if os.path.exists(scorecard_file):
            card_id = open(scorecard_file).read().strip()
            print(f"Scorecard: {card_id}")

    except Exception as e:
        print(f"Agent error: {e}")

print("Done.")
