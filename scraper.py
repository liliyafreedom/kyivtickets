import requests
from bs4 import BeautifulSoup
import json, os, hashlib, re, time
from datetime import datetime

TELEGRAM_TOKEN = os.environ.get("TELEGRAM_TOKEN", "")
TELEGRAM_CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID", "")
SEEN_FILE = "seen_events.json"

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "uk-UA,uk;q=0.9,en;q=0.8",
    "Referer": "https://google.com",
}

# ═══════════════════════════════════════════════════════
# ФІЛЬТРИ — що викидаємо
# ═══════════════════════════════════════════════════════

GARBAGE_TITLES = [
    "sign in", "login", "create event", "allevents", "open app",
    "куди піти", "протягом тижня", "найближчі події", "для дітей в києві",
    "кіно в києві", "сьогодні", "завтра", "на цих вихі", "упссс",
    "форуми в києві", "концерти в києві", "театри в києві",
    "change city", "host control", "need help", "get the",
    "з 27", "з 28", "з 29", "з 30", "з 31",
    "open menu", "cookie", "javascript", "підпис", "реєстрац",
    "event ticket service",
]

def is_garbage(title):
    t = title.lower().strip()
    if len(t) < 4:
        return True
    if any(g in t for g in GARBAGE_TITLES):
        return True
    if re.search(r'\d{1,2}(березня|квітня|травня|червня)\d{2}:\d{2}', t):
        return True
    if t.startswith("🤔") or "упссс" in t:
        return True
    return False

# ═══════════════════════════════════════════════════════
# ФІЛЬТР ДАТИ — тільки ТРАВЕНЬ 2026
# ═══════════════════════════════════════════════════════

NOT_MAY = [
    r'\b(jan|feb|mar|apr|jun|jul|aug|sep|oct|nov|dec)\b',
    r'\b(січ|лют|бер|квіт|черв|лип|серп|вер|жовт|лист|груд)',
    r'\b(january|february|march|april|june|july|august|september|october|november|december)\b',
    r'\b0[1-4][./]\d{4}\b',   # 01-04 місяць
    r'\b0[6-9][./]\d{4}\b',   # 06-12 місяць
    r'\b1[0-2][./]\d{4}\b',
    r'apr|апр',
    r'\b(04|06|07|08|09|10|11|12)[./]2026\b',
]

MAY_PATTERNS = [
    r'\bmay\b', r'\bтрав', r'05[./]2026', r'2026-05',
    r'\b(0?[1-9]|[12]\d|3[01])\s+may\b',
    r'\bmay\s+(0?[1-9]|[12]\d|3[01])\b',
]

def is_may_event(date_str):
    if not date_str or date_str.strip() == "":
        return True
    d = date_str.lower()
    for pat in NOT_MAY:
        if re.search(pat, d):
            return False
    for pat in MAY_PATTERNS:
        if re.search(pat, d):
            return True
    if "2026" in d:
        return True
    return False

# ═══════════════════════════════════════════════════════
# ФОРМАТУВАННЯ ДАТИ — красиво
# ═══════════════════════════════════════════════════════

MONTH_MAP = {
    "jan": "січ", "feb": "лют", "mar": "бер", "apr": "квіт",
    "may": "трав", "jun": "черв", "jul": "лип", "aug": "серп",
    "sep": "вер", "oct": "жовт", "nov": "лист", "dec": "груд",
    "january": "січ", "february": "лют", "march": "бер", "april": "квіт",
    "june": "черв", "july": "лип", "august": "серп", "september": "вер",
    "october": "жовт", "november": "лист", "december": "груд",
}

DAY_MAP = {
    "mon": "пн", "tue": "вт", "wed": "ср", "thu": "чт",
    "fri": "пт", "sat": "сб", "sun": "нд",
}

