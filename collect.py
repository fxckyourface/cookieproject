"""Автоматический сбор и разметка новых снимков. Играть можно вручную."""
import argparse
import json
import time
from playwright.sync_api import sync_playwright
from app import URL, ROOT, pause_bonuses


def visible_buttons(frame):
    return frame.locator("button").evaluate_all("""els => els.map(el => {
        const r=el.getBoundingClientRect(), s=getComputedStyle(el);
        let rect={x:r.x,y:r.y,width:r.width,height:r.height};
        if(s.visibility==='hidden'||s.display==='none') return null;
        for(let parent=el.parentElement;parent;parent=parent.parentElement){
            const style=getComputedStyle(parent), b=parent.getBoundingClientRect();
            if(/(auto|scroll|hidden|clip)/.test(style.overflowY)){
                const bottom=Math.min(rect.y+rect.height,b.bottom);
                rect.y=Math.max(rect.y,b.top);rect.height=bottom-rect.y;
            }
        }
        const hit=document.elementFromPoint(rect.x+rect.width/2,rect.y+rect.height/2);
        if(!hit||!el.contains(hit)||rect.width<=0||rect.height<=0)return null;
        return {name:el.getAttribute('aria-label')||el.textContent,
                cls:el.className,disabled:el.disabled,box:rect};
    }).filter(Boolean)""")


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument("--count",type=int,default=30)
    args=parser.parse_args()
    output=ROOT / "collected"
    output.mkdir(exist_ok=True)
    (output / "screenshots").mkdir(exist_ok=True)
    records=[]
    with sync_playwright() as p:
        browser=p.chromium.launch(headless=False)
        page=browser.new_page(viewport={"width":1280,"height":720},device_scale_factor=1)
        page.goto(URL,wait_until="domcontentloaded")
        print("Открой игру, закрой первую рекламу. Во время сбора кликай и открывай магазин.")
        input("Нажми Enter для начала сбора: ")
        frame=page.locator("#game-frame").element_handle().content_frame()
        for i in range(args.count):
            name=f"sample_{i:02d}"
            pause_bonuses(frame, True)
            offset=page.locator("#game-frame").bounding_box()
            buttons=visible_buttons(frame)
            full_ad=page.get_by_test_id("yandex-fullscreen-render-button")
            if full_ad.count() and full_ad.first.is_visible():
                buttons=[]
            for close in page.get_by_test_id("yandex-fullscreen-render-button").all():
                if close.is_visible():
                    box=close.bounding_box()
                    box["x"]-=offset["x"];box["y"]-=offset["y"]
                    buttons.append({"name":"Закрыть рекламу","cls":"ad-close","disabled":False,"box":box})
            page.screenshot(path=str(output / "screenshots" / (name+".png")))
            pause_bonuses(frame, False)
            records.append({"name":name,"offset":offset,"buttons":buttons})
            print(f"Снимок {i+1}/{args.count}")
            time.sleep(1)
        browser.close()
    (output / "samples.json").write_text(json.dumps(records,ensure_ascii=False,indent=2))
    print("Готово. Разметка: python prepare_data.py --source collected")


if __name__=="__main__":
    main()
