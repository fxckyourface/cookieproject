"""Дополнительные учебные сцены: спрайты бонусов на настоящих снимках.

Это синтетическое расширение выборки, а не новые снимки настоящей игры.
Спрайты сохранены из ресурсов игры во время предыдущего разрешённого запуска.
"""
import json
import random
import shutil
from pathlib import Path
from PIL import Image
import yaml

ROOT = Path(__file__).resolve().parent


def main():
    random.seed(42)
    output = ROOT / "bonus_dataset"
    manifest = []
    sprites = {name:Image.open(ROOT / "training_assets" / (name+".png")).convert("RGBA")
               for name in ["cookie", "gem"]}
    for split in ["train", "val"]:
        images = output / "images" / split
        labels = output / "labels" / split
        images.mkdir(parents=True, exist_ok=True)
        labels.mkdir(parents=True, exist_ok=True)
        for original in sorted((ROOT / "dataset" / "images" / split).glob("*.png")):
            label = ROOT / "dataset" / "labels" / split / (original.stem+".txt")
            shutil.copy2(original, images / original.name)
            shutil.copy2(label, labels / label.name)
            lines = label.read_text().strip().splitlines()
            if not any(line.startswith("0 ") for line in lines):
                continue
            for version in range(3):
                picture = Image.open(original).convert("RGBA")
                new_labels = list(lines)
                added = []
                # Бонусы размещаются по сторонам печенья, как в реальной игре.
                # Train и val используют разные исходные фоны.
                for side, name in enumerate(["cookie", "gem"]):
                    size = random.randint(50, 94)
                    sprite = sprites[name].resize((size,size), Image.Resampling.LANCZOS)
                    bounds = sprite.getbbox()
                    x = random.randint(35,215) if side == 0 else random.randint(670,795)
                    y = random.randint(225,430)
                    if picture.width != 1280:
                        x = round(x*picture.width/1280)
                        y = round(y*picture.height/720)
                    picture.alpha_composite(sprite, (x,y))
                    left,top,right,bottom = bounds
                    x1,y1,x2,y2 = x+left,y+top,x+right,y+bottom
                    cx,cy=(x1+x2)/2/picture.width,(y1+y2)/2/picture.height
                    w,h=(x2-x1)/picture.width,(y2-y1)/picture.height
                    new_labels.append(f"2 {cx:.6f} {cy:.6f} {w:.6f} {h:.6f}")
                    added.append({"sprite":name,"box":[x1,y1,x2,y2]})
                stem=f"aug_{original.stem}_{version}"
                picture.convert("RGB").save(images / (stem+".png"))
                (labels / (stem+".txt")).write_text("\n".join(new_labels)+"\n")
                manifest.append({"image":stem+".png","split":split,
                                 "background":original.name,"synthetic":True,"bonuses":added})
    config={"path":"bonus_dataset", "train":"images/train", "val":"images/val",
            "names":{0:"game",1:"upgrade",2:"bonus",3:"close",4:"shop"}}
    (ROOT / "bonus_data.yaml").write_text(yaml.safe_dump(config))
    (output / "manifest.json").write_text(json.dumps(manifest,ensure_ascii=False,indent=2))
    print("Добавлены синтетические сцены бонусов:",len(manifest))


if __name__ == "__main__":
    main()
