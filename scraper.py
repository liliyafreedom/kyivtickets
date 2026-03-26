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
}

# ═══════════════════════════════════════════════════════════
# ПОВНИЙ СПИСОК ДЖЕРЕЛ
# ═══════════════════════════════════════════════════════════

SOURCES = {

    # ── АГРЕГАТОРИ (продають квитки з багатьох місць) ──────
    "aggregators": [
        {"name": "concert.ua — концерти",     "url": "https://concert.ua/ua/catalog/kyiv/concerts?from=2026-05-01&to=2026-05-31"},
        {"name": "concert.ua — театр",        "url": "https://concert.ua/ua/catalog/kyiv/theater?from=2026-05-01&to=2026-05-31"},
        {"name": "concert.ua — стендап",      "url": "https://concert.ua/ua/catalog/kyiv/stand-up?from=2026-05-01&to=2026-05-31"},
        {"name": "concert.ua — фестивалі",    "url": "https://concert.ua/ua/catalog/kyiv/festivals?from=2026-05-01&to=2026-05-31"},
        {"name": "concert.ua — дітям",        "url": "https://concert.ua/ua/catalog/kyiv/for-kids?from=2026-05-01&to=2026-05-31"},
        {"name": "karabas — травень",         "url": "https://kyiv.karabas.com/may/"},
        {"name": "karabas — театр",           "url": "https://kyiv.karabas.com/theatres/"},
        {"name": "karabas — концерти",        "url": "https://kyiv.karabas.com/concerts/"},
        {"name": "karabas — клуби",           "url": "https://kyiv.karabas.com/clubs/"},
        {"name": "kontramarka — травень",     "url": "https://kontramarka.ua/uk/kyiv/?month=5&year=2026"},
        {"name": "kontramarka — театр",       "url": "https://kontramarka.ua/uk/theatre?city=kyiv"},
        {"name": "kontramarka — концерти",    "url": "https://kontramarka.ua/uk/concert?city=kyiv"},
        {"name": "ticketsbox — травень",      "url": "https://kyiv.ticketsbox.com/may/"},
        {"name": "ticketsbox — театр",        "url": "https://kyiv.ticketsbox.com/theater/"},
        {"name": "ticketsbox — концерти",     "url": "https://kyiv.ticketsbox.com/concert/"},
        {"name": "kvytok.co — театр",         "url": "https://kvytok.co/theater/"},
        {"name": "kvytok.co — концерти",      "url": "https://kvytok.co/concert/"},
    ],

    # ── ТЕАТРИ (офіційні сайти) ────────────────────────────
    "theaters": [
        {"name": "Опера Шевченка",            "url": "https://opera.com.ua/afisha"},
        {"name": "Київська опера",            "url": "https://kyivopera.com.ua/afisha/"},
        {"name": "Театр Франка",              "url": "https://ft.org.ua/performance/"},
        {"name": "Театр Лесі Українки",       "url": "https://rutheater.com.ua/uk/afisha"},
        {"name": "Молодий театр",             "url": "https://molodyytheatre.com/afisha"},
        {"name": "Театр на Подолі",           "url": "https://teatrpodil.com/afisha/"},
        {"name": "Театр Оперети",             "url": "https://operetta.com.ua/afisha/"},
        {"name": "Театр Колесо",              "url": "https://teatrkoleso.com.ua/afisha"},
        {"name": "Театр на Лівому березі",    "url": "https://ltb.com.ua/afisha"},
        {"name": "Театр юного глядача",       "url": "https://tyg.kiev.ua/afisha"},
        {"name": "Театр ляльок",              "url": "https://puppet.com.ua/afisha"},
        {"name": "Театр Сузір'я",             "url": "https://suzirya.com.ua/afisha/"},
        {"name": "МКЦ ім. Козловського",      "url": "https://mkc.org.ua/afisha/"},
        {"name": "Центр ім. Курбаса",         "url": "https://kurbas.org.ua/afisha"},
        {"name": "Будинок Актора",            "url": "https://bdaktora.com.ua/afisha"},
    ],

    # ── КОНЦЕРТНІ МАЙДАНЧИКИ ───────────────────────────────
    "venues": [
        {"name": "Палац Україна",             "url": "https://palace.com.ua/afisha/"},
        {"name": "Палац Спорту",              "url": "https://palacesport.com.ua/events/"},
        {"name": "Жовтневий палац",           "url": "https://zhovtnevy.com.ua/afisha/"},
        {"name": "ORIGIN STAGE",              "url": "https://originstage.com.ua/events/"},
        {"name": "Stereo Plaza",              "url": "https://stereoplaza.ua/afisha/"},
        {"name": "Atlas",                     "url": "https://clubatlas.com.ua/afisha/"},
        {"name": "Caribbean Club",            "url": "https://caribbean.kiev.ua/afisha/"},
        {"name": "Sentrum",                   "url": "https://sentrum.com.ua/afisha/"},
        {"name": "Дах ЦУМ",                   "url": "https://dakhtsum.com/events/"},
        {"name": "Арт-завод Платформа",       "url": "https://artplatforma.com.ua/events/"},
        {"name": "Планетарій",                "url": "https://planetarium.kiev.ua/program"},
        {"name": "Філармонія",                "url": "https://filarmonia.com.ua/afisha/"},
        {"name": "МЦКМ",                      "url": "https://mckm.org.ua/afisha"},
    ],
}


