"""
Friday Web Tools
Search, weather, page fetch, stocks, wiki, calculator, currency, QR, API tester
"""

import re
import json
import math
from typing import Optional
from dataclasses import dataclass

@dataclass
class R:
    ok:  bool
    out: str
    cmd: str = ""


def _req(url, params=None, headers=None, method="GET", body=None, timeout=12):
    try:
        import requests
        h = {"User-Agent": "FridayAI/1.0"}
        if headers: h.update(headers)
        if method == "GET":
            r = requests.get(url, params=params, headers=h, timeout=timeout)
        elif method == "POST":
            r = requests.post(url, params=params, headers=h, json=body, timeout=timeout)
        else:
            r = requests.request(method, url, params=params, headers=h, json=body, timeout=timeout)
        r.raise_for_status()
        return True, r
    except Exception as e:
        return False, str(e)


def web_search(query, max_results=6):
    try:
        from duckduckgo_search import DDGS
        with DDGS() as d:
            results = list(d.text(query, max_results=max_results))
        if not results: return R(False, "No results", "ddg")
        lines = [f"🔍 {query}\n"]
        for i, r in enumerate(results, 1):
            lines.append(f"{i}. {r.get('title','')}")
            lines.append(f"   {r.get('href','')}")
            lines.append(f"   {r.get('body','')[:200]}\n")
        return R(True, "\n".join(lines), "ddg_search")
    except Exception as e:
        return R(False, f"Search error: {e}", "ddg")


def fetch_page(url, summarize=False):
    ok, r = _req(url)
    if not ok: return R(False, f"Fetch error: {r}", url)
    try:
        from bs4 import BeautifulSoup
        import html2text
        soup = BeautifulSoup(r.text, "html.parser")
        for tag in soup(["script","style","nav","footer","aside","header"]):
            tag.decompose()
        h = html2text.HTML2Text()
        h.ignore_links = False; h.ignore_images = True
        text = h.handle(str(soup))
        text = re.sub(r"\n{3,}", "\n\n", text).strip()
        if len(text) > 8000: text = text[:8000] + f"\n\n[truncated — {len(text)} chars total]"
        return R(True, f"📄 {url}\n\n{text}", url)
    except Exception as e:
        return R(False, str(e), url)


def get_weather(location):
    ok, r = _req("https://nominatim.openstreetmap.org/search",
                 params={"q": location, "format": "json", "limit": 1})
    if not ok or not r.json(): return R(False, f"Cannot geocode '{location}'", "weather")
    geo = r.json()[0]
    lat, lon, city = geo["lat"], geo["lon"], geo.get("display_name","?").split(",")[0]

    ok2, r2 = _req("https://api.open-meteo.com/v1/forecast", params={
        "latitude": lat, "longitude": lon, "current_weather": True,
        "daily": "temperature_2m_max,temperature_2m_min,precipitation_sum,weathercode",
        "forecast_days": 5, "timezone": "auto",
    })
    if not ok2: return R(False, f"Weather API error: {r2}", "weather")
    wx = r2.json()
    cw = wx.get("current_weather", {})
    codes = {0:"☀️ Clear",1:"🌤 Mostly clear",2:"⛅ Partly cloudy",3:"☁️ Overcast",
             45:"🌫 Fog",51:"🌦 Drizzle",61:"🌧 Rain",63:"🌧 Heavy rain",
             71:"❄️ Snow",80:"🌦 Showers",95:"⛈ Thunderstorm"}
    cond = codes.get(cw.get("weathercode",0),"🌡 Unknown")
    tc = cw.get("temperature","?")
    tf = round(float(tc)*9/5+32,1) if isinstance(tc,(int,float)) else "?"
    lines = [f"⛅ {city}", f"  Now: {cond} | {tc}°C / {tf}°F | Wind {cw.get('windspeed','?')} km/h", "  Forecast:"]
    d = wx.get("daily",{})
    for i in range(min(5, len(d.get("time",[])))):
        dc = codes.get((d.get("weathercode",[0]*5)[i]),"")
        lines.append(f"    {d['time'][i]}: {dc} {d.get('temperature_2m_min',[0]*5)[i]}–{d.get('temperature_2m_max',[0]*5)[i]}°C 💧{d.get('precipitation_sum',[0]*5)[i]}mm")
    return R(True, "\n".join(lines), "weather")


def get_datetime(timezone=None):
    from datetime import datetime
    import pytz
    tz_name = timezone or "UTC"
    try:
        tz = pytz.timezone(tz_name)
        now = datetime.now(tz)
    except Exception:
        now = datetime.now(); tz_name = "local"
    return R(True, (f"🕐 {tz_name}\n"
                    f"  Date : {now.strftime('%A, %B %d, %Y')}\n"
                    f"  Time : {now.strftime('%I:%M:%S %p')}\n"
                    f"  Week : {now.isocalendar()[1]} of {now.year}"), "datetime")


