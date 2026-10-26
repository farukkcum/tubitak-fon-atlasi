#!/usr/bin/env python3
"""
TÜBİTAK Fon Atlası · takvim taraması
====================================

GitHub Actions bu betiği her sabah çalıştırır ve depodaki takvim.json dosyasını
yeniler. Atlas (index.html) açılışta ve "Takvimi güncelle" butonuna basıldığında
bu dosyayı okur.

Taranan yerler:
  1. tubitak.gov.tr/tr/duyuru listesinin son sayfaları: başlığı atlastaki bir
     programla eşleşen çağrı, uzatma ve güncelleme duyuruları.
  2. Duyurusu bulunmayan programların resmî sayfalarındaki takvim tabloları ve
     "son başvuru" cümleleri.

Elle çalıştırmak için:
    pip install requests beautifulsoup4
    python scripts/tara.py --out takvim.json

Hiç duyuru okunamazsa (site erişilemezse) dosya yazılmaz ve betik hata koduyla
çıkar; böylece önceki takvim korunur.
"""

from __future__ import annotations

import argparse
import datetime as dt
import json
import re
import sys
import time
from dataclasses import dataclass
from urllib.parse import urljoin

try:
    import requests
    from bs4 import BeautifulSoup
except ImportError:  # pragma: no cover
    sys.exit("Eksik paket: pip install requests beautifulsoup4")

BASE = "https://tubitak.gov.tr"
LIST_URL = BASE + "/tr/duyuru"
UA = "Mozilla/5.0 (TUBITAK-fon-atlasi takvim taramasi)"

# ---------------------------------------------------------------------------
# 1. Duyuru başlığı → atlas kartı eşleştirmesi
#    targets : atlastaki kartın program no alanı (index.html'deki `no`)
#    include : başlıkta aranan ifadeler (biri yeterli)
#    exclude : başlıkta varsa kural uygulanmaz
#    page    : programın resmî sayfası; duyuru bulunamazsa burası taranır
#    label   : kartı olmayan genel duyurular için takvimde görünen etiket
#    generic : yalnızca daha özel bir kural eşleşmediyse kullanılır
# ---------------------------------------------------------------------------
P = "/tr/destekler/akademik/ulusal-destek-programlari/"
S = "/tr/destekler/sanayi/ulusal-destek-programlari/"
SI = "/tr/destekler/sanayi/uluslararasi-ortakli-destek-programlari/"
DS = "/tr/burslar/doktora-sonrasi/arastirma-burs-programlari/"
LE = "/tr/burslar/lisansustu/egitim-burs-programlari/"
LA = "/tr/burslar/lisansustu/arastirma-burs-programlari/"
LB = "/tr/burslar/lisans-onlisans/destek-programlari/"
ED = "/tr/destekler/bilimsel-etkinlik/etkinlik-duzenleme-destekleri/"
EK = "/tr/destekler/bilimsel-etkinlik/etkinliklere-katilma-destekleri/"
BT = "/tr/destekler/bilim-toplum/ulusal-destek-programlari/"
NB = r"(?!\s*[–-]?\s*[A-E]\b)"  # numaranın arkasında alt program harfi yoksa


@dataclass
class Rule:
    targets: list
    include: list
    exclude: str | None = None
    page: str | None = None
    label: str | None = None
    generic: bool = False