# ═══════════════════════════════════════════════════════════
# КАТЕГОРИЗАЦІЯ
# ═══════════════════════════════════════════════════════════

CATEGORY_MAP = {
    "🎵 Концерт":           ["концерт", "музик", "джаз", "рок", "поп", "реп", "live", "виступ", "тур", "гурт", "onuka", "dzidzio", "океан", "filarmonia", "філармон", "органн"],
    "🎭 Театр / Вистава":   ["театр", "вистав", "спектакл", "опер", "балет", "мюзикл", "прем'єр", "драм", "франка", "лесі", "оперет", "лялькови"],
    "🎤 Стендап / Зйомка":  ["зйомк", "стендап", "stand-up", "гумор", "comedy", "квартал", "дизель", "розгон", "жарт"],
    "🎪 Фестиваль":         ["фестивал", "fest", "festival", "опенейр", "open-air"],
    "🖼 Виставка":          ["виставк", "галере", "музей", "арт", "експозиц"],
    "🎬 Кіно / Шоу":        ["кіно", "фільм", "шоу", "show", "цирк", "планетар"],
    "👶 Дітям":             ["дітям", "дитяч", "казк", "ляльк", "puppet"],
    "🎻 Класична музика":   ["класичн", "симфон", "камерн", "орке", "квартет", "соліст"],
}

def detect_category(title):
    t = title.lower()
    for cat, kws in CATEGORY_MAP.items():
        if any(k in t for k in kws):
            return cat
    return "📅 Подія"


# ═══════════════════════════════════════════════════════════
# ПАРСЕР (універсальний)
# ═══════════════════════════════════════════════════════════

