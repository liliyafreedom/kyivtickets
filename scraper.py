import requests
from bs4 import BeautifulSoup
import json
import os
import hashlib
from datetime import datetime
import time

TELEGRAM_TOKEN = os.environ.get("TELEGRAM_TOKEN", "")
TELEGRAM_CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID", "")
SEEN_FILE = "seen_events.json"

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "uk-UA,uk;q=0.9,en;q=0.8",
    "Referer": "https://google.com",
}

MAY_KEYWORDS = ["may", "трав", " 05 ", ".05.", "/05/", "05/2026",
                 "16 may", "17 may", "30 may", "01 may", "02 may",
                 "03 may", "04 may", "05 may", "06 may", "07 may",
                 "08 may", "09 may", "10 may", "11 may", "12 may",
                 "13 may", "14 may", "15 may", "18 may", "19 may",
                 "20 may", "21 may", "22 may", "23 may", "24 may",
                 "25 may", "26 may", "27 may", "28 may", "29 may", "31 may"]

def is_may_event(date_str):
    if not date_str:
        return True  # якщо дата невідома — включаємо
    d = date_str.lower()
    return any(k in d for k in MAY_KEYWORDS)

# ═══════════════════════════════════════════════════════════
# КАТЕГОРИЗАЦІЯ
# ═══════════════════════════════════════════════════════════

CATEGORY_MAP = {
    "🎵 Концерт":          ["концерт", "concert", "музик", "джаз", "jazz", "рок", "rock", "поп", "реп", "rap", "live", "виступ", "тур", "гурт", "симфон", "symphony", "органн", "філармон", "philharmon", "бумбокс", "dzidzio", "onuka", "sadsvit", "tik tu", "jerry heil", "vivienne"],
    "🎭 Театр / Вистава":  ["театр", "theatre", "theater", "вистав", "спектакл", "опер", "opera", "балет", "ballet", "мюзикл", "musical", "прем'єр", "драм", "drama", "dakh daughters", "перформанс", "performance"],
    "🎤 Стендап / Зйомка": ["зйомк", "стендап", "stand-up", "standup", "гумор", "humor", "comedy", "квартал", "дизель", "розгон", "business stand up"],
    "🎪 Фестиваль":        ["фестивал", "fest", "festival", "open-air", "опенейр", "форум культ"],
    "🖼 Виставка / Форум": ["виставк", "exhibition", "expo", "форум", "forum", "конгрес", "конференц", "congress"],
    "🎬 Шоу":              ["шоу", "show", "цирк", "circus", "magic", "магія"],
    "👶 Дітям":            ["дітям", "дитяч", "children", "kids", "казк", "ляльк", "puppet"],
    "🏃 Спорт / Забіг":    ["марафон", "marathon", "забіг", "spartan", "спорт", "sport", "турнір", "трейл", "trail", "race", "run"],
    "💃 Танці / Вечірка":  ["танц", "dance", "party", "вечірк", "nightlife", "tango", "salsa", "bachata"],
    "💼 Бізнес":           ["бізнес", "business", "it ", "tech", "dou ", "dev", "startup", "invest"],
}

def detect_category(title):
    t = title.lower()
    for cat, kws in CATEGORY_MAP.items():
        if any(k in t for k in kws):
            return cat
    return "📅 Подія"

# ═══════════════════════════════════════════════════════════
# ПАРСЕРИ
# ═══════════════════════════════════════════════════════════

def scrape_allevents_category(url, label):
    events = []
    try:
        s = requests.Session()
        s.headers.update(HEADERS)
        r = s.get(url, timeout=25)
        soup = BeautifulSoup(r.text, "html.parser")

        # Точні селектори allevents.in з реального HTML
        for item in soup.select("li"):
            link_el = item.select_one("a[href*='/kiev/']")
            if not link_el:
                continue
            title = link_el.get_text(strip=True)
            if len(title) < 3 or len(title) > 200:
                continue
            # Пропускаємо технічні елементи
            if any(x in title.lower() for x in ["sign in", "login", "create event", "allevents", "open app"]):
                continue

            # Дата — шукаємо текст поруч
            date = ""
            parent = link_el.parent
            for _ in range(3):
                if parent:
                    date_candidate = parent.get_text(" ", strip=True)
                    # Шукаємо дату у форматі "Sat, 16 May, 2026"
                    import re
                    match = re.search(r'(Mon|Tue|Wed|Thu|Fri|Sat|Sun),?\s+\d{1,2}\s+\w+,?\s+\d{4}', date_candidate)
                    if match:
                        date = match.group(0)
                        break
                    match = re.search(r'\d{1,2}\s+(Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)\w*\s+\d{4}', date_candidate)
                    if match:
                        date = match.group(0)
                        break
                    parent = parent.parent

            # Місце проведення
            venue = ""
            if item.select_one("p, [class*='venue'], [class*='location']"):
                venue_el = item.select_one("p, [class*='venue'], [class*='location']")
                venue_text = venue_el.get_text(strip=True) if venue_el else ""
                if len(venue_text) < 80:
                    venue = venue_text

            href = link_el.get("href", "")
            link = href if href.startswith("http") else "https://allevents.in" + href

            # Фільтруємо тільки травень або невідому дату
            if date and not is_may_event(date):
                continue

            events.append({
                "title": title,
                "date": date,
                "venue": venue,
                "price": "",
                "link": link,
                "source": f"allevents.in ({label})",
                "category": detect_category(title),
            })
    except Exception as e:
        print(f"  allevents {label}: {e}")
    return events