RULES = [
    # ARDEB
    Rule(["1001"], [r"\b1001\b"], r"UDAP", P + "1001-bilimsel-ve-teknolojik-arastirma-projelerini-destekleme-programi"),
    Rule(["1001 · UDAP"], [r"UDAP"]),
    Rule(["1002-A", "1002-B"], [r"\b1002\b"]),
    Rule(["3501"], [r"\b3501\b"]),
    Rule(["1005"], [r"\b1005\b"], None, P + "1005-ulusal-yeni-fikirler-ve-urunler-arastirma-destek-programi"),
    Rule(["3005-A", "3005-B"], [r"\b3005\b"]),
    Rule(["1003"], [r"\b1003\b"], None, P + "1003-oncelikli-alanlar-ar-ge-projeleri-destekleme-programi"),
    Rule(["1004"], [r"\b1004\b"], None, P + "1004-mukemmeliyet-merkezi-destek-programi"),
    Rule(["1000"], [r"\b1000\b"], None, P + "1000-universitelerin-arastirma-ve-gelistirme-potansiyelinin-artirilmasina-yonelik-destek-programi"),
    Rule(["Kutup"], [r"Kutup Araştırma"], r"2204", P + "kutup-arastirmalari"),
    Rule(["1007"], [r"\b1007\b"], r"Balistik|SAVTAG|Savunma"),
    Rule(["1007 · SAVTAG"], [r"\b1007\b.*(Balistik|SAVTAG|Savunma)"]),
    # BİDEB araştırmacı
    Rule(["2218"], [r"\b2218\b"], None, DS + "2218-yurt-ici-doktora-sonrasi-arastirma-burs-programi"),
    Rule(["2219"], [r"\b2219\b"], None, DS + "2219-yurt-disi-doktora-sonrasi-arastirma-burs-programi"),
    Rule(["2221"], [r"\b2221\b"], None, DS + "2221-konuk-veya-akademik-izinli-sabbatical-bilim-insani-destekleme-p"),
    Rule(["2232-A", "2232-B"], [r"\b2232\b"], None, DS + "2232-uluslararasi-lider-arastirmacilar-programi"),
    Rule(["2236-A"], [r"2236\s*[–-]?\s*A\b", r"CoCirculation"], None, DS + "2236a-uluslararasi-deneyimli-arastirmaci-dolasimi-destek-programi"),
    Rule(["2236-B"], [r"2236\s*[–-]?\s*B\b", r"COFUND"]),
    Rule(["2247-A"], [r"2247\s*[–-]?\s*A\b", r"Ulusal Lider"], None, DS + "2247-ulusal-lider-arastirmacilar-programi"),
    Rule(["2247-D"], [r"2247\s*[–-]?\s*D\b", r"Genç Lider"], None, DS + "2247-d-ulusal-genc-liderler-programi"),
    Rule(["2247-B"], [r"2247\s*[–-]?\s*B\b", r"ERC Projeleri"]),
    # BİDEB burslar
    Rule(["2247-C"], [r"2247\s*[–-]?\s*C\b", r"\bSTAR\b"]),
    Rule(["2205"], [r"\b2205\b"]),
    Rule(["2209-A", "2209-B"], [r"\b2209\b"], None, LB + "2209-universite-ogrencileri-arastirma-projeleri-destekleme-programi"),
    Rule(["2210"], [r"\b2210\b"]),
    Rule(["2211"], [r"\b2211\b"]),
    Rule(["2213-A"], [r"\b2213" + r"(?!\s*[–-]?\s*B\b)"], None, LE + "2213-yurt-disi-doktora-burs-programi"),
    Rule(["2213-B"], [r"2213\s*[–-]?\s*B\b"]),
    Rule(["2214-A"], [r"\b2214\b"], None, LA + "2214-yurt-disi-doktora-sirasi-arastirma-burs-programi"),
    Rule(["2244"], [r"\b2244\b"], None, LE + "2244-sanayi-doktora-programi"),
    Rule(["2250"], [r"\b2250\b"], None, LE + "2250-lisansustu-burslari-performans-programi"),
    Rule(["2204"], [r"\b2204\b"]),
    Rule(["2242"], [r"\b2242\b"]),
    Rule(["BİÇABA"], [r"BİÇABA"]),
    # Etkinlik
    Rule(["2223-B", "2223-C"], [r"\b2223\b" + NB], None, ED + "2223-b-yurt-ici-bilimsel-etkinlik-duzenleme-destegi"),
    Rule(["2223-B"], [r"2223\s*[–-]?\s*B\b"]),
    Rule(["2223-C"], [r"2223\s*[–-]?\s*C\b"]),
    Rule(["2223-D"], [r"2223\s*[–-]?\s*D\b"]),
    Rule(["2224-A", "2224-B"], [r"\b2224\b" + NB], None, EK + "2224-yurt-disi-bilimsel-etkinliklere-katilimi-destekleme-programi"),
    Rule(["2224-A"], [r"2224\s*[–-]?\s*A\b"]),
    Rule(["2224-B"], [r"2224\s*[–-]?\s*B\b"]),
    Rule(["2224-C"], [r"2224\s*[–-]?\s*C\b"]),
    Rule(["2224-D"], [r"2224\s*[–-]?\s*D\b"]),
    Rule(["2237-A"], [r"\b2237\b" + NB, r"2237\s*[–-]?\s*A\b"], r"Proje Eğitimi", ED + "2237-bilimsel-egitim-etkinlikleri-destegi"),
    Rule(["2237-B"], [r"2237\s*[–-]?\s*B\b", r"Proje Eğitimi"]),
    # UİDB
    Rule(["1071 · DUT"], [r"\bDUT\b", r"Kentsel Geçiş"]),
    Rule(["1071 · Biodiversa+"], [r"Biodiv"]),
    Rule(["1071 · Water4All"], [r"Water4All"]),
    Rule(["1071 · SBEP"], [r"\bSBEP\b", r"Mavi Ekonomi"]),
    Rule(["1071 · FOREST"], [r"\bFOREST\b"]),
    Rule(["1071 · PRIMA"], [r"\bPRIMA\b"]),
    Rule(["2531"], [r"\b2531\b", r"DAAD"]),
    Rule(["2572"], [r"\b2572\b", r"Ürdün"]),
    Rule(["2518"], [r"\b2518\b", r"Özbekistan"]),
    Rule(["COST · 2515"], [r"\bCOST\b", r"\b2515\b"]),
    Rule(["Belmont"], [r"Belmont"]),
    Rule(["NATO SPS"], [r"\bNATO\b"]),
    Rule(["SEA-EU JFS"], [r"SEA[- ]EU", r"Güneydoğu Asya"]),
    Rule(["CORNET"], [r"CORNET"]),
    Rule([], [r"Ufuk Avrupa", r"Ortaklığı"], None, None, "Ufuk Avrupa ortak çağrısı", True),
    Rule([], [r"\b25\d\d\b", r"İkili İş ?[Bb]irliği"], None, None, "İkili işbirliği çağrısı", True),
    # TEYDEB
    Rule(["1501"], [r"\b1501\b"], None, S + "1501-tubitak-sanayi-ar-ge-projeleri-destekleme-programi"),
    Rule(["1505"], [r"\b1505\b"]),
    Rule(["1507"], [r"\b1507\b"], None, S + "1507-tubitak-kobi-ar-ge-baslangic-destek-programi"),
    Rule(["1511"], [r"\b1511\b", r"Sanayi Hamlesi"]),
    Rule(["1515"], [r"\b1515\b"]),
    Rule(["1707"], [r"\b1707\b", r"Sipariş Ar-Ge"], None, S + "1707-siparise-dayali-ar-ge-projeleri-icin-kobi-destekleme-cagrisi"),
    Rule(["1711"], [r"\b1711\b", r"Yapay Zek[aâ] Ekosistem"], None, S + "1711-yapay-zeka-ekosistem-cagrisi"),
    Rule(["1831"], [r"\b1831\b", r"Mentörlük"], None, S + "1831-yesil-inovasyon-teknoloji-mentorluk-cagrisi"),
    Rule(["1832"], [r"\b1832\b", r"Sanayide Yeşil Dönüşüm"], None, S + "1832-sanayide-yesil-donusum-cagrisi"),
    Rule(["1833"], [r"\b1833\b", r"SAYEM"], None, S + "1833-sayem-yesil-donusum-cagrisi"),
    Rule(["1503"], [r"\b1503\b", r"Proje Pazar"]),
    Rule(["1701"], [r"\b1701\b"]),
    # Girişim ve TT
    Rule(["1812"], [r"\b1812\b", r"BiGG Yatırım"], None, S + "1812-yatirim-tabanli-girisimcilik-destek-programi-bigg-yatirim"),
    Rule(["1612 · BiGG"], [r"\b1612\b", r"Uygulayıcı Kuruluş"]),
    Rule([], [r"BiGG"], None, None, "BiGG çağrısı", True),
    Rule(["1513"], [r"\b1513\b"]),
    Rule(["1514"], [r"\b1514\b", r"Tech-?InvesTR"]),
    Rule(["1601"], [r"\b1601\b"]),
    Rule(["1602"], [r"\b1602\b"]),
    Rule(["1613"], [r"\b1613\b"]),
    Rule(["1702"], [r"\b1702\b"]),
    # Eureka
    Rule(["1709"], [r"Eurostars", r"\b1709\b"], None, SI + "1709-eureka-eurostars"),
    Rule(["1509 · Japonya"], [r"Globalstars.*Japon"]),
    Rule(["1509 · İspanya"], [r"Eureka.*İspanya"]),
    Rule(["1719"], [r"\b1719\b"]),
    Rule(["Innowwide"], [r"Innowwide"]),
    Rule([], [r"Eureka", r"\b1509\b"], None, None, "Eureka çağrısı", True),
    # Bilim ve Toplum
    Rule(["4001"], [r"\b4001\b"]),
    Rule(["4003"], [r"\b4003\b"]),
    Rule(["4004"], [r"\b4004\b"], None, BT + "4004-doga-egitimi-ve-bilim-okullari-destekleme-programi"),
    Rule(["4005"], [r"\b4005\b"], None, BT + "4005-yenilikci-egitim-uygulamalari-destekleme-programi"),
    Rule(["4006"], [r"\b4006\b"]),
    Rule(["4007"], [r"\b4007\b"], None, BT + "4007-bilim-senlikleri-destekleme-programi"),
    Rule(["4008"], [r"\b4008\b"]),
    Rule(["4009"], [r"\b4009\b"]),
    Rule(["Söyleşi"], [r"Bilim Söyleşi"]),
    Rule(["Teşvik"], [r"Proje Teşvik Ödül"]),
    Rule(["MTA"], [r"Milli Teknoloji", r"Gökyüzü Gözlem"]),
    # Çevre
    Rule(["EMBO"], [r"\bEMBO\b"]),
    Rule(["ICGEB"], [r"ICGEB"]),
    Rule(["2216"], [r"\b2216"]),
    Rule(["Ödül"], [r"Bilim,? Teşvik"]),
]