def parse_page(url, source_name):
    events = []
    try:
        session = requests.Session()
        session.headers.update(HEADERS)
        r = session.get(url, timeout=20, verify=False)
        if r.status_code != 200:
            print(f"     ⚠️  {source_name}: HTTP {r.status_code}")
            return events

        soup = BeautifulSoup(r.text, "html.parser")

        # Шукаємо контейнери подій (багато варіантів)
        selectors = [
            ".catalog-item", ".event-card", ".event-item", ".event-tile",
            ".b-event-tile", "[class*='EventCard']", "[class*='event-card']",
            "[class*='event_card']", "[class*='concert']", "[class*='show-item']",
            "article.event", ".schedule-item", ".afisha-item", ".poster-item",
            ".repertoire-item", ".performance-item", "li.event", ".card-event",
        ]
        items = []
        for sel in selectors:
            found = soup.select(sel)
            if found:
                items = found
                break

        # Fallback: всі article або li з посиланням
        if not items:
            items = soup.select("article") or soup.select("li:has(a)")

        for item in items[:50]:
            title_el = item.select_one(
                "h1, h2, h3, h4, "
                "[class*='title'], [class*='name'], [class*='Title'], [class*='Name'], "
                "[class*='heading'], [class*='caption']"
            )
            date_el = item.select_one(
                "time, [class*='date'], [class*='Date'], "
                "[class*='time'], [class*='when'], [class*='schedule']"
            )
            link_el = item.select_one("a[href]")
            price_el = item.select_one(
                "[class*='price'], [class*='Price'], [class*='cost'], [class*='ticket']"
            )

            if not title_el:
                continue

            title = title_el.get_text(strip=True)
            if len(title) < 3 or len(title) > 200:
                continue
            # Пропускаємо технічні рядки
            skip = ["cookie", "javascript", "завантаж", "підпис", "реєстрац", "увійдіть"]
            if any(s in title.lower() for s in skip):
                continue

            date = date_el.get_text(strip=True)[:30] if date_el else "травень 2026"
            price = price_el.get_text(strip=True)[:30] if price_el else ""

            href = link_el["href"] if link_el else ""
            if href.startswith("http"):
                link = href
            elif href.startswith("/"):
                from urllib.parse import urlparse
                base = urlparse(url)
                link = f"{base.scheme}://{base.netloc}{href}"
            else:
                link = url

            events.append({
                "title": title,
                "date": date,
                "price": price,
                "link": link,
                "source": source_name,
                "category": detect_category(title),
            })

    except Exception as e:
        print(f"     ❌ {source_name}: {e}")
    return events


# ═══════════════════════════════════════════════════════════
# TELEGRAM
# ═══════════════════════════════════════════════════════════

def send_telegram(message):
    if not TELEGRAM_TOKEN or not TELEGRAM_CHAT_ID:
        print(message)
        return False
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    try:
        r = requests.post(url, json={
            "chat_id": TELEGRAM_CHAT_ID,
            "text": message,
            "parse_mode": "HTML",
            "disable_web_page_preview": True
        }, timeout=15)
        r.raise_for_status()
        return True
    except Exception as e:
        print(f"Telegram помилка: {e}")
        return False

def send_long(text):
    max_len = 3800
    while len(text) > max_len:
        cut = text.rfind("\n", 0, max_len)
        if cut == -1:
            cut = max_len
        send_telegram(text[:cut])
        text = text[cut:]
        time.sleep(0.5)
    send_telegram(text)


# ═══════════════════════════════════════════════════════════
# ФОРМАТУВАННЯ
# ═══════════════════════════════════════════════════════════

def format_full(all_events, new_ids):
    by_cat = {}
    for e in all_events:
        by_cat.setdefault(e["category"], []).append(e)

    lines = [f"📋 <b>УСІ події — Київ, травень 2026</b>",
             f"Знайдено: <b>{len(all_events)}</b> подій з <b>{len(set(e['source'] for e in all_events))}</b> джерел\n"]

    for cat in sorted(by_cat):
        evts = by_cat[cat]
        lines.append(f"\n{cat} — {len(evts)} шт.")
        for e in evts:
            is_new = "🆕 " if event_id(e) in new_ids else ""
            t = e["title"][:55] + ("…" if len(e["title"]) > 55 else "")
            d = e["date"][:20] if e["date"] != "травень 2026" else ""
            p = f" · {e['price'][:15]}" if e.get("price") else ""
            date_str = f"\n  📆 {d}{p}" if d or p else ""
            lines.append(f"{is_new}• <a href='{e['link']}'>{t}</a>{date_str}")

    lines.append(f"\n🆕 = нова подія сьогодні")
    lines.append(f"⏰ {datetime.now().strftime('%d.%m.%Y %H:%M')}")
    return "\n".join(lines)

def format_new(new_events):
    if not new_events:
        return None
    by_cat = {}
    for e in new_events:
        by_cat.setdefault(e["category"], []).append(e)

    lines = [f"🆕 <b>НОВІ події — додались сьогодні!</b>",
             f"Кількість: <b>{len(new_events)}</b>\n"]
    for cat in sorted(by_cat):
        lines.append(f"\n{cat}")
        for e in by_cat[cat]:
            t = e["title"][:55] + ("…" if len(e["title"]) > 55 else "")
            d = e["date"][:20] if e["date"] != "травень 2026" else ""
            p = f" · {e['price'][:15]}" if e.get("price") else ""
            date_str = f"\n  📆 {d}{p}" if d or p else ""
            lines.append(f"• <a href='{e['link']}'>{t}</a>{date_str}")
    lines.append(f"\n⏰ {datetime.now().strftime('%d.%m.%Y %H:%M')}")
    return "\n".join(lines)

