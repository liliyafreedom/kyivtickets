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

# ═══════════════════════════════════════════════════════════
# КАТЕГОРИЗАЦІЯ
# ═══════════════════════════════════════════════════════════

CATEGORY_MAP = {
    "🎵 Концерт":          ["концерт", "музик", "джаз", "рок", "поп", "реп", "live", "виступ", "тур", "гурт", "симфон", "органн", "філармон", "orchestra", "concert"],
    "🎭 Театр / Вистава":  ["театр", "вистав", "спектакл", "опер", "балет", "мюзикл", "прем'єр", "драм", "comedy play", "performance", "show"],
    "🎤 Стендап / Зйомка": ["зйомк", "стендап", "stand-up", "гумор", "квартал", "дизель", "розгон", "comedy"],
    "🎪 Фестиваль":        ["фестивал", "fest", "festival", "open-air", "опенейр"],
    "🖼 Виставка":         ["виставк", "галере", "музей", "exposition", "exhibition", "expo"],
    "🎬 Шоу / Кіно":       ["шоу", "show", "кіно", "фільм", "цирк", "circus"],
    "👶 Дітям":            ["дітям", "дитяч", "казк", "ляльк", "puppet", "children"],
    "🏃 Спорт":            ["марафон", "забіг", "spartan", "спорт", "турнір", "змаган"],
}

def detect_category(title):
    t = title.lower()
    for cat, kws in CATEGORY_MAP.items():
        if any(k in t for k in kws):
            return cat
    return "📅 Подія"


# ═══════════════════════════════════════════════════════════
# ПАРСЕРИ — ТІЛЬКИ САЙТИ З СТАТИЧНИМ HTML
# ═══════════════════════════════════════════════════════════

def scrape_allevents():
    """allevents.in — агрегатор з статичним HTML, парсить Facebook Events та інші"""
    events = []
    urls = [
        "https://allevents.in/kiev-ua/all#",
        "https://allevents.in/kiev-ua/concerts",
        "https://allevents.in/kiev-ua/theatre",
        "https://allevents.in/kiev-ua/comedy",
        "https://allevents.in/kiev-ua/festivals",
        "https://allevents.in/kiev-ua/art",
    ]
    try:
        s = requests.Session()
        s.headers.update(HEADERS)
        for url in urls:
            r = s.get(url, timeout=20)
            soup = BeautifulSoup(r.text, "html.parser")
            for item in soup.select(".event-item, .event-card, [class*='event'], article, li.item")[:40]:
                title_el = item.select_one("h3, h2, h4, [class*='title'], [class*='name']")
                date_el  = item.select_one("time, [class*='date'], [class*='time']")
                link_el  = item.select_one("a[href]")
                if not title_el: continue
                title = title_el.get_text(strip=True)
                if len(title) < 3: continue
                date = date_el.get_text(strip=True)[:40] if date_el else ""
                # Фільтр по травню
                if date and not any(x in date.lower() for x in ["may", "трав", "05/", "/05", "05."]):
                    if "2026" not in date and date:
                        continue
                href = link_el["href"] if link_el else url
                link = href if href.startswith("http") else "https://allevents.in" + href
                events.append({"title": title, "date": date, "price": "",
                                "link": link, "source": "allevents.in",
                                "category": detect_category(title)})
            time.sleep(0.5)
    except Exception as e:
        print(f"  allevents.in: {e}")
    return events


def scrape_eventbrite():
    """Eventbrite — великий міжнародний агрегатор"""
    events = []
    urls = [
        "https://www.eventbrite.com/d/ukraine--kyiv/events--in-may-2026/",
        "https://www.eventbrite.com/d/ukraine--kyiv/concerts--in-may-2026/",
        "https://www.eventbrite.com/d/ukraine--kyiv/performing-arts--in-may-2026/",
    ]
    try:
        s = requests.Session()
        s.headers.update(HEADERS)
        for url in urls:
            r = s.get(url, timeout=20)
            soup = BeautifulSoup(r.text, "html.parser")
            for item in soup.select("[data-testid='event-card'], .eds-event-card, article, [class*='event-card']")[:30]:
                title_el = item.select_one("h3, h2, [class*='title'], [data-testid='event-card-title']")
                date_el  = item.select_one("time, [class*='date'], [data-testid*='date']")
                link_el  = item.select_one("a[href]")
                if not title_el: continue
                title = title_el.get_text(strip=True)
                if len(title) < 3: continue
                date = date_el.get_text(strip=True)[:40] if date_el else ""
                href = link_el["href"] if link_el else url
                link = href if href.startswith("http") else "https://www.eventbrite.com" + href
                events.append({"title": title, "date": date, "price": "",
                                "link": link, "source": "eventbrite.com",
                                "category": detect_category(title)})
            time.sleep(0.5)
    except Exception as e:
        print(f"  eventbrite: {e}")
    return events