OPEN_WORDS = re.compile(r"açıldı|açılıyor|başladı|başvuru(?:ya|lara)? açık|uzatıldı|güncellendi|yayınlandı|yayımlandı|başvuruya", re.I)
SKIP_WORDS = re.compile(r"sonuç|finalist|kazanan|tören", re.I)


def match_rules(title: str) -> list[Rule]:
    hits = [r for r in RULES
            if any(re.search(p, title, re.I) for p in r.include)
            and not (r.exclude and re.search(r.exclude, title, re.I))]
    specific = [r for r in hits if not r.generic]
    return specific or hits[:1]

# ---------------------------------------------------------------------------
# 2. Türkçe tarih ayıklama
# ---------------------------------------------------------------------------
MONTHS = {
    "ocak": 1, "oca": 1, "şubat": 2, "şub": 2, "mart": 3, "mar": 3, "nisan": 4, "nis": 4,
    "mayıs": 5, "may": 5, "haziran": 6, "haz": 6, "temmuz": 7, "tem": 7, "ağustos": 8, "ağu": 8,
    "eylül": 9, "eyl": 9, "ekim": 10, "eki": 10, "kasım": 11, "kas": 11, "aralık": 12, "ara": 12,
}
MON = r"(Ocak|Oca|Şubat|Şub|Mart|Mar|Nisan|Nis|Mayıs|May|Haziran|Haz|Temmuz|Tem|Ağustos|Ağu|Eylül|Eyl|Ekim|Eki|Kasım|Kas|Aralık|Ara)\.?"
DASH = r"\s*[–—-]\s*"

