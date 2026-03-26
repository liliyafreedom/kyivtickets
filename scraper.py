import requests
from bs4 import BeautifulSoup
import json
import os
import hashlib
from datetime import datetime

# ─── НАЛАШТУВАННЯ ───────────────────────────────────────────────
TELEGRAM_TOKEN = os.environ.get("TELEGRAM_TOKEN", "")
TELEGRAM_CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID", "")
SEEN_FILE = "seen_events.json"

CATEGORIES = ["концерт", "театр", "вистав", "зйомк", "стендап", "фестивал", "виставк", "шоу", "музик", "джаз", "опер", "балет"]
TARGET_MONTH = "05"
TARGET_YEAR = "2026"

# ─── ДОПОМІЖНІ ФУНКЦІЇ ──────────────────────────────────────────
def load_seen():
    if os.path.exists(SEEN_FILE):
        with open(SEEN_FILE, "r", encoding="utf-8") as f:
            return set(json.load(f))
    return set()

def save_seen(seen):
    with open(SEEN_FILE, "w", encoding="utf-8") as f:
        json.dump(list(seen), f, ensure_ascii=False)

def event_id(event):
    key = f"{event['title']}_{event['date']}_{event['source']}"
    return hashlib.md5(key.encode()).hexdigest()

def is_may_2026(date_str):
    return TARGET_MONTH in date_str and TARGET_YEAR in date_str

def send_telegram(message):
    if not TELEGRAM_TOKEN or not TELEGRAM_CHAT_ID:
        print("⚠️  Telegram не налаштований. Перевір змінні середовища.")
        print(message)
        return
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    payload = {
        "chat_id": TELEGRAM_CHAT_ID,
        "text": message,
        "parse_mode": "HTML",
        "disable_web_page_preview": True
    }
    try:
        r = requests.post(url, json=payload, timeout=10)
        r.raise_for_status()
    except Exception as e:
        print(f"Помилка Telegram: {e}")

# ─── ПАРСЕРИ ────────────────────────────────────────────────────

def scrape_concert_ua():
    events = []
    try:
        headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}
        url = "https://concert.ua/ua/catalog/kyiv/all-categories?from=2026-05-01&to=2026-05-31"
        r = requests.get(url, headers=headers, timeout=15)
        soup = BeautifulSoup(r.text, "html.parser")

        for item in soup.select(".event-card, .catalog-event, [class*='event']")[:60]:
            title_el = item.select_one("h3, h2, .title, [class*='title'], [class*='name']")
            date_el = item.select_one(".date, [class*='date'], time")
            link_el = item.select_one("a[href]")
            price_el = item.select_one(".price, [class*='price']")

            if not title_el:
                continue

            title = title_el.get_text(strip=True)
            date = date_el.get_text(strip=True) if date_el else "травень 2026"
            link = "https://concert.ua" + link_el["href"] if link_el and link_el["href"].startswith("/") else (link_el["href"] if link_el else "https://concert.ua")
            price = price_el.get_text(strip=True) if price_el else ""

            if title and len(title) > 3:
                events.append({
                    "title": title, "date": date,
                    "price": price, "link": link,
                    "source": "concert.ua", "category": detect_category(title)
                })
    except Exception as e:
        print(f"concert.ua помилка: {e}")
    return events


def scrape_karabas():
    events = []
    try:
        headers = {"User-Agent": "Mozilla/5.0"}
        url = "https://kyiv.karabas.com/may/"
        r = requests.get(url, headers=headers, timeout=15)
        soup = BeautifulSoup(r.text, "html.parser")

        for item in soup.select(".event, .event-item, article, [class*='event'], [class*='card']")[:60]:
            title_el = item.select_one("h3, h2, h4, .title, [class*='title'], [class*='name']")
            date_el = item.select_one(".date, [class*='date'], time, [class*='time']")
            link_el = item.select_one("a[href]")
            price_el = item.select_one(".price, [class*='price']")

            if not title_el:
                continue

            title = title_el.get_text(strip=True)
            date = date_el.get_text(strip=True) if date_el else "травень 2026"
            href = link_el["href"] if link_el else ""
            link = ("https://kyiv.karabas.com" + href) if href.startswith("/") else href or "https://kyiv.karabas.com"
            price = price_el.get_text(strip=True) if price_el else ""

            if title and len(title) > 3:
                events.append({
                    "title": title, "date": date,
                    "price": price, "link": link,
                    "source": "karabas.com", "category": detect_category(title)
                })
    except Exception as e:
        print(f"karabas.com помилка: {e}")
    return events