def scrape_kyiv_opera():
    """Опера Шевченка — офіційний сайт, статичний HTML"""
    events = []
    try:
        s = requests.Session()
        s.headers.update(HEADERS)
        r = s.get("https://opera.com.ua/afisha", timeout=20)
        soup = BeautifulSoup(r.text, "html.parser")
        for item in soup.select(".b-afisha__item, .afisha-item, [class*='afisha'], [class*='performance'], article, li")[:50]:
            title_el = item.select_one("h3, h2, h4, [class*='title'], [class*='name']")
            date_el  = item.select_one("time, [class*='date'], [class*='day']")
            link_el  = item.select_one("a[href]")
            if not title_el: continue
            title = title_el.get_text(strip=True)
            if len(title) < 3 or len(title) > 150: continue
            date = date_el.get_text(strip=True)[:30] if date_el else ""
            href = link_el["href"] if link_el else ""
            link = ("https://opera.com.ua" + href) if href.startswith("/") else href or "https://opera.com.ua/afisha"
            events.append({"title": title, "date": date, "price": "",
                            "link": link, "source": "opera.com.ua (Опера Шевченка)",
                            "category": "🎭 Театр / Вистава"})
    except Exception as e:
        print(f"  opera.com.ua: {e}")
    return events


def scrape_molody_theatre():
    """Молодий театр"""
    events = []
    try:
        s = requests.Session()
        s.headers.update(HEADERS)
        r = s.get("https://molodyytheatre.com/afisha", timeout=20)
        soup = BeautifulSoup(r.text, "html.parser")
        for item in soup.select("article, .performance, .event, [class*='afisha'], li, [class*='item']")[:50]:
            title_el = item.select_one("h3, h2, h4, [class*='title'], [class*='name']")
            date_el  = item.select_one("time, [class*='date']")
            link_el  = item.select_one("a[href]")
            if not title_el: continue
            title = title_el.get_text(strip=True)
            if len(title) < 3 or len(title) > 150: continue
            date = date_el.get_text(strip=True)[:30] if date_el else ""
            href = link_el["href"] if link_el else ""
            link = ("https://molodyytheatre.com" + href) if href.startswith("/") else href or "https://molodyytheatre.com/afisha"
            events.append({"title": title, "date": date, "price": "",
                            "link": link, "source": "molodyytheatre.com",
                            "category": "🎭 Театр / Вистава"})
    except Exception as e:
        print(f"  molodyytheatre.com: {e}")
    return events