RE_RANGE_SAME = re.compile(rf"(\d{{1,2}}){DASH}(\d{{1,2}})\s+{MON}\s+(\d{{4}})", re.I)
RE_RANGE_DIFF = re.compile(rf"(\d{{1,2}})\s+{MON}(?:\s+(\d{{4}}))?{DASH}(\d{{1,2}})\s+{MON}\s+(\d{{4}})", re.I)
RE_LONG = re.compile(rf"(\d{{1,2}})\s+{MON}\s+(\d{{4}})", re.I)
RE_NUM = re.compile(r"\b(\d{1,2})[./](\d{1,2})[./](20\d{2})\b")

DEADLINE_CUES = re.compile(
    r"son başvuru|son tarih|son gün|başvuru süresi|başvurular[ıi]?\s.*(?:kadar|sona|kapan)|"
    r"kadar|sona erecek|sona erer|kapanış|kapanacak|bitiş|deadline|tamamlanma", re.I)
ESIGN_CUES = re.compile(r"e-?imza|elektronik imza|kurum (?:yetkilisi )?onay", re.I)
INTL_CUES = re.compile(r"uluslararası|çağrı sekretarya|CET|CEST|international|platformu", re.I)
NEGATIVE_CUES = re.compile(r"sonuç(?:lar)?(?:ı|ın)?\s+açıklan|ilan edil|destek(?:in)?\s+başla|"
                           r"proje başlangıç|etkinlik tarih|doktora tarihi|mezun|yaş", re.I)


