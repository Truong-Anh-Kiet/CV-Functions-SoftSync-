import os
from pathlib import Path
from urllib.request import Request, urlopen

AI_ROOT = Path(__file__).resolve().parent

MODEL_URL = os.environ.get("ONNX_MODEL_URL")
MODEL_PATH = (
    AI_ROOT
    / "checkpoints"
    / "mbert_onnx_int8"
    / "model_int8.onnx"
)

MIN_SIZE = 300 * 1024 * 1024


def main():
    if not MODEL_URL:
        raise RuntimeError("Missing ONNX_MODEL_URL")

    MODEL_PATH.parent.mkdir(parents=True, exist_ok=True)

    if MODEL_PATH.exists() and MODEL_PATH.stat().st_size >= MIN_SIZE:
        print(f"ONNX model already exists: {MODEL_PATH}")
        return

    temp_path = MODEL_PATH.with_suffix(".onnx.part")
    request = Request(
        MODEL_URL,
        headers={"User-Agent": "cv-functions-ai"},
    )

    print("Downloading ONNX INT8 model...")

    try:
        with urlopen(request, timeout=120) as response:
            with temp_path.open("wb") as output:
                while True:
                    chunk = response.read(8 * 1024 * 1024)
                    if not chunk:
                        break
                    output.write(chunk)

        size = temp_path.stat().st_size

        if size < MIN_SIZE:
            raise RuntimeError(
                f"Downloaded file is too small: {size} bytes"
            )

        temp_path.replace(MODEL_PATH)

        print(f"Model downloaded: {size / (1024 * 1024):.2f} MiB")
        print(f"Saved to: {MODEL_PATH}")

    except Exception:
        temp_path.unlink(missing_ok=True)
        raise


if __name__ == "__main__":
    main()