def scrape_ticketsbox_api():
    """TicketsBox — спробуємо їхній JSON endpoint"""
    events = []
    try:
        s = requests.Session()
        s.headers.update({**HEADERS, "Accept": "application/json"})
        # Пробуємо різні API endpoints
        api_urls = [
            "https://kyiv.ticketsbox.com/api/events?month=5&year=2026&per_page=100",
            "https://kyiv.ticketsbox.com/api/v1/events?city=kyiv&date_from=2026-05-01&date_to=2026-05-31",
            "https://api.ticketsbox.com/events?city=kyiv&from=2026-05-01&to=2026-05-31",
        ]
        for api_url in api_urls:
            try:
                r = s.get(api_url, timeout=15)
                if r.status_code == 200 and "json" in r.headers.get("content-type", ""):
                    data = r.json()
                    items = data if isinstance(data, list) else data.get("data", data.get("events", []))
                    for item in items[:100]:
                        title = item.get("title") or item.get("name", "")
                        date  = str(item.get("date") or item.get("start_date", ""))[:30]
                        link  = item.get("url") or item.get("link", "https://kyiv.ticketsbox.com")
                        price = str(item.get("min_price") or item.get("price", ""))
                        if title and len(title) > 2:
                            events.append({"title": title, "date": date, "price": price,
                                            "link": link, "source": "ticketsbox.com",
                                            "category": detect_category(title)})
                    if events:
                        break
            except:
                continue

        # Fallback HTML
        if not events:
            s.headers.update(HEADERS)
            for url in ["https://kyiv.ticketsbox.com/may/", "https://kyiv.ticketsbox.com/"]:
                r = s.get(url, timeout=20)
                soup = BeautifulSoup(r.text, "html.parser")
                for item in soup.select(".event-item, .b-events__item, [class*='event'], article, .item")[:60]:
                    title_el = item.select_one("h3, h2, h4, [class*='title'], [class*='name']")
                    date_el  = item.select_one("time, [class*='date']")
                    link_el  = item.select_one("a[href]")
                    if not title_el: continue
                    title = title_el.get_text(strip=True)
                    if len(title) < 3: continue
                    date = date_el.get_text(strip=True)[:30] if date_el else ""
                    href = link_el["href"] if link_el else ""
                    link = ("https://kyiv.ticketsbox.com" + href) if href.startswith("/") else href or "https://kyiv.ticketsbox.com"
                    price_el = item.select_one("[class*='price']")
                    price = price_el.get_text(strip=True)[:20] if price_el else ""
                    events.append({"title": title, "date": date, "price": price,
                                    "link": link, "source": "ticketsbox.com",
                                    "category": detect_category(title)})
    except Exception as e:
        print(f"  ticketsbox: {e}")
    return events


def scrape_karabas_may():
    """Karabas — пряма сторінка травня"""
    events = []
    try:
        s = requests.Session()
        s.headers.update(HEADERS)
        for url in [
            "https://kyiv.karabas.com/may/",
            "https://karabas.com/ua/kyiv/may/",
        ]:
            r = s.get(url, timeout=20)
            soup = BeautifulSoup(r.text, "html.parser")
            # Karabas використовує специфічні класи
            for item in soup.select(".b-event-tile, .event-tile, .event__item, [class*='EventTile'], [class*='event-tile'], [class*='poster']")[:80]:
                title_el = item.select_one("h3, h2, h4, .event-tile__title, [class*='title']")
                date_el  = item.select_one(".event-tile__date, [class*='date'], time")
                link_el  = item.select_one("a[href]")
                price_el = item.select_one("[class*='price']")
                if not title_el: continue
                title = title_el.get_text(strip=True)
                if len(title) < 3: continue
                date = date_el.get_text(strip=True)[:30] if date_el else ""
                price = price_el.get_text(strip=True)[:20] if price_el else ""
                href = link_el["href"] if link_el else ""
                link = ("https://kyiv.karabas.com" + href) if href.startswith("/") else href or "https://kyiv.karabas.com"
                events.append({"title": title, "date": date, "price": price,
                                "link": link, "source": "karabas.com",
                                "category": detect_category(title)})
            if events:
                break
    except Exception as e:
        print(f"  karabas: {e}")
    return events


def scrape_origin_stage():
    """ORIGIN STAGE — популярний майданчик"""
    events = []
    try:
        s = requests.Session()
        s.headers.update(HEADERS)
        for url in ["https://originstage.com.ua/events/", "https://originstage.com.ua/"]:
            r = s.get(url, timeout=20)
            soup = BeautifulSoup(r.text, "html.parser")
            for item in soup.select("article, .event, [class*='event'], [class*='show'], li")[:40]:
                title_el = item.select_one("h3, h2, h4, [class*='title'], [class*='name']")
                date_el  = item.select_one("time, [class*='date']")
                link_el  = item.select_one("a[href]")
                if not title_el: continue
                title = title_el.get_text(strip=True)
                if len(title) < 3: continue
                date = date_el.get_text(strip=True)[:30] if date_el else ""
                href = link_el["href"] if link_el else ""
                link = ("https://originstage.com.ua" + href) if href.startswith("/") else href or "https://originstage.com.ua"
                events.append({"title": title, "date": date, "price": "",
                                "link": link, "source": "ORIGIN STAGE",
                                "category": detect_category(title)})
            if events: break
    except Exception as e:
        print(f"  originstage: {e}")
    return events