def _mk(d: str, m: str, y: str) -> dt.date | None:
    try:
        return dt.date(int(y), MONTHS[m.lower().rstrip(".")], int(d))
    except (KeyError, ValueError):
        return None


def dates_in(sentence: str) -> list[tuple[dt.date, bool]]:
    """Cümledeki tarihleri döndürür. İkinci değer: tarih bir aralığın bitişi mi?"""
    found: list[tuple[dt.date, bool]] = []
    spans: list[tuple[int, int]] = []

    def free(a: int, b: int) -> bool:
        return all(b <= s or a >= e for s, e in spans)

    for m in RE_RANGE_DIFF.finditer(sentence):
        d2 = _mk(m.group(4), m.group(5), m.group(6))
        if d2:
            found.append((d2, True)); spans.append(m.span())
    for m in RE_RANGE_SAME.finditer(sentence):
        if free(*m.span()):
            d2 = _mk(m.group(2), m.group(3), m.group(4))
            if d2:
                found.append((d2, True)); spans.append(m.span())
    for m in RE_LONG.finditer(sentence):
        if free(*m.span()):
            d = _mk(m.group(1), m.group(2), m.group(3))
            if d:
                found.append((d, False)); spans.append(m.span())
    for m in RE_NUM.finditer(sentence):
        if free(*m.span()):
            try:
                found.append((dt.date(int(m.group(3)), int(m.group(2)), int(m.group(1))), False))
            except ValueError:
                pass
    # Aynı cümlede/tablo satırında birden çok tarih varsa en geç olan pencerenin kapanışıdır
    if len(found) >= 2:
        last = max(d for d, _ in found)
        found = [(d, r or d == last) for d, r in found]
    return found


def split_sentences(text: str) -> list[str]:
    text = re.sub(r"[ \t ]+", " ", text)
    parts = re.split(r"(?<=[.!?])\s+(?=[A-ZÇĞİÖŞÜ0-9])|\n+", text)
    return [p.strip() for p in parts if len(p.strip()) > 8]