def format_date(date_str):
    """Перетворює 'Sat, 16 May, 2026' → '16 трав (сб)'"""
    if not date_str:
        return ""
    d = date_str.strip()

    # Формат: "Sat, 16 May, 2026" або "16 May, 2026"
    m = re.search(r'(Mon|Tue|Wed|Thu|Fri|Sat|Sun)?,?\s*(\d{1,2})\s+(\w+),?\s*(\d{4})', d, re.I)
    if m:
        day_name = m.group(1).lower()[:3] if m.group(1) else ""
        day_num = m.group(2)
        month_raw = m.group(3).lower()[:3]
        month_ua = MONTH_MAP.get(month_raw, month_raw)
        day_ua = DAY_MAP.get(day_name, "")
        day_part = f" ({day_ua})" if day_ua else ""
        return f"{day_num} {month_ua}{day_part}"

    # Формат: "2026-05-16"
    m2 = re.search(r'2026-(\d{2})-(\d{2})', d)
    if m2:
        months = ["","січ","лют","бер","квіт","трав","черв","лип","серп","вер","жовт","лист","груд"]
        mon = int(m2.group(1))
        day = int(m2.group(2))
        return f"{day} {months[mon] if mon <= 12 else m2.group(1)}"

    return d[:20]

# ═══════════════════════════════════════════════════════
# КАТЕГОРИЗАЦІЯ
# ═══════════════════════════════════════════════════════

CATEGORIES = {
    "🎵 Концерти": [
        "концерт", "concert", "джаз", "jazz", "рок", "rock", "поп", "реп",
        "rap", "live", "виступ", "гурт", "симфон", "symphony", "органн",
        "філармон", "бумбокс", "dzidzio", "onuka", "sadsvit", "tik tu",
        "jerry heil", "vivienne", "laud", "kozak system", "бах", "bach",
        "брамс", "brahms", "дворжак", "шуберт", "шуман", "вебер",
        "серенад", "ave maria", "телеман", "sanctus", "страсті",
        "класика", "музик", "the unsleeping", "miyazaki",
    ],
    "🎭 Театр і вистави": [
        "театр", "theatre", "theater", "вистав", "спектакл", "опер",
        "opera", "балет", "ballet", "мюзикл", "musical", "прем'єр",
        "драм", "dakh daughters", "перформанс", "performance", "франка",
    ],
    "🎤 Стендап і зйомки": [
        "зйомк", "стендап", "stand-up", "standup", "гумор", "comedy",
        "квартал", "дизель", "розгон", "фактично самі",
    ],
    "🎪 Фестивалі": [
        "фестивал", "fest", "festival", "open-air", "маркет",
        "великодн", "easter", "miyazaki day",
    ],
    "🖼 Виставки і форуми": [
        "виставк", "exhibition", "expo", "форум", "forum", "конгрес",
        "конференц", "congress", "дискусія", "meeting", "incrypted",
        "solar", "heatup", "mining", "hr-директор",
    ],
    "🏃 Спорт і забіги": [
        "марафон", "marathon", "забіг", "spartan", "пробіг", "трейл",
        "trail", "race", "run", "чорнобил",
    ],
    "💃 Танці і вечірки": [
        "танц", "dance", "party", "вечірк", "tango", "salsa", "bachata",
        "kizomba", "zouk", "щоп'ятниці",
    ],
    "👶 Дітям": [
        "дітям", "дитяч", "children", "kids", "казк", "ляльк", "puppet",
    ],
    "💼 Бізнес і IT": [
        "бізнес", "business", "dou day", "tech", "startup", "invest",
        "crypto", "stem-освіта", "тренінг", "конструктор компетент",
        "usubc",
    ],
    "🎬 Кіно": [
        "кіно", "film", "cinema", "movie", "українське кіно",
    ],
    "🚶 Екскурсії і прогулянки": [
        "прогулянк", "екскурс", "walk", "tour", "музей", "церква",
        "андріївськ", "софія", "великдень у",
    ],
}

def detect_category(title):
    t = title.lower()
    for cat, kws in CATEGORIES.items():
        if any(k in t for k in kws):
            return cat
    return "📅 Інші події"

# ═══════════════════════════════════════════════════════
# ПАРСЕРИ
# ═══════════════════════════════════════════════════════