def scrape_kontramarka():
    events = []
    try:
        headers = {"User-Agent": "Mozilla/5.0"}
        url = "https://kontramarka.ua/uk/kyiv/?month=5&year=2026"
        r = requests.get(url, headers=headers, timeout=15)
        soup = BeautifulSoup(r.text, "html.parser")

        for item in soup.select(".event, [class*='event'], article, .item, [class*='card']")[:60]:
            title_el = item.select_one("h3, h2, h4, .title, [class*='title']")
            date_el = item.select_one(".date, [class*='date'], time")
            link_el = item.select_one("a[href]")
            price_el = item.select_one(".price, [class*='price']")

            if not title_el:
                continue

            title = title_el.get_text(strip=True)
            date = date_el.get_text(strip=True) if date_el else "травень 2026"
            href = link_el["href"] if link_el else ""
            link = ("https://kontramarka.ua" + href) if href.startswith("/") else href or "https://kontramarka.ua"
            price = price_el.get_text(strip=True) if price_el else ""

            if title and len(title) > 3:
                events.append({
                    "title": title, "date": date,
                    "price": price, "link": link,
                    "source": "kontramarka.ua", "category": detect_category(title)
                })
    except Exception as e:
        print(f"kontramarka.ua помилка: {e}")
    return events


def scrape_ticketsbox():
    events = []
    try:
        headers = {"User-Agent": "Mozilla/5.0"}
        url = "https://kyiv.ticketsbox.com/may/"
        r = requests.get(url, headers=headers, timeout=15)
        soup = BeautifulSoup(r.text, "html.parser")

        for item in soup.select(".event, [class*='event'], article, .item, [class*='card'], li")[:60]:
            title_el = item.select_one("h3, h2, h4, .title, [class*='title'], [class*='name']")
            date_el = item.select_one(".date, [class*='date'], time")
            link_el = item.select_one("a[href]")
            price_el = item.select_one(".price, [class*='price']")

            if not title_el:
                continue

            title = title_el.get_text(strip=True)
            date = date_el.get_text(strip=True) if date_el else "травень 2026"
            href = link_el["href"] if link_el else ""
            link = ("https://kyiv.ticketsbox.com" + href) if href.startswith("/") else href or "https://kyiv.ticketsbox.com"
            price = price_el.get_text(strip=True) if price_el else ""

            if title and len(title) > 3:
                events.append({
                    "title": title, "date": date,
                    "price": price, "link": link,
                    "source": "ticketsbox.com", "category": detect_category(title)
                })
    except Exception as e:
        print(f"ticketsbox.com помилка: {e}")
    return events


def scrape_afisha_ua():
    events = []
    try:
        headers = {"User-Agent": "Mozilla/5.0"}
        url = "https://afisha.ua/kyiv/all/?period=month&date=2026-05"
        r = requests.get(url, headers=headers, timeout=15)
        soup = BeautifulSoup(r.text, "html.parser")

        for item in soup.select(".b-event-tile, .event, article, [class*='event'], [class*='tile']")[:60]:
            title_el = item.select_one("h3, h2, h4, .title, [class*='title'], [class*='name']")
            date_el = item.select_one(".date, [class*='date'], time")
            link_el = item.select_one("a[href]")
            price_el = item.select_one(".price, [class*='price']")

            if not title_el:
                continue

            title = title_el.get_text(strip=True)
            date = date_el.get_text(strip=True) if date_el else "травень 2026"
            href = link_el["href"] if link_el else ""
            link = ("https://afisha.ua" + href) if href.startswith("/") else href or "https://afisha.ua"
            price = price_el.get_text(strip=True) if price_el else ""

            if title and len(title) > 3:
                events.append({
                    "title": title, "date": date,
                    "price": price, "link": link,
                    "source": "afisha.ua", "category": detect_category(title)
                })
    except Exception as e:
        print(f"afisha.ua помилка: {e}")
    return events