@dataclass
class Hit:
    date: dt.date
    kind: str            # "son" | "eimza" | "intl"
    score: int
    sentence: str


def extract_deadlines(text: str, today: dt.date, strict: bool) -> list[Hit]:
    """Metindeki son başvuru adaylarını puanlayarak döndürür.
    strict=True (program sayfaları) iken cümlede son tarih ifadesi şarttır."""
    hits: list[Hit] = []
    for s in split_sentences(text):
        ds = dates_in(s)
        if not ds:
            continue
        cue = bool(DEADLINE_CUES.search(s))
        if strict and not cue:
            continue
        if NEGATIVE_CUES.search(s) and not cue:
            continue
        esign = bool(ESIGN_CUES.search(s))
        intl = bool(INTL_CUES.search(s)) and not re.search(r"ulusal başvuru|TÜBİTAK|PBS|TSİ", s)
        for d, is_range_end in ds:
            if d < today or d > today + dt.timedelta(days=550):
                continue
            score = 1 + (3 if cue else 0) + (2 if is_range_end else 0)
            if NEGATIVE_CUES.search(s):
                score -= 3
            kind = "eimza" if esign else ("intl" if intl else "son")
            if score > 0:
                hits.append(Hit(d, kind, score, s[:300]))
    return hits



# ---------------------------------------------------------------------------
# 3. Tarama
# ---------------------------------------------------------------------------
class Fetcher:
    def __init__(self, delay: float):
        self.s = requests.Session()
        self.s.headers["User-Agent"] = UA
        self.delay = delay
        self.errors: list[str] = []
        self.count = 0

    def soup(self, url: str) -> BeautifulSoup | None:
        try:
            time.sleep(self.delay)
            r = self.s.get(url, timeout=25)
            r.raise_for_status()
            self.count += 1
            return BeautifulSoup(r.text, "html.parser")
        except Exception as e:  # noqa: BLE001
            self.errors.append(f"{url}: {e}")
            return None


def main_text(soup: BeautifulSoup) -> str:
    for t in soup(["script", "style", "nav", "header", "footer", "noscript", "form"]):
        t.decompose()
    root = soup.find("main") or soup.find("article") or soup.body or soup
    # tablolardaki satırları cümleye çevir (ör. "3. çağrı | 1 Eylül 2026 | 13 Kasım 2026")
    for tr in root.find_all("tr"):
        cells = [c.get_text(" ", strip=True) for c in tr.find_all(["td", "th"])]
        tr.replace_with(soup.new_string("\n" + " | ".join(cells) + " son başvuru tablosu.\n"))
    return root.get_text("\n", strip=True)



def list_announcements(f: Fetcher, pages: int) -> list[tuple[str, str]]:
    seen: dict[str, str] = {}
    for p in range(pages):
        url = LIST_URL if p == 0 else f"{LIST_URL}?page={p}"
        soup = f.soup(url)
        if not soup:
            continue
        for a in soup.select('a[href*="/tr/duyuru/"]'):
            href = urljoin(BASE, a["href"].split("#")[0].split("?")[0])
            title = a.get_text(" ", strip=True)
            if href.rstrip("/").endswith("/tr/duyuru") or len(title) < 12 or title.lower().startswith("devamını"):
                continue
            seen.setdefault(href, title)
    return list(seen.items())


def best(hits: list[Hit]):
    """En yakın ulusal son tarih, e-imza penceresinin sonu ve uluslararası tarih."""
    def pick(kind):
        hs = [h for h in hits if h.kind == kind]
        if not hs:
            return None
        top = max(h.score for h in hs)
        cands = [h for h in hs if h.score >= top - 1]
        return (max if kind == "eimza" else min)(cands, key=lambda h: h.date)
    return pick("son"), pick("eimza"), pick("intl")