def scrape_allevents_category(url, label):
    events = []
    try:
        s = requests.Session()
        s.headers.update(HEADERS)
        r = s.get(url, timeout=25)
        soup = BeautifulSoup(r.text, "html.parser")

        for li in soup.select("li"):
            link_el = li.select_one("a[href*='/kiev/']")
            if not link_el:
                continue
            title = link_el.get_text(strip=True)
            if is_garbage(title) or len(title) < 4 or len(title) > 200:
                continue

            block_text = li.get_text(" ", strip=True)
            date = ""
            m = re.search(r'(Mon|Tue|Wed|Thu|Fri|Sat|Sun),?\s+\d{1,2}\s+\w+,?\s+\d{4}', block_text)
            if m:
                date = m.group(0)
            else:
                m2 = re.search(r'\d{1,2}\s+(Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)\w*\s+\d{4}', block_text)
                if m2:
                    date = m2.group(0)

            if not is_may_event(date):
                continue

            # Місце — перший короткий рядок що не є датою і не заголовком
            venue = ""
            for el in li.select("p, span"):
                txt = el.get_text(strip=True)
                if 3 < len(txt) < 70 and txt.lower() != title.lower():
                    if not re.search(r'(Mon|Tue|Wed|Thu|Fri|Sat|Sun)', txt):
                        if not re.search(r'\d+\s+interested', txt.lower()):
                            venue = txt
                            break

            href = link_el.get("href", "")
            link = href if href.startswith("http") else "https://allevents.in" + href

            events.append({
                "title": title, "date": date, "venue": venue[:55],
                "price": "", "link": link,
                "source": f"allevents.in", "category": detect_category(title),
            })
    except Exception as e:
        print(f"  allevents/{label}: {e}")
    return events


def scrape_allevents_all():
    all_events = []
    cats = [
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
        ("business",     "https://allevents.in/kiev-ua/business"),
    ]
    for label, url in cats:
        found = scrape_allevents_category(url, label)
        print(f"   allevents/{label}: {len(found)}")
        all_events.extend(found)
        time.sleep(1)
    return all_events