# ─── КАТЕГОРИЗАЦІЯ ──────────────────────────────────────────────
CATEGORY_MAP = {
    "🎵 Концерт": ["концерт", "музик", "джаз", "рок", "поп", "хіп-хоп", "live", "виступ", "тур"],
    "🎭 Театр / Вистава": ["театр", "вистав", "спектакл", "опер", "балет", "мюзикл", "прем'єр"],
    "🎤 Зйомка / Стендап": ["зйомк", "стендап", "stand-up", "гумор", "comedy", "квартал"],
    "🎪 Фестиваль / Виставка": ["фестивал", "виставк", "ярмарок", "форум", "арт", "культур"],
    "🎬 Кіно": ["кіно", "фільм", "прем'єра", "cinema"],
    "🎊 Шоу": ["шоу", "show", "цирк", "магія"],
}

def detect_category(title):
    title_lower = title.lower()
    for cat, keywords in CATEGORY_MAP.items():
        if any(kw in title_lower for kw in keywords):
            return cat
    return "📅 Інша подія"


# ─── ФОРМАТУВАННЯ ПОВІДОМЛЕННЯ ──────────────────────────────────
def format_message(new_events):
    if not new_events:
        return None

    by_cat = {}
    for e in new_events:
        cat = e.get("category", "📅 Інша подія")
        by_cat.setdefault(cat, []).append(e)

    lines = [f"🗓 <b>Нові події в Києві — травень 2026</b>"]
    lines.append(f"Знайдено нових: <b>{len(new_events)}</b>\n")

    for cat, evts in sorted(by_cat.items()):
        lines.append(f"\n{cat} ({len(evts)})")
        for e in evts[:5]:
            title = e['title'][:55] + ("…" if len(e['title']) > 55 else "")
            price = f" · {e['price']}" if e.get('price') else ""
            date = e.get('date', '')[:20]
            link = e.get('link', '')
            lines.append(f"• <a href='{link}'>{title}</a>")
            lines.append(f"  📆 {date}{price}")

    lines.append(f"\n⏰ Оновлено: {datetime.now().strftime('%d.%m.%Y %H:%M')}")
    return "\n".join(lines)


# ─── ГОЛОВНА ФУНКЦІЯ ────────────────────────────────────────────
def main():
    print(f"[{datetime.now().strftime('%H:%M:%S')}] Починаємо збір подій...")

    all_events = []
    scrapers = [
        ("concert.ua",    scrape_concert_ua),
        ("karabas.com",   scrape_karabas),
        ("kontramarka",   scrape_kontramarka),
        ("ticketsbox",    scrape_ticketsbox),
        ("afisha.ua",     scrape_afisha_ua),
    ]

    for name, fn in scrapers:
        print(f"  → Парсимо {name}...")
        found = fn()
        print(f"     Знайдено: {len(found)} подій")
        all_events.extend(found)

    # Збереження всіх знайдених подій
    with open("all_events_may2026.json", "w", encoding="utf-8") as f:
        json.dump(all_events, f, ensure_ascii=False, indent=2)
    print(f"\nВсього знайдено: {len(all_events)} подій")

    # Фільтр тільки нових
    seen = load_seen()
    new_events = []
    new_ids = set()

    for e in all_events:
        eid = event_id(e)
        if eid not in seen:
            new_events.append(e)
            new_ids.add(eid)

    print(f"Нових (не бачених раніше): {len(new_events)}")

    if new_events:
        # Надсилаємо по 20 за раз (ліміт Telegram)
        for i in range(0, len(new_events), 20):
            chunk = new_events[i:i+20]
            msg = format_message(chunk)
            if msg:
                send_telegram(msg)

        seen.update(new_ids)
        save_seen(seen)
        print("✅ Повідомлення надіслано в Telegram!")
    else:
        print("ℹ️  Нових подій не знайдено.")
        send_telegram(f"ℹ️ Перевірка завершена — нових подій на травень 2026 не знайдено.\n⏰ {datetime.now().strftime('%d.%m.%Y %H:%M')}")


if __name__ == "__main__":
    main()
