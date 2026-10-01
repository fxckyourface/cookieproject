"""Создание разметки YOLO по координатам видимых кнопок игры."""
import json
import argparse
import shutil
from pathlib import Path
from PIL import Image, ImageDraw

ROOT = Path(__file__).resolve().parent
NAMES = ["game", "upgrade", "bonus", "close", "shop"]
VALIDATION = {"game_03", "game_10", "shop_04", "bonus_02", "bonus_05", "ad_03"}


def class_id(button):
    name, css = button["name"], button["cls"]
    if button["disabled"]:
        return None
    if name == "Испечь печенье":
        return 0
    if "building-price" in css:
        return 1
    if name == "Открыть сундук" or name.startswith("Собрать "):
        return 2
    if css in {"panel-header-close", "ad-close"}:
        return 3
    if name == "Магазин":
        return 4
    return None


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--source", default=".")
    args = parser.parse_args()
    source_root = ROOT / args.source
    samples = json.loads((source_root / "samples.json").read_text())
    samples = list({row["name"]: row for row in samples}.values())
    counts = [0] * len(NAMES)
    for index, row in enumerate(samples):
        name = row["name"]
        split = "val" if (name in VALIDATION if args.source == "." else index % 5 == 0) else "train"
        images = source_root / "dataset" / "images" / split
        labels = source_root / "dataset" / "labels" / split
        images.mkdir(parents=True, exist_ok=True)
        labels.mkdir(parents=True, exist_ok=True)
        source = source_root / "screenshots" / (name + ".png")
        shutil.copy2(source, images / source.name)
        picture = Image.open(source).convert("RGB")
        draw = ImageDraw.Draw(picture)
        lines = []
        for button in row["buttons"]:
            cls = class_id(button)
            # В этой сцене уже показывается награда, кнопка сундука исчезла.
            if name == "bonus_03" and cls == 2:
                continue
            if cls is None:
                continue
            b, offset = button["box"], row["offset"]
            x1 = max(0, b["x"] + offset["x"])
            y1 = max(0, b["y"] + offset["y"])
            x2 = min(1280, x1 + b["width"])
            y2 = min(720, y1 + b["height"])
            # Первые снимки были сохранены браузером с другим масштабом.
            # Их рамки сверены с изображениями и исправлены вручную.
            if picture.size == (1195, 672):
                corrected = {0: (312, 240, 590, 468),
                             2: (344, 414, 557, 457),
                             4: (215, 470, 328, 543)}
                if cls in corrected:
                    a, c, d, e = corrected[cls]
                    x1, y1, x2, y2 = a*1280/1195, c*720/672, d*1280/1195, e*720/672
            # В начале падения алмаз ещё за верхним краем игрового поля.
            if args.source == "." and "falling-object" in button["cls"]:
                continue
            # Ограничиваем рамку областью iframe: часть магазина бывает за экраном.
            if button["cls"] != "ad-close":
                x2 = min(x2, offset["x"] + offset["width"])
                y2 = min(y2, offset["y"] + offset["height"])
            if x2 <= x1 or y2 <= y1:
                continue
            values = ((x1+x2)/2560, (y1+y2)/1440, (x2-x1)/1280, (y2-y1)/720)
            lines.append(str(cls) + " " + " ".join(f"{v:.6f}" for v in values))
            counts[cls] += 1
            sx, sy = picture.width / 1280, picture.height / 720
            draw.rectangle((x1*sx, y1*sy, x2*sx, y2*sy), outline="lime", width=2)
            draw.text((x1*sx+3, y1*sy+3), NAMES[cls], fill="lime")
        (labels / (name + ".txt")).write_text("\n".join(lines) + "\n")
        shapes = []
        for line in lines:
            cls, cx, cy, w, h = map(float, line.split())
            shapes.append({"label": NAMES[int(cls)], "points": [
                [(cx-w/2)*picture.width, (cy-h/2)*picture.height],
                [(cx+w/2)*picture.width, (cy+h/2)*picture.height]],
                "group_id": None, "shape_type": "rectangle", "flags": {}})
        native = {"version":"2.5.0", "flags":{}, "shapes":shapes,
                  "imagePath":source.name, "imageData":None,
                  "imageHeight":picture.height, "imageWidth":picture.width}
        source.with_suffix(".json").write_text(json.dumps(native, ensure_ascii=False, indent=2))
        if name in {"game_03", "shop_04", "bonus_02", "bonus_05", "ad_03"}:
            output = ROOT / "examples"
            output.mkdir(exist_ok=True)
            picture.save(output / (name + ".jpg"))
    (source_root / "class.txt").write_text("\n".join(NAMES) + "\n")
    if args.source != ".":
        import yaml
        config = {"path":str(source_root / "dataset"), "train":"images/train", "val":"images/val", "names":dict(enumerate(NAMES))}
        (source_root / "data.yaml").write_text(yaml.safe_dump(config))
    print(f"Готово: {len(samples)} снимков.")
    print(dict(zip(NAMES, counts)))


if __name__ == "__main__":
    main()