def scrape_allevents_all():
    """Парсить усі категорії allevents.in"""
    all_events = []
    categories = [
        ("all",          "https://allevents.in/kiev-ua/all"),
        ("concerts",     "https://allevents.in/kiev-ua/concerts"),
        ("music",        "https://allevents.in/kiev-ua/music"),
        ("theatre",      "https://allevents.in/kiev-ua/theatre"),
        ("performances", "https://allevents.in/kiev-ua/performances"),
        ("comedy",       "https://allevents.in/kiev-ua/comedy"),
        ("festivals",    "https://allevents.in/kiev-ua/festivals"),
        ("art",          "https://allevents.in/kiev-ua/art"),
        ("dance",        "https://allevents.in/kiev-ua/dance"),
        ("kids",         "https://allevents.in/kiev-ua/kids"),
        ("exhibitions",  "https://allevents.in/kiev-ua/exhibitions"),
        ("sports",       "https://allevents.in/kiev-ua/sports"),
    ]
    for label, url in categories:
        found = scrape_allevents_category(url, label)
        print(f"     allevents/{label}: {len(found)}")
        all_events.extend(found)
        time.sleep(1)
    return all_events


def scrape_ticketsbox():
    events = []
    try:
        s = requests.Session()
        s.headers.update(HEADERS)
        for url in ["https://kyiv.ticketsbox.com/may/", "https://kyiv.ticketsbox.com/"]:
            r = s.get(url, timeout=20)
            soup = BeautifulSoup(r.text, "html.parser")
            for item in soup.select(".event-item, .b-events__item, article, [class*='event'], li.item, .item")[:80]:
                title_el = item.select_one("h3, h2, h4, [class*='title'], [class*='name']")
                date_el  = item.select_one("time, [class*='date']")
                link_el  = item.select_one("a[href]")
                price_el = item.select_one("[class*='price']")
                if not title_el: continue
                title = title_el.get_text(strip=True)
                if len(title) < 3 or len(title) > 200: continue
                date = date_el.get_text(strip=True)[:40] if date_el else ""
                price = price_el.get_text(strip=True)[:25] if price_el else ""
                href = link_el["href"] if link_el else ""
                link = ("https://kyiv.ticketsbox.com" + href) if href.startswith("/") else href or "https://kyiv.ticketsbox.com"
                events.append({"title": title, "date": date, "price": price, "venue": "",
                                "link": link, "source": "ticketsbox.com", "category": detect_category(title)})
            if events: break
    except Exception as e:
        print(f"  ticketsbox: {e}")
    return events


def scrape_origin_stage():
    events = []
    try:
        s = requests.Session()
        s.headers.update(HEADERS)
        r = s.get("https://originstage.com.ua/events/", timeout=20)
        soup = BeautifulSoup(r.text, "html.parser")
        for item in soup.select("article, .event, [class*='event'], [class*='show'], li, [class*='card']")[:50]:
            title_el = item.select_one("h3, h2, h4, [class*='title'], [class*='name']")
            date_el  = item.select_one("time, [class*='date']")
            link_el  = item.select_one("a[href]")
            if not title_el: continue
            title = title_el.get_text(strip=True)
            if len(title) < 3: continue
            date = date_el.get_text(strip=True)[:40] if date_el else ""
            href = link_el["href"] if link_el else ""
            link = ("https://originstage.com.ua" + href) if href.startswith("/") else href or "https://originstage.com.ua"
            events.append({"title": title, "date": date, "price": "", "venue": "ORIGIN STAGE",
                            "link": link, "source": "ORIGIN STAGE", "category": detect_category(title)})
    except Exception as e:
        print(f"  originstage: {e}")
    return events