def calculate(expression):
    safe = {k: getattr(math, k) for k in dir(math) if not k.startswith("_")}
    safe.update({"abs":abs,"round":round,"int":int,"float":float,"sum":sum,"min":min,"max":max,"len":len})
    try:
        result = eval(expression, {"__builtins__": {}}, safe)  # noqa: S307
        return R(True, f"🧮 {expression} = {result}", "calc")
    except Exception as e:
        return R(False, f"Calc error: {e}", "calc")


def get_stock(symbol):
    ok, r = _req(f"https://query1.finance.yahoo.com/v8/finance/chart/{symbol}",
                 headers={"User-Agent":"Mozilla/5.0"})
    if not ok: return R(False, f"Stock error: {r}", "stock")
    try:
        meta = r.json()["chart"]["result"][0]["meta"]
        price = meta.get("regularMarketPrice","?")
        prev  = meta.get("previousClose", price)
        chg   = round(float(price)-float(prev),2)
        pct   = round(chg/float(prev)*100,2) if prev else 0
        arrow = "📈" if chg>=0 else "📉"
        return R(True, f"{arrow} {symbol.upper()}: ${price}  ({'+' if chg>=0 else ''}{chg}, {'+' if pct>=0 else ''}{pct}%)  prev ${prev}", "stock")
    except Exception as e:
        return R(False, str(e), "stock")


def wikipedia(topic):
    ok, r = _req(f"https://en.wikipedia.org/api/rest_v1/page/summary/{topic.replace(' ','_')}")
    if not ok: return R(False, f"Wiki error: {r}", "wiki")
    d = r.json()
    return R(True, f"📖 {d.get('title',topic)}\n{d.get('extract','No summary.')[:600]}", "wiki")


def convert_currency(amount, from_cur, to_cur):
    ok, r = _req(f"https://open.er-api.com/v6/latest/{from_cur.upper()}")
    if not ok: return R(False, f"Currency API error: {r}", "currency")
    rates = r.json().get("rates",{})
    rate = rates.get(to_cur.upper())
    if not rate: return R(False, f"Unknown currency: {to_cur}", "currency")
    result = round(float(amount) * rate, 4)
    return R(True, f"💱 {amount} {from_cur.upper()} = {result} {to_cur.upper()}  (rate: {rate})", "currency")


def convert_units(value, from_unit, to_unit):
    # Basic unit conversions
    conversions = {
        ("km","mi"): 0.621371, ("mi","km"): 1.60934,
        ("kg","lb"): 2.20462,  ("lb","kg"): 0.453592,
        ("m","ft"): 3.28084,   ("ft","m"): 0.3048,
        ("c","f"): lambda x: x*9/5+32, ("f","c"): lambda x: (x-32)*5/9,
        ("l","gal"): 0.264172, ("gal","l"): 3.78541,
        ("mb","gb"): 0.001024, ("gb","mb"): 1024,
        ("gb","tb"): 0.001024, ("tb","gb"): 1024,
    }
    key = (from_unit.lower(), to_unit.lower())
    factor = conversions.get(key)
    if factor is None: return R(False, f"Unknown conversion: {from_unit} → {to_unit}", "unit")
    result = factor(value) if callable(factor) else value * factor
    return R(True, f"📏 {value} {from_unit} = {round(result,4)} {to_unit}", "unit")


def generate_qr(data, output_path=None):
    try:
        import qrcode  # type: ignore
        qr = qrcode.QRCode()
        qr.add_data(data)
        qr.make(fit=True)
        if output_path:
            img = qr.make_image()
            img.save(output_path)
            return R(True, f"QR saved to {output_path}", "qr")
        # Print ASCII QR to terminal
        from io import StringIO
        qr.print_ascii(out=StringIO())
        return R(True, "QR generated (install qrcode: pip install qrcode[pil])", "qr")
    except ImportError:
        return R(False, "Install qrcode: pip install 'qrcode[pil]'", "qr")


def api_test(url, method="GET", headers=None, body=None):
    ok, r = _req(url, method=method.upper(), headers=headers, body=body)
    if not ok: return R(False, f"API error: {r}", f"{method} {url}")
    try:
        data = r.json()
        out = json.dumps(data, indent=2)[:2000]
    except Exception:
        out = r.text[:2000]
    return R(True, f"[{r.status_code}] {method} {url}\n\n{out}", f"{method} {url}")


def start_local_server(port=8080, directory="."):
    import subprocess
    import shutil
    if shutil.which("python3"):
        subprocess.Popen(["python3","-m","http.server",str(port),"--directory",directory],
                         start_new_session=True)
        return R(True, f"Server started at http://localhost:{port} serving {directory}", f"http.server:{port}")
    return R(False, "python3 not found", "")
