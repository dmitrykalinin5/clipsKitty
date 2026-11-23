"""Run using the Python already bundled with Clips Kitty."""
import argparse
import sys
from pathlib import Path

parser = argparse.ArgumentParser(description="Download local Whisper speech recognition models")
parser.add_argument("--model", choices=["small", "large-v3-turbo", "both"], default="both")
parser.add_argument("--check", action="store_true")
args = parser.parse_args()
root = Path(__file__).resolve().parent / "resources" / "backend" / "_internal" / "whisper"
sizes = ["small", "large-v3-turbo"] if args.model == "both" else [args.model]
def ready(target):
    return all((target/name).is_file() for name in ("model.bin", "config.json", "tokenizer.json"))
if args.check:
    for size in sizes:
        print(size + ": " + ("installed" if ready(root/size) else "not downloaded"))
    # Check the real downloader imports, without making a network request.
    from faster_whisper.utils import download_model
    print("Bundled model downloader: ready")
    sys.exit(0)
from faster_whisper.utils import download_model
for size in sizes:
    target = root / size
    if ready(target):
        print("Already installed:", size, flush=True)
        continue
    print("Downloading Whisper", size, "(please keep this window open)", flush=True)
    target.mkdir(parents=True, exist_ok=True)
    download_model(size, output_dir=str(target))
    if not ready(target):
        raise RuntimeError("Model download incomplete: " + size)
    print("Installed:", size, flush=True)
print("Done. Clips Kitty can now use the downloaded speech models offline.", flush=True)