def format_stats(all_events, sources_stats):
    lines = ["📊 <b>Статистика збору</b>\n"]
    for name, count in sorted(sources_stats.items(), key=lambda x: -x[1]):
        icon = "✅" if count > 0 else "⚠️"
        lines.append(f"{icon} {name}: <b>{count}</b>")
    lines.append(f"\n📦 Всього: <b>{len(all_events)}</b> подій")
    lines.append(f"⏰ {datetime.now().strftime('%d.%m.%Y %H:%M')}")
    return "\n".join(lines)


# ═══════════════════════════════════════════════════════════
# ДЕДУБЛІКАЦІЯ
# ═══════════════════════════════════════════════════════════

def event_id(e):
    return hashlib.md5(f"{e['title'].lower().strip()}".encode()).hexdigest()

def deduplicate(events):
    seen = {}
    for e in events:
        eid = event_id(e)
        if eid not in seen:
            seen[eid] = e
    return list(seen.values())

def load_seen():
    if os.path.exists(SEEN_FILE):
        with open(SEEN_FILE, "r", encoding="utf-8") as f:
            return set(json.load(f))
    return set()

def save_seen(seen):
    with open(SEEN_FILE, "w", encoding="utf-8") as f:
        json.dump(list(seen), f)


# ═══════════════════════════════════════════════════════════
# ГОЛОВНА ФУНКЦІЯ
# ═══════════════════════════════════════════════════════════

def main():
    print(f"\n{'='*55}")
    print(f"  Київ — моніторинг подій травень 2026")
    print(f"  {datetime.now().strftime('%d.%m.%Y %H:%M:%S')}")
    print(f"{'='*55}\n")

    all_raw = []
    sources_stats = {}

    all_sources = (
        SOURCES["aggregators"] +
        SOURCES["theaters"] +
        SOURCES["venues"]
    )

    total = len(all_sources)
    for i, src in enumerate(all_sources, 1):
        print(f"[{i:02d}/{total}] {src['name']}")
        found = parse_page(src["url"], src["name"])
        print(f"       → {len(found)} подій")
        sources_stats[src["name"]] = len(found)
        all_raw.extend(found)
        time.sleep(0.3)  # не спамимо сервери

    # Дедублікація
    all_events = deduplicate(all_raw)
    print(f"\n✔ Всього: {len(all_raw)} → після дедублікації: {len(all_events)}")

    # Зберігаємо
    with open("all_events_may2026.json", "w", encoding="utf-8") as f:
        json.dump(all_events, f, ensure_ascii=False, indent=2)

    # Знаходимо нові
    seen = load_seen()
    new_events = []
    new_ids = set()
    for e in all_events:
        eid = event_id(e)
        if eid not in seen:
            new_events.append(e)
            new_ids.add(eid)

    print(f"🆕 Нових: {len(new_events)}")

    if not all_events:
        send_telegram(f"⚠️ Не вдалось отримати жодної події — можливо сайти тимчасово недоступні.\n⏰ {datetime.now().strftime('%d.%m.%Y %H:%M')}")
        return

    # Надсилаємо статистику збору
    send_telegram(format_stats(all_events, sources_stats))
    time.sleep(1)

    # Надсилаємо повний список
    send_long(format_full(all_events, new_ids))
    time.sleep(1)

    # Надсилаємо тільки нові (якщо є)
    if new_events:
        new_msg = format_new(new_events)
        if new_msg:
            send_long(new_msg)
        seen.update(new_ids)
        save_seen(seen)
    else:
        send_telegram(f"✅ Нових подій сьогодні не додалось.\n⏰ {datetime.now().strftime('%d.%m.%Y %H:%M')}")

    print("\n✅ Готово!")


if __name__ == "__main__":
    main()
