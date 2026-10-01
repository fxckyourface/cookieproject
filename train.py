"""Обучение небольшой модели YOLO на снимках кликера."""
import argparse
import os
import shutil
from pathlib import Path

ROOT = Path(__file__).resolve().parent
os.environ.setdefault("YOLO_CONFIG_DIR", str(ROOT / ".yolo"))
os.environ.setdefault("MPLCONFIGDIR", str(ROOT / ".matplotlib"))


def main():
    import torch
    import yaml
    from ultralytics import YOLO

    parser = argparse.ArgumentParser()
    parser.add_argument("--epochs", type=int, default=80)
    parser.add_argument("--data", default="data.yaml")
    parser.add_argument("--model", default="yolov8n.pt")
    parser.add_argument("--name", default="cookie")
    parser.add_argument("--device", default="mps" if torch.backends.mps.is_available() else "cpu")
    args = parser.parse_args()
    config = yaml.safe_load((ROOT / args.data).read_text())
    if not Path(config["path"]).is_absolute():
        config["path"] = str(ROOT / config["path"])
    runtime = ROOT / ".data-local.yaml"
    runtime.write_text(yaml.safe_dump(config, allow_unicode=True))
    torch.set_num_threads(4)
    os.chdir(ROOT)
    model = YOLO(args.model)
    model.train(data=str(runtime), epochs=args.epochs, imgsz=640, batch=8,
                device=args.device, workers=0, project=str(ROOT / "runs"),
                name=args.name, exist_ok=True, patience=25, seed=42,
                fliplr=0, mosaic=0, degrees=0, translate=0.05, scale=0.1,
                hsv_h=0.01, hsv_s=0.15, hsv_v=0.15)
    best = ROOT / "runs" / args.name / "weights" / "best.pt"
    shutil.copy2(best, ROOT / "best.pt")
    print("Модель сохранена в best.pt")


if __name__ == "__main__":
    main()