def scrape_kontramarka_may():
    """Kontramarka — сторінка травня"""
    events = []
    try:
        s = requests.Session()
        s.headers.update(HEADERS)
        r = s.get("https://kontramarka.ua/uk/kyiv/?month=5&year=2026", timeout=20)
        soup = BeautifulSoup(r.text, "html.parser")
        for item in soup.select(".event-card, .b-event, [class*='EventCard'], [class*='event'], article")[:80]:
            title_el = item.select_one("h3, h2, h4, [class*='title'], [class*='name']")
            date_el  = item.select_one("time, [class*='date']")
            link_el  = item.select_one("a[href]")
            price_el = item.select_one("[class*='price']")
            if not title_el: continue
            title = title_el.get_text(strip=True)
            if len(title) < 3: continue
            date = date_el.get_text(strip=True)[:30] if date_el else ""
            price = price_el.get_text(strip=True)[:20] if price_el else ""
            href = link_el["href"] if link_el else ""
            link = ("https://kontramarka.ua" + href) if href.startswith("/") else href or "https://kontramarka.ua"
            events.append({"title": title, "date": date, "price": price,
                            "link": link, "source": "kontramarka.ua",
                            "category": detect_category(title)})
    except Exception as e:
        print(f"  kontramarka: {e}")
    return events


def scrape_concert_ua_rss():
    """Concert.ua — пробуємо RSS або sitemap"""
    events = []
    try:
        s = requests.Session()
        s.headers.update(HEADERS)
        # Concert.ua має XML sitemap з подіями
        for url in [
            "https://concert.ua/sitemap_events.xml",
            "https://concert.ua/rss/events/kyiv",
            "https://concert.ua/ua/catalog/kyiv/all-categories.json",
        ]:
            try:
                r = s.get(url, timeout=15)
                if r.status_code != 200:
                    continue
                ct = r.headers.get("content-type", "")
                if "xml" in ct:
                    soup = BeautifulSoup(r.text, "xml")
                    for item in soup.select("item, url")[:200]:
                        title_el = item.find("title")
                        link_el  = item.find("link") or item.find("loc")
                        date_el  = item.find("pubDate") or item.find("lastmod")
                        if not title_el: continue
                        title = title_el.get_text(strip=True)
                        if "kyiv" not in title.lower() and "київ" not in title.lower():
                            loc = link_el.get_text() if link_el else ""
                            if "kyiv" not in loc.lower():
                                continue
                        date = date_el.get_text(strip=True)[:30] if date_el else ""
                        link = link_el.get_text(strip=True) if link_el else "https://concert.ua"
                        if len(title) > 3:
                            events.append({"title": title, "date": date, "price": "",
                                            "link": link, "source": "concert.ua",
                                            "category": detect_category(title)})
                    if events: break
                elif "json" in ct:
                    data = r.json()
                    items = data if isinstance(data, list) else data.get("data", data.get("events", []))
                    for item in items:
                        title = item.get("title") or item.get("name", "")
                        if title and len(title) > 2:
                            events.append({"title": title,
                                            "date": str(item.get("date", ""))[:30],
                                            "price": str(item.get("min_price", "")),
                                            "link": item.get("url", "https://concert.ua"),
                                            "source": "concert.ua",
                                            "category": detect_category(title)})
                    if events: break
            except:
                continue
    except Exception as e:
        print(f"  concert.ua rss/xml: {e}")
    return events