def scrape_opera():
    events = []
    try:
        s = requests.Session()
        s.headers.update(HEADERS)
        r = s.get("https://opera.com.ua/afisha", timeout=20)
        soup = BeautifulSoup(r.text, "html.parser")
        for item in soup.select(".b-afisha__item, [class*='afisha'], [class*='performance'], article, li, [class*='item']")[:60]:
            title_el = item.select_one("h3, h2, h4, [class*='title'], [class*='name']")
            date_el  = item.select_one("time, [class*='date'], [class*='day']")
            link_el  = item.select_one("a[href]")
            if not title_el: continue
            title = title_el.get_text(strip=True)
            if len(title) < 3 or len(title) > 150: continue
            date = date_el.get_text(strip=True)[:40] if date_el else ""
            href = link_el["href"] if link_el else ""
            link = ("https://opera.com.ua" + href) if href.startswith("/") else href or "https://opera.com.ua/afisha"
            events.append({"title": title, "date": date, "price": "", "venue": "Опера Шевченка",
                            "link": link, "source": "opera.com.ua", "category": "🎭 Театр / Вистава"})
    except Exception as e:
        print(f"  opera: {e}")
    return events


def scrape_molody():
    events = []
    try:
        s = requests.Session()
        s.headers.update(HEADERS)
        r = s.get("https://molodyytheatre.com/afisha", timeout=20)
        soup = BeautifulSoup(r.text, "html.parser")
        for item in soup.select("article, .performance, [class*='afisha'], [class*='event'], li, [class*='item']")[:60]:
            title_el = item.select_one("h3, h2, h4, [class*='title'], [class*='name']")
            date_el  = item.select_one("time, [class*='date']")
            link_el  = item.select_one("a[href]")
            if not title_el: continue
            title = title_el.get_text(strip=True)
            if len(title) < 3 or len(title) > 150: continue
            date = date_el.get_text(strip=True)[:40] if date_el else ""
            href = link_el["href"] if link_el else ""
            link = ("https://molodyytheatre.com" + href) if href.startswith("/") else href or "https://molodyytheatre.com"
            events.append({"title": title, "date": date, "price": "", "venue": "Молодий театр",
                            "link": link, "source": "molodyytheatre.com", "category": "🎭 Театр / Вистава"})
    except Exception as e:
        print(f"  molody: {e}")
    return events


def scrape_kyivcity():
    events = []
    try:
        s = requests.Session()
        s.headers.update(HEADERS)
        r = s.get("https://kyivcity.gov.ua/news/category/events/", timeout=20)
        soup = BeautifulSoup(r.text, "html.parser")
        for item in soup.select("article, .news-item, [class*='event'], [class*='news'], li")[:30]:
            title_el = item.select_one("h3, h2, h4, [class*='title']")
            date_el  = item.select_one("time, [class*='date']")
            link_el  = item.select_one("a[href]")
            if not title_el: continue
            title = title_el.get_text(strip=True)
            if len(title) < 3: continue
            date = date_el.get_text(strip=True)[:40] if date_el else ""
            href = link_el["href"] if link_el else ""
            link = ("https://kyivcity.gov.ua" + href) if href.startswith("/") else href or "https://kyivcity.gov.ua"
            events.append({"title": title, "date": date, "price": "🆓 безкоштовно", "venue": "",
                            "link": link, "source": "kyivcity.gov.ua", "category": detect_category(title)})
    except Exception as e:
        print(f"  kyivcity: {e}")
    return events


# ═══════════════════════════════════════════════════════════
# TELEGRAM
# ═══════════════════════════════════════════════════════════

def send_telegram(message):
    if not TELEGRAM_TOKEN or not TELEGRAM_CHAT_ID:
        print(message)
        return False
    try:
        r = requests.post(
            f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage",
            json={"chat_id": TELEGRAM_CHAT_ID, "text": message,
                  "parse_mode": "HTML", "disable_web_page_preview": True},
            timeout=15
        )
        r.raise_for_status()
        return True
    except Exception as e:
        print(f"Telegram: {e}")
        return False

def send_long(text):
    max_len = 3800
    while len(text) > max_len:
        cut = text.rfind("\n", 0, max_len)
        if cut == -1: cut = max_len
        send_telegram(text[:cut])
        text = text[cut:]
        time.sleep(0.5)
    send_telegram(text)

# ═══════════════════════════════════════════════════════════
# ДЕДУБЛІКАЦІЯ
# ═══════════════════════════════════════════════════════════

def event_id(e):
    return hashlib.md5(e["title"].lower().strip().encode()).hexdigest()

def deduplicate(events):
    seen = {}
    for e in events:
        eid = event_id(e)
        if eid not in seen:
            seen[eid] = e
    return list(seen.values())

def load_seen():
    if os.path.exists(SEEN_FILE):
        with open(SEEN_FILE, "r") as f:
            return set(json.load(f))
    return set()

def save_seen(seen):
    with open(SEEN_FILE, "w") as f:
        json.dump(list(seen), f)

# ═══════════════════════════════════════════════════════════
# ФОРМАТУВАННЯ
# ═══════════════════════════════════════════════════════════