def entry(targets, label, title, url, origin, hits):
    son, eimza, intl = best(hits)
    main = son or intl
    if not main:
        return None
    return {
        "targets": targets,
        "label": label,
        "title": title,
        "url": url,
        "origin": origin,
        "dl": main.date.isoformat(),
        "kind": main.kind,
        "esign": eimza.date.isoformat() if eimza and eimza.date >= main.date else None,
        "intl": intl.date.isoformat() if son and intl and intl.date != son.date else None,
        "sentence": main.sentence,
    }


def build(today: dt.date, pages: int, delay: float, verbose: bool) -> dict:
    f = Fetcher(delay)
    items: list[dict] = []
    covered: set[str] = set()

    anns = list_announcements(f, pages)
    if verbose:
        print(f"{len(anns)} duyuru bağlantısı bulundu", file=sys.stderr)
    if not anns:
        print("Duyuru listesi okunamadı; takvim.json değiştirilmedi.", file=sys.stderr)
        for e in f.errors[:5]:
            print("  " + e, file=sys.stderr)
        sys.exit(1)

    for url, title in anns:
        if SKIP_WORDS.search(title) or not OPEN_WORDS.search(title):
            continue
        rules = match_rules(title)
        if not rules:
            continue
        soup = f.soup(url)
        if not soup:
            continue
        targets = sorted({t for r in rules for t in r.targets})
        label = next((r.label for r in rules if r.label), None)
        it = entry(targets, label, title, url, "duyuru", extract_deadlines(main_text(soup), today, strict=False))
        if it:
            items.append(it)
            covered.update(targets)
            if verbose:
                print(f"  ✓ {it['dl']}  {title[:90]}", file=sys.stderr)

    for r in RULES:
        if not r.page or set(r.targets) & covered:
            continue
        url = BASE + r.page
        soup = f.soup(url)
        if not soup:
            continue
        h1 = soup.find("h1")
        title = h1.get_text(" ", strip=True) if h1 else " / ".join(r.targets)
        it = entry(r.targets, None, title, url, "program sayfası", extract_deadlines(main_text(soup), today, strict=True))
        if it:
            items.append(it)
            covered.update(r.targets)
            if verbose:
                print(f"  ✓ {it['dl']}  {title[:90]} (program sayfası)", file=sys.stderr)

    uniq: dict[tuple, dict] = {}
    for it in sorted(items, key=lambda i: (i["origin"] != "duyuru", i["dl"])):
        uniq.setdefault((tuple(it["targets"]) or (it["title"],), it["dl"]), it)

    tz = dt.timezone(dt.timedelta(hours=3))
    return {
        "generated": dt.datetime.now(tz).isoformat(timespec="minutes"),
        "scanned": f.count,
        "errors": len(f.errors),
        "items": sorted(uniq.values(), key=lambda i: i["dl"]),
    }


def main() -> None:
    ap = argparse.ArgumentParser(description="TÜBİTAK Fon Atlası için takvim.json üretir.")
    ap.add_argument("--out", default="takvim.json")
    ap.add_argument("--pages", type=int, default=8, help="taranacak duyuru listesi sayfası (sayfa başına 18 duyuru)")
    ap.add_argument("--delay", type=float, default=0.7, help="istekler arası bekleme, saniye")
    ap.add_argument("--bugun", help="'bugün' yerine kullanılacak tarih, YYYY-AA-GG")
    ap.add_argument("-q", "--quiet", action="store_true")
    a = ap.parse_args()
    today = dt.date.fromisoformat(a.bugun) if a.bugun else dt.date.today()
    data = build(today, a.pages, a.delay, not a.quiet)
    with open(a.out, "w", encoding="utf-8") as fh:
        json.dump(data, fh, ensure_ascii=False, indent=1)
    print(f"{a.out}: {len(data['items'])} son tarih, {data['scanned']} sayfa, {data['errors']} hata")


if __name__ == "__main__":
    main()