def scrape_kyiv_city_events():
    """Офіційний сайт Києва — міські події"""
    events = []
    try:
        s = requests.Session()
        s.headers.update(HEADERS)
        r = s.get("https://kyivcity.gov.ua/news/category/events/", timeout=20)
        soup = BeautifulSoup(r.text, "html.parser")
        for item in soup.select("article, .news-item, [class*='event'], [class*='news'], li.item")[:30]:
            title_el = item.select_one("h3, h2, h4, [class*='title']")
            date_el  = item.select_one("time, [class*='date']")
            link_el  = item.select_one("a[href]")
            if not title_el: continue
            title = title_el.get_text(strip=True)
            if len(title) < 3: continue
            date = date_el.get_text(strip=True)[:30] if date_el else ""
            href = link_el["href"] if link_el else ""
            link = ("https://kyivcity.gov.ua" + href) if href.startswith("/") else href or "https://kyivcity.gov.ua"
            events.append({"title": title, "date": date, "price": "безкоштовно",
                            "link": link, "source": "kyivcity.gov.ua",
                            "category": detect_category(title)})
    except Exception as e:
        print(f"  kyivcity.gov.ua: {e}")
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
    parts = []
    while len(text) > max_len:
        cut = text.rfind("\n", 0, max_len)
        if cut == -1: cut = max_len
        parts.append(text[:cut])
        text = text[cut:]
    parts.append(text)
    for part in parts:
        send_telegram(part)
        time.sleep(0.5)


# ═══════════════════════════════════════════════════════════
# ДЕДУБЛІКАЦІЯ + ЗБЕРЕЖЕННЯ
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
    lines = ["📊 <b>Статистика збору — Київ травень 2026</b>\n"]
    for name, count in sorted(stats.items(), key=lambda x: -x[1]):
        icon = "✅" if count > 0 else "⚠️"
        lines.append(f"{icon} {name}: <b>{count}</b>")
    lines.append(f"\n📦 Разом унікальних: <b>{total}</b>")
    lines.append(f"⏰ {datetime.now().strftime('%d.%m.%Y %H:%M')}")
    return "\n".join(lines)

def format_full(events, new_ids):
    by_cat = {}
    for e in events:
        by_cat.setdefault(e["category"], []).append(e)

    lines = [f"📋 <b>УСІ події — Київ, травень 2026</b>",
             f"Всього: <b>{len(events)}</b> подій\n"]
    for cat in sorted(by_cat):
        evts = by_cat[cat]
        lines.append(f"\n{cat} — {len(evts)} шт.")
        for e in evts:
            is_new = "🆕 " if event_id(e) in new_ids else ""
            t = e["title"][:55] + ("…" if len(e["title"]) > 55 else "")
            d = e["date"][:20] if e.get("date") and e["date"] not in ("", "травень 2026") else ""
            p = f" · {e['price'][:15]}" if e.get("price") else ""
            suffix = f"\n  📆 {d}{p}" if d or p else ""
            lines.append(f"{is_new}• <a href='{e['link']}'>{t}</a>{suffix}")
    lines.append(f"\n🆕 = з'явилось сьогодні  |  ⏰ {datetime.now().strftime('%d.%m.%Y %H:%M')}")
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
            d = e["date"][:20] if e.get("date") else ""
            p = f" · {e['price'][:15]}" if e.get("price") else ""
            suffix = f"\n  📆 {d}{p}" if d or p else ""
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

    scrapers = [
        ("allevents.in",       scrape_allevents),
        ("eventbrite.com",     scrape_eventbrite),
        ("ticketsbox.com",     scrape_ticketsbox_api),
        ("karabas.com",        scrape_karabas_may),
        ("kontramarka.ua",     scrape_kontramarka_may),
        ("concert.ua",         scrape_concert_ua_rss),
        ("originstage.com.ua", scrape_origin_stage),
        ("opera.com.ua",       scrape_kyiv_opera),
        ("molodyytheatre.com", scrape_molody_theatre),
        ("kyivcity.gov.ua",    scrape_kyiv_city_events),
    ]

    all_raw = []
    stats = {}

    for name, fn in scrapers:
        print(f"  → {name}...")
        found = fn()
        print(f"     {len(found)} подій")
        stats[name] = len(found)
        all_raw.extend(found)
        time.sleep(0.3)

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
        send_telegram(f"⚠️ Жодного результату — сайти недоступні.\n⏰ {datetime.now().strftime('%d.%m.%Y %H:%M')}")
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