def format_stats(stats, total):
    lines = ["📊 <b>Статистика — Київ травень 2026</b>\n"]
    for name, count in sorted(stats.items(), key=lambda x: -x[1]):
        icon = "✅" if count > 0 else "⚠️"
        lines.append(f"{icon} {name}: <b>{count}</b>")
    lines.append(f"\n📦 Унікальних подій: <b>{total}</b>")
    lines.append(f"⏰ {datetime.now().strftime('%d.%m.%Y %H:%M')}")
    return "\n".join(lines)

def format_full(events, new_ids):
    by_cat = {}
    for e in events:
        by_cat.setdefault(e["category"], []).append(e)

    lines = [f"📋 <b>УСІ події — Київ, травень 2026</b>",
             f"Всього: <b>{len(events)}</b>\n"]
    for cat in sorted(by_cat):
        evts = by_cat[cat]
        lines.append(f"\n{cat} — {len(evts)} шт.")
        for e in evts:
            is_new = "🆕 " if event_id(e) in new_ids else ""
            t = e["title"][:55] + ("…" if len(e["title"]) > 55 else "")
            d = e.get("date", "")[:25]
            v = e.get("venue", "")[:30]
            p = e.get("price", "")[:20]
            details = " · ".join(filter(None, [d, v, p]))
            suffix = f"\n  📆 {details}" if details else ""
            lines.append(f"{is_new}• <a href='{e['link']}'>{t}</a>{suffix}")
    lines.append(f"\n🆕 = нова  |  ⏰ {datetime.now().strftime('%d.%m.%Y %H:%M')}")
    return "\n".join(lines)

def format_new(new_events):
    if not new_events: return None
    by_cat = {}
    for e in new_events:
        by_cat.setdefault(e["category"], []).append(e)
    lines = [f"🆕 <b>НОВІ події — додались сьогодні!</b>",
             f"Кількість: <b>{len(new_events)}</b>\n"]
    for cat in sorted(by_cat):
        lines.append(f"\n{cat}")
        for e in by_cat[cat]:
            t = e["title"][:55] + ("…" if len(e["title"]) > 55 else "")
            d = e.get("date", "")[:25]
            v = e.get("venue", "")[:30]
            details = " · ".join(filter(None, [d, v]))
            suffix = f"\n  📆 {details}" if details else ""
            lines.append(f"• <a href='{e['link']}'>{t}</a>{suffix}")
    lines.append(f"\n⏰ {datetime.now().strftime('%d.%m.%Y %H:%M')}")
    return "\n".join(lines)

# ═══════════════════════════════════════════════════════════
# ГОЛОВНА
# ═══════════════════════════════════════════════════════════

def main():
    print(f"\n{'='*55}")
    print(f"  Kyiv Events Monitor — {datetime.now().strftime('%d.%m.%Y %H:%M')}")
    print(f"{'='*55}\n")

    all_raw = []
    stats = {}

    # 1. Головне джерело — allevents.in (всі категорії)
    print("→ allevents.in (всі категорії)...")
    ae_events = scrape_allevents_all()
    stats["allevents.in"] = len(ae_events)
    all_raw.extend(ae_events)

    # 2. Інші джерела
    other_scrapers = [
        ("ticketsbox.com",     scrape_ticketsbox),
        ("originstage.com.ua", scrape_origin_stage),
        ("opera.com.ua",       scrape_opera),
        ("molodyytheatre.com", scrape_molody),
        ("kyivcity.gov.ua",    scrape_kyivcity),
    ]
    for name, fn in other_scrapers:
        print(f"→ {name}...")
        found = fn()
        print(f"   {len(found)} подій")
        stats[name] = len(found)
        all_raw.extend(found)
        time.sleep(0.5)

    all_events = deduplicate(all_raw)
    print(f"\n✔ Всього: {len(all_raw)} → унікальних: {len(all_events)}")

    with open("all_events_may2026.json", "w", encoding="utf-8") as f:
        json.dump(all_events, f, ensure_ascii=False, indent=2)

    seen = load_seen()
    new_events, new_ids = [], set()
    for e in all_events:
        eid = event_id(e)
        if eid not in seen:
            new_events.append(e)
            new_ids.add(eid)

    print(f"🆕 Нових: {len(new_events)}")

    if not all_events:
        send_telegram(f"⚠️ Жодного результату.\n⏰ {datetime.now().strftime('%d.%m.%Y %H:%M')}")
        return

    send_telegram(format_stats(stats, len(all_events)))
    time.sleep(1)
    send_long(format_full(all_events, new_ids))
    time.sleep(1)

    if new_events:
        msg = format_new(new_events)
        if msg: send_long(msg)
        seen.update(new_ids)
        save_seen(seen)
    else:
        send_telegram(f"✅ Нових подій сьогодні не додалось.\n⏰ {datetime.now().strftime('%d.%m.%Y %H:%M')}")

    print("✅ Готово!")

if __name__ == "__main__":
    main()
