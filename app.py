"""Игра в кликер: снимок -> YOLO -> проверка цели -> нажатие."""
import argparse
import io
import json
import os
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent
URL = "https://yandex.ru/games/app/cookie-clicker-192443"
os.environ.setdefault("YOLO_CONFIG_DIR", str(ROOT / ".yolo"))
os.environ.setdefault("MPLCONFIGDIR", str(ROOT / ".matplotlib"))


def detect(model, image):
    result = model.predict(image, imgsz=640, conf=0.30, device="cpu", verbose=False)[0]
    objects = []
    for box in result.boxes:
        x1, y1, x2, y2 = box.xyxy[0].tolist()
        objects.append({"name": result.names[int(box.cls[0])],
                        "score": round(float(box.conf[0]), 3),
                        "x": (x1+x2)/2, "y": (y1+y2)/2})
    return result, objects


def target_at(page, frame, x, y):
    """Проверяем, что найденная моделью точка действительно на нужной кнопке."""
    iframe = page.locator("#game-frame").bounding_box()
    if iframe and iframe["x"] <= x < iframe["x"]+iframe["width"] and iframe["y"] <= y < iframe["y"]+iframe["height"]:
        if not page.evaluate("p => document.elementFromPoint(p.x,p.y)?.id === 'game-frame'", {"x":x,"y":y}):
            return None
        return frame.evaluate("""p => {
            const hit = document.elementFromPoint(p.x, p.y);
            const b = hit && hit.closest('button');
            return b ? {name:b.getAttribute('aria-label') || b.textContent,
                        css:b.className, disabled:b.disabled, inside:true} : null;
        }""", {"x": x-iframe["x"], "y": y-iframe["y"]})
    return page.evaluate("""p => {
        const hit = document.elementFromPoint(p.x, p.y);
        const b = hit && hit.closest('button');
        return b ? {name:b.getAttribute('aria-label') || b.textContent,
                    css:b.className, disabled:b.disabled, inside:false} : null;
    }""", {"x": x, "y": y})


def permitted(kind, target):
    if not target or target["disabled"]:
        return False
    name, css = target["name"], target["css"]
    if kind == "game":
        return target["inside"] and name == "Испечь печенье"
    if kind == "shop":
        return target["inside"] and name == "Магазин"
    if kind == "upgrade":
        return target["inside"] and "building-price" in css
    if kind == "bonus":
        return target["inside"] and (name == "Открыть сундук" or name.startswith("Собрать "))
    if kind == "close":
        return (target["inside"] and "panel-header-close" in css) or (not target["inside"] and "adv-fullscreen" in css)
    return False


def choose(objects, in_shop, shop_due, should_close):
    priority = ["bonus", "upgrade", "close"] if in_shop else ["close", "bonus", "shop", "game"]
    for kind in priority:
        if kind == "shop" and not shop_due:
            continue
        if kind == "close" and in_shop and not should_close:
            continue
        if kind == "upgrade" and should_close:
            continue
        candidates = [item for item in objects if item["name"] == kind]
        candidates.sort(key=lambda item: item["score"], reverse=True)
        for item in candidates:
            yield item


def pause_bonuses(frame, paused):
    """Останавливаем CSS-анимацию бонуса на время снимка и выбора цели."""
    frame.evaluate("""paused => {
        if (paused) {
            window.pausedCookieBonuses=window.pausedCookieBonuses || [];
            for (const el of document.querySelectorAll('.falling-object')) {
                for (const a of el.getAnimations()) {
                    if (a.playState === 'running') {
                        a.pause(); window.pausedCookieBonuses.push(a);
                    }
                }
            }
        } else {
            for (const a of window.pausedCookieBonuses || []) a.play();
            window.pausedCookieBonuses=[];
        }
    }""", paused)


