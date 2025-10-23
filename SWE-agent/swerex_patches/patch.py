import importlib.util
import os
import shutil
import subprocess
import sys
from pathlib import Path
import argparse # Import argparse for command-line argument parsing


def find_swerex_installation():
    """Find the SWE-Rex installation directory."""
    # Try to import swerex to find its location
    try:
        spec = importlib.util.find_spec("swerex")
        if spec and spec.origin:
            # Return the parent directory of the module, not the module itself
            return Path(spec.origin).parent.parent
    except ImportError:
        pass

    # Try to find it using pip
    try:
        result = subprocess.run(
            [sys.executable, "-m", "pip", "show", "swe_rex"],
            capture_output=True,
            text=True,
            check=True,
        )
        for line in result.stdout.splitlines():
            if line.startswith("Location:"):
                # Return the site-packages directory, not appending swerex again
                return Path(line.split(":", 1)[1].strip())
    except subprocess.CalledProcessError:
        pass

    return None


# Modified apply_patches to accept a force_all argument
def apply_patches(swerex_dir, patches_dir, force_all=False):
    """Apply patches from patches_dir to swerex_dir, with confirmation for each file."""
    patches_dir = Path(patches_dir)
    swerex_dir = Path(swerex_dir)

    if not swerex_dir.exists():
        print(f"Error: SWE-Rex directory not found at {swerex_dir}")
        return False

    if not patches_dir.exists():
        print(f"Error: Patches directory not found at {patches_dir}")
        return False

    # Walk through the patches directory and copy files to the corresponding locations
    patched_files = []
    skipped_files = []

    # If force_all is True, we don't need the 'apply_all' internal flag for prompts
    internal_apply_all = force_all

    for root, _, files in os.walk(patches_dir):
        rel_path = Path(root).relative_to(patches_dir)
        target_dir = swerex_dir / rel_path

        # Create target directory if it doesn't exist
        target_dir.mkdir(parents=True, exist_ok=True)

        for file in files:
            if file == "patch.py" or file == "README.md":
                continue  # Skip the patch script itself and README

            source_file = Path(root) / file
            target_file = target_dir / file

            # Only prompt if not in force_all mode
            if not internal_apply_all:
                # Prompt for confirmation for this specific file
                print(f"\nPatch file: {source_file.relative_to(patches_dir)}")
                print(f"Target: {target_file}")

                if target_file.exists():
                    print("Note: Target file already exists and will be backed up.")

                response = input("Apply this patch? [y/N/a(ll)/q(uit)] ").lower()

                if response == "q":
                    print("Patching process aborted.")
                    return len(patched_files) > 0

                if response == "a":
                    internal_apply_all = True # Set internal_apply_all if 'a' is chosen

            # Apply the patch if force_all, or if user said yes/all in interactive mode
            if internal_apply_all or response in ["y", "yes"]:
                # Backup the original file if it exists
                if target_file.exists():
                    backup_file = target_file.with_suffix(target_file.suffix + ".bak")
                    shutil.copy2(target_file, backup_file)
                    print(f"Backed up {target_file} to {backup_file}")

                # Copy the patch file
                shutil.copy2(source_file, target_file)
                patched_files.append(str(target_file))
                print(f"Patched {source_file} -> {target_file} ")
            else:
                skipped_files.append(str(target_file))
                print(f"Skipped {target_file}")

    if patched_files:
        print(f"\nSuccessfully patched {len(patched_files)} files in SWE-Rex installation.")
        if skipped_files:
            print(f"Skipped {len(skipped_files)} files.")
        return True
    else:
        print("No files were patched.")
        return False


def main():
    parser = argparse.ArgumentParser(description="Patch SWE-Rex installation.")
    parser.add_argument(
        "--yes", "-y", action="store_true",
        help="Answer yes to all prompts without asking for confirmation."
    )
    args = parser.parse_args()

    # Get the directory containing this script
    script_dir = Path(__file__).parent.absolute()

    # Find SWE-Rex installation
    swerex_dir = find_swerex_installation()

    if not swerex_dir:
        print("Error: Could not find SWE-Rex installation.")
        print("Please make sure SWE-Rex is installed and try again.")
        sys.exit(1)

    print(f"Found SWE-Rex installation at: {swerex_dir}")

    # Confirm before patching, unless --yes flag is used
    if not args.yes:
        response = input(f"Do you want to patch SWE-Rex at {swerex_dir}? [y/N] ")
        if response.lower() not in ["y", "yes"]:
            print("Patching cancelled.")
            sys.exit(0)

    # Apply patches, passing the force_all status from the --yes flag
    success = apply_patches(swerex_dir, script_dir, force_all=args.yes)

    if success:
        print("\nPatching completed successfully!")
    else:
        print("\nPatching failed or was cancelled.")
        sys.exit(1)


if __name__ == "__main__":
    main()