def scrape_ticketsbox():
    events = []
    try:
        s = requests.Session()
        s.headers.update(HEADERS)
        r = s.get("https://kyiv.ticketsbox.com/may/", timeout=20)
        soup = BeautifulSoup(r.text, "html.parser")
        for item in soup.select(".event-item, .b-events__item, article, [class*='event'], li.item")[:80]:
            title_el = item.select_one("h3, h2, h4, [class*='title'], [class*='name']")
            date_el  = item.select_one("time, [class*='date']")
            link_el  = item.select_one("a[href]")
            price_el = item.select_one("[class*='price']")
            if not title_el: continue
            title = title_el.get_text(strip=True)
            if is_garbage(title) or len(title) < 4: continue
            date = date_el.get_text(strip=True)[:40] if date_el else ""
            if not is_may_event(date): continue
            price = price_el.get_text(strip=True)[:25] if price_el else ""
            href = link_el["href"] if link_el else ""
            link = ("https://kyiv.ticketsbox.com" + href) if href.startswith("/") else href or "https://kyiv.ticketsbox.com"
            events.append({"title": title, "date": date, "venue": "", "price": price,
                            "link": link, "source": "ticketsbox.com", "category": detect_category(title)})
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
        for item in soup.select("article, .event, [class*='event'], li, [class*='card']")[:50]:
            title_el = item.select_one("h3, h2, h4, [class*='title'], [class*='name']")
            date_el  = item.select_one("time, [class*='date']")
            link_el  = item.select_one("a[href]")
            if not title_el: continue
            title = title_el.get_text(strip=True)
            if is_garbage(title) or len(title) < 4: continue
            date = date_el.get_text(strip=True)[:40] if date_el else ""
            if not is_may_event(date): continue
            href = link_el["href"] if link_el else ""
            link = ("https://originstage.com.ua" + href) if href.startswith("/") else href or "https://originstage.com.ua"
            events.append({"title": title, "date": date, "venue": "ORIGIN STAGE", "price": "",
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
        for item in soup.select(".b-afisha__item, [class*='afisha'], [class*='performance'], article, li")[:60]:
            title_el = item.select_one("h3, h2, h4, [class*='title'], [class*='name']")
            date_el  = item.select_one("time, [class*='date'], [class*='day']")
            link_el  = item.select_one("a[href]")
            if not title_el: continue
            title = title_el.get_text(strip=True)
            if is_garbage(title) or len(title) < 4: continue
            date = date_el.get_text(strip=True)[:40] if date_el else ""
            if not is_may_event(date): continue
            href = link_el["href"] if link_el else ""
            link = ("https://opera.com.ua" + href) if href.startswith("/") else href or "https://opera.com.ua/afisha"
            events.append({"title": title, "date": date, "venue": "Опера Шевченка", "price": "",
                            "link": link, "source": "opera.com.ua", "category": "🎭 Театр і вистави"})
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
        for item in soup.select("article, .performance, [class*='afisha'], li")[:60]:
            title_el = item.select_one("h3, h2, h4, [class*='title'], [class*='name']")
            date_el  = item.select_one("time, [class*='date']")
            link_el  = item.select_one("a[href]")
            if not title_el: continue
            title = title_el.get_text(strip=True)
            if is_garbage(title) or len(title) < 4: continue
            date = date_el.get_text(strip=True)[:40] if date_el else ""
            if not is_may_event(date): continue
            href = link_el["href"] if link_el else ""
            link = ("https://molodyytheatre.com" + href) if href.startswith("/") else href or "https://molodyytheatre.com"
            events.append({"title": title, "date": date, "venue": "Молодий театр", "price": "",
                            "link": link, "source": "molodyytheatre.com", "category": "🎭 Театр і вистави"})
    except Exception as e:
        print(f"  molody: {e}")
    return events


# ═══════════════════════════════════════════════════════
# TELEGRAM
# ═══════════════════════════════════════════════════════

def send_telegram(message):
    if not TELEGRAM_TOKEN or not TELEGRAM_CHAT_ID:
        print(message); return False
    try:
        r = requests.post(
            f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage",
            json={"chat_id": TELEGRAM_CHAT_ID, "text": message,
                  "parse_mode": "HTML", "disable_web_page_preview": True},
            timeout=15
        )
        r.raise_for_status(); return True
    except Exception as e:
        print(f"Telegram: {e}"); return False

def send_long(text):
    """Розбиває на частини і надсилає"""
    max_len = 3800
    while len(text) > max_len:
        cut = text.rfind("\n\n", 0, max_len)
        if cut == -1:
            cut = text.rfind("\n", 0, max_len)
        if cut == -1:
            cut = max_len
        send_telegram(text[:cut])
        text = text[cut:].lstrip()
        time.sleep(0.8)
    if text.strip():
        send_telegram(text)

# ═══════════════════════════════════════════════════════
# ДЕДУБЛІКАЦІЯ
# ═══════════════════════════════════════════════════════

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

# ═══════════════════════════════════════════════════════
# КРАСИВЕ ФОРМАТУВАННЯ
# ═══════════════════════════════════════════════════════

def format_event_card(e, is_new=False):
    """Одна подія — красива картка"""
    title = e["title"][:60] + ("…" if len(e["title"]) > 60 else "")
    new_badge = "🆕 " if is_new else ""

    # Рядок з деталями
    details = []
    date_fmt = format_date(e.get("date", ""))
    if date_fmt:
        details.append(f"📅 {date_fmt}")
    if e.get("venue"):
        details.append(f"📍 {e['venue'][:40]}")
    if e.get("price"):
        details.append(f"💰 {e['price'][:20]}")

    line1 = f"{new_badge}🎟 <a href='{e['link']}'><b>{title}</b></a>"
    line2 = "   " + "  ·  ".join(details) if details else ""

    return line1 + ("\n" + line2 if line2 else "")


def format_category_block(cat, events, new_ids):
    """Блок однієї категорії"""
    lines = []
    lines.append(f"\n{cat} — <b>{len(events)}</b>")
    lines.append("┄" * 20)
    for e in events:
        lines.append(format_event_card(e, is_new=event_id(e) in new_ids))
    return "\n".join(lines)


def build_full_message(all_events, new_ids):
    """Повне повідомлення по категоріях"""
    by_cat = {}
    for e in all_events:
        by_cat.setdefault(e["category"], []).append(e)

    # Сортуємо події всередині категорії по даті
    def sort_key(e):
        d = e.get("date", "")
        m = re.search(r'(\d{1,2})\s+(May|трав)', d, re.I)
        return int(m.group(1)) if m else 99

    messages = []
    current = f"📋 <b>Київ · Травень 2026</b>\n🗓 Всього: <b>{len(all_events)}</b> подій\n"

    for cat in sorted(by_cat):
        evts = sorted(by_cat[cat], key=sort_key)
        block = format_category_block(cat, evts, new_ids)

        if len(current) + len(block) > 3800:
            messages.append(current)
            current = block
        else:
            current += block

    current += f"\n\n🆕 = нова сьогодні  ·  ⏰ {datetime.now().strftime('%d.%m %H:%M')}"
    messages.append(current)
    return messages


def build_new_message(new_events):
    """Повідомлення тільки про нові події"""
    if not new_events:
        return []

    by_cat = {}
    for e in new_events:
        by_cat.setdefault(e["category"], []).append(e)

    header = f"🆕 <b>Нові події — з'явились сьогодні!</b>\nКількість: <b>{len(new_events)}</b>\n"
    messages = []
    current = header

    for cat in sorted(by_cat):
        lines = [f"\n{cat}"]
        lines.append("┄" * 20)
        for e in by_cat[cat]:
            lines.append(format_event_card(e, is_new=True))
        block = "\n".join(lines)

        if len(current) + len(block) > 3800:
            messages.append(current)
            current = block
        else:
            current += block

    current += f"\n\n⏰ {datetime.now().strftime('%d.%m.%Y %H:%M')}"
    messages.append(current)
    return messages


def build_stats_message(stats, total):
    lines = [
        "📊 <b>Статистика збору</b>",
        f"📅 Київ · Травень 2026\n",
    ]
    for name, count in sorted(stats.items(), key=lambda x: -x[1]):
        bar = "▓" * min(count, 10) + "░" * max(0, 10 - min(count, 10))
        icon = "✅" if count > 0 else "⚠️"
        lines.append(f"{icon} {bar} {count}  <i>{name}</i>")
    lines.append(f"\n📦 Унікальних: <b>{total}</b>")
    lines.append(f"⏰ {datetime.now().strftime('%d.%m.%Y %H:%M')}")
    return "\n".join(lines)

# ═══════════════════════════════════════════════════════
# ГОЛОВНА
# ═══════════════════════════════════════════════════════

def main():
    print(f"\n{'='*55}")
    print(f"  Kyiv Events — {datetime.now().strftime('%d.%m.%Y %H:%M')}")
    print(f"{'='*55}\n")

    all_raw = []
    stats = {}

    print("→ allevents.in...")
    ae = scrape_allevents_all()
    stats["allevents.in"] = len(ae)
    all_raw.extend(ae)

    others = [
        ("ticketsbox.com",     scrape_ticketsbox),
        ("originstage.com.ua", scrape_origin_stage),
        ("opera.com.ua",       scrape_opera),
        ("molodyytheatre.com", scrape_molody),
    ]
    for name, fn in others:
        print(f"→ {name}...")
        found = fn()
        print(f"   {len(found)}")
        stats[name] = len(found)
        all_raw.extend(found)
        time.sleep(0.5)

    all_events = deduplicate(all_raw)
    print(f"\n✔ Унікальних: {len(all_events)}")

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

    # 1. Статистика
    send_telegram(build_stats_message(stats, len(all_events)))
    time.sleep(1)

    # 2. Повний список по категоріях
    for msg in build_full_message(all_events, new_ids):
        send_telegram(msg)
        time.sleep(0.8)

    # 3. Тільки нові
    if new_events:
        for msg in build_new_message(new_events):
            send_telegram(msg)
            time.sleep(0.8)
        seen.update(new_ids)
        save_seen(seen)
    else:
        send_telegram(f"✅ Нових подій сьогодні не додалось.\n⏰ {datetime.now().strftime('%d.%m.%Y %H:%M')}")

    print("✅ Готово!")

if __name__ == "__main__":
    main()