def check(model):
    from PIL import Image
    output = ROOT / "verification"
    output.mkdir(exist_ok=True)
    summary = []
    for path in sorted((ROOT / "dataset" / "images" / "val").glob("*.png")):
        result, objects = detect(model, Image.open(path).convert("RGB"))
        result.save(str(output / (path.stem + ".jpg")))
        summary.append({"image": path.name, "objects": objects})
        print(path.name, ", ".join(item["name"] for item in objects))
    (output / "predictions.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2))


def play(model, args):
    import cv2
    from PIL import Image
    from playwright.sync_api import sync_playwright, Error

    output = ROOT / "session"
    output.mkdir(exist_ok=True)
    actions = []
    with sync_playwright() as p:
        context = p.chromium.launch_persistent_context(
            str(ROOT / ".browser-profile"), headless=False,
            viewport={"width": 1280, "height": 720}, device_scale_factor=1)
        page = context.pages[0] if context.pages else context.new_page()
        page.goto(URL, wait_until="domcontentloaded", timeout=60000)
        page.locator("#game-frame").wait_for(timeout=60000)
        frame = page.locator("#game-frame").element_handle().content_frame()
        print("Игра открыта. Если появится кнопка «Играть», нажми её.")
        print("Нажми Enter здесь, когда увидишь игру или рекламный ролик.")
        input()
        print("Запущено. Остановка: Q в окне распознавания или Ctrl+C здесь.")
        last_shop = time.monotonic()
        shop_opened = None
        purchases = 0
        started = time.monotonic()
        last_saved = 0
        paused = False
        try:
            while not page.is_closed():
                if args.seconds and time.monotonic()-started >= args.seconds:
                    break
                handle = page.locator("#game-frame").element_handle()
                if not handle or not handle.content_frame():
                    time.sleep(0.3)
                    continue
                frame = handle.content_frame()
                pause_bonuses(frame, True)
                image = Image.open(io.BytesIO(page.screenshot())).convert("RGB")
                result, objects = detect(model, image)
                display = cv2.resize(result.plot(), (960, 540))
                cv2.putText(display, "SPACE: pause  Q: stop", (12, 530), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0,255,0), 2)
                cv2.imshow("Cookie AI", display)
                key = cv2.waitKey(1) & 0xff
                if key in (ord("q"), ord("Q")):
                    break
                if key == 32:
                    paused = not paused
                    print("Пауза" if paused else "Продолжение")
                if paused:
                    time.sleep(0.1)
                    continue
                now = time.monotonic()
                in_shop = frame.locator(".panel-header-close").is_visible()
                if in_shop and shop_opened is None:
                    shop_opened = now
                    purchases = 0
                should_close = in_shop and (purchases >= 2 or now-shop_opened > 12)
                acted = False
                for item in choose(objects, in_shop, now-last_shop > 12, should_close):
                    if acted:
                        break
                    target = target_at(page, frame, item["x"], item["y"])
                    if not permitted(item["name"], target):
                        continue
                    page.mouse.click(item["x"], item["y"])
                    kind = item["name"]
                    if kind == "shop":
                        shop_opened, purchases = now, 0
                        # Над покупками находится предложение просмотра рекламы.
                        # Прокручиваем магазин до первой обычной покупки.
                        purchase = frame.locator(".building-price").first
                        if purchase.count():
                            purchase.scroll_into_view_if_needed(timeout=2000)
                    elif kind == "upgrade":
                        purchases += 1
                    elif kind == "close" and target["inside"]:
                        last_shop, shop_opened = now, None
                    actions.append({"time": round(now-started, 2), "kind": kind,
                                    "score": item["score"], "target": target["name"]})
                    if kind == "game":
                        for _ in range(4):
                            time.sleep(0.08)
                            if not permitted("game", target_at(page, frame, item["x"], item["y"])):
                                break
                            page.mouse.click(item["x"], item["y"])
                            actions.append({"time":round(time.monotonic()-started,2),
                                            "kind":"game", "score":item["score"],
                                            "target":"Испечь печенье"})
                    if kind != "game":
                        print(f"{kind}: {target['name']} ({item['score']:.0%})")
                    acted = True
                    break
                if now-last_saved >= 5:
                    result.save(str(output / "last_detection.jpg"))
                    (output / "actions.json").write_text(json.dumps(actions, ensure_ascii=False, indent=2))
                    last_saved = now
                pause_bonuses(frame, False)
                time.sleep(0.15 if acted else 0.4)
        except KeyboardInterrupt:
            print("Остановлено.")
        except Error as error:
            print("Окно игры закрыто или соединение потеряно:", error.message.splitlines()[0])
        finally:
            (output / "actions.json").write_text(json.dumps(actions, ensure_ascii=False, indent=2))
            cv2.destroyAllWindows()
            context.close()
        print(f"Выполнено действий: {len(actions)}. Журнал: session/actions.json")


def main():
    import torch
    from ultralytics import YOLO
    parser = argparse.ArgumentParser()
    parser.add_argument("--check", action="store_true", help="проверить модель на 6 снимках")
    parser.add_argument("--seconds", type=int, default=0)
    args = parser.parse_args()
    if not (ROOT / "best.pt").exists():
        raise SystemExit("Нет best.pt. Сначала запусти train.py.")
    torch.set_num_threads(4)
    model = YOLO(str(ROOT / "best.pt"))
    check(model) if args.check else play(model, args)


if __name__ == "__main__":
    main()
