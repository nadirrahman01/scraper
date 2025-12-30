import re
import time
import html as htmllib
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Set, Tuple, Optional
from urllib.parse import urljoin, urlparse

import pandas as pd
import requests
import streamlit as st
from bs4 import BeautifulSoup
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry


# =========================================================
# Cordoba / CRG Brand (Light)
# =========================================================
CRG = {
    "gold": "#9A690F",
    "gold_dark": "#7F560C",
    "bg": "#FFF7F0",
    "card": "#FFFFFF",
    "ink": "#0B0E14",
    "muted": "rgba(11,14,20,0.66)",
    "muted2": "rgba(11,14,20,0.52)",
    "border": "rgba(11,14,20,0.10)",
    "border2": "rgba(11,14,20,0.14)",
    "shadow": "0 18px 45px rgba(11,14,20,0.08)",
    "shadow_soft": "0 10px 22px rgba(11,14,20,0.06)",
}

st.set_page_config(
    page_title="CRG | Email Discovery",
    page_icon="✉️",
    layout="wide",
    initial_sidebar_state="expanded",
)

# =========================================================
# Global CSS: make it look like a Cordoba web app
# =========================================================
st.markdown(
    f"""
<style>
/* Hide Streamlit chrome */
#MainMenu {{ visibility: hidden; }}
footer {{ visibility: hidden; }}
header {{ visibility: hidden; }}
[data-testid="stToolbar"] {{ visibility: hidden; height: 0px; }}
[data-testid="stDecoration"] {{ display: none; }}
[data-testid="stStatusWidget"] {{ visibility:hidden; }}

/* Base */
.stApp {{
  background: {CRG["bg"]};
  color: {CRG["ink"]};
}}
.block-container {{
  padding-top: 22px;
  padding-bottom: 44px;
  max-width: 1180px;
}}
html, body, [class*="css"] {{
  font-family: -apple-system, BlinkMacSystemFont, "Inter", "Helvetica Neue", Arial, sans-serif;
  color: {CRG["ink"]} !important;
}}

/* Typography */
h1, h2, h3 {{
  font-family: "Times New Roman", Times, serif;
  font-weight: 650;
  letter-spacing: 0.2px;
  color: {CRG["ink"]};
  margin-bottom: 6px;
}}

/* FORCE all label/help/caption text to be readable */
label, label span, .stMarkdown, .stTextInput label, .stTextArea label,
.stSelectbox label, .stMultiSelect label, .stSlider label, .stCheckbox label {{
  color: {CRG["ink"]} !important;
  font-weight: 650 !important;
}}
small, .stCaption, .stHelp, [data-testid="stCaptionContainer"], [data-testid="stWidgetLabel"] + div {{
  color: {CRG["muted"]} !important;
}}
/* Streamlit often renders "help" text as very faint; override it */
div[data-testid="stMarkdownContainer"] p {{
  color: {CRG["ink"]};
}}
/* Placeholder text slightly muted but still visible */
textarea::placeholder, input::placeholder {{
  color: {CRG["muted2"]} !important;
  opacity: 1 !important;
}}

/* Card system */
.crg-card {{
  background: {CRG["card"]};
  border: 1px solid {CRG["border"]};
  border-radius: 18px;
  box-shadow: {CRG["shadow"]};
  padding: 18px 18px;
}}
.crg-card.soft {{
  box-shadow: {CRG["shadow_soft"]};
}}
.crg-header-title {{
  font-family: "Times New Roman", Times, serif;
  font-size: 44px;
  font-weight: 750;
  line-height: 1.05;
  margin: 0;
}}
.crg-subtitle {{
  margin-top: 6px;
  font-size: 14px;
  color: {CRG["muted"]};
}}

/* Sidebar */
section[data-testid="stSidebar"] {{
  background: {CRG["bg"]};
  border-right: 1px solid rgba(11,14,20,0.06);
}}
section[data-testid="stSidebar"] .block-container {{
  padding-top: 18px;
}}
.crg-sidebar-card {{
  background: {CRG["card"]};
  border: 1px solid {CRG["border"]};
  border-radius: 18px;
  box-shadow: {CRG["shadow_soft"]};
  padding: 16px;
}}

/* Inputs */
textarea, input {{
  background: {CRG["card"]} !important;
  border: 1px solid {CRG["border2"]} !important;
  border-radius: 14px !important;
  color: {CRG["ink"]} !important;
}}
div[data-baseweb="textarea"] textarea {{ border-radius: 14px !important; }}
div[data-baseweb="input"] input {{ border-radius: 14px !important; }}

/* Buttons */
.stButton > button {{
  background: {CRG["gold"]};
  color: white;
  border: none;
  border-radius: 14px;
  padding: 0.65rem 1.05rem;
  font-weight: 800;
  box-shadow: 0 12px 25px rgba(154,105,15,0.18);
}}
.stButton > button:hover {{ background: {CRG["gold_dark"]}; }}
button[kind="secondary"] {{
  background: white !important;
  color: {CRG["ink"]} !important;
  border: 1px solid {CRG["border2"]} !important;
  border-radius: 14px !important;
  font-weight: 750 !important;
  box-shadow: 0 10px 20px rgba(11,14,20,0.06) !important;
}}
button[kind="secondary"]:hover {{ background: rgba(11,14,20,0.02) !important; }}

/* Tabs */
button[data-baseweb="tab"] {{
  font-weight: 800;
  color: rgba(11,14,20,0.70) !important;
}}
button[data-baseweb="tab"][aria-selected="true"] {{
  color: {CRG["gold"]} !important;
  border-bottom: 2px solid {CRG["gold"]} !important;
}}

/* Sliders: gold track, black numbers */
div[data-baseweb="slider"] [role="slider"] {{
  background: {CRG["gold"]} !important;
  border-color: {CRG["gold"]} !important;
}}
div[data-baseweb="slider"] span {{
  background: transparent !important;
  color: {CRG["ink"]} !important;
  font-weight: 750 !important;
}}

/* Multiselect: remove dark blob, clean chips */
div[data-baseweb="select"] > div {{
  background: {CRG["card"]} !important;
  border: 1px solid {CRG["border2"]} !important;
  border-radius: 14px !important;
  box-shadow: none !important;
}}
div[data-baseweb="tag"] {{
  background: rgba(154,105,15,0.10) !important;
  border: 1px solid rgba(154,105,15,0.22) !important;
  border-radius: 999px !important;
}}
div[data-baseweb="tag"] span {{
  color: {CRG["ink"]} !important;
  font-weight: 750 !important;
}}
ul[role="listbox"] {{
  background: {CRG["card"]} !important;
  border: 1px solid {CRG["border2"]} !important;
  border-radius: 14px !important;
  box-shadow: {CRG["shadow_soft"]} !important;
}}
ul[role="listbox"] li {{ color: {CRG["ink"]} !important; }}
ul[role="listbox"] li:hover {{ background: rgba(11,14,20,0.03) !important; }}

/* Tables */
div[data-testid="stDataFrame"] {{
  border: 1px solid {CRG["border"]};
  border-radius: 16px;
  overflow: hidden;
  background: {CRG["card"]};
  box-shadow: {CRG["shadow_soft"]};
}}
div[data-testid="stAlert"] {{ border-radius: 16px; }}
</style>
""",
    unsafe_allow_html=True,
)

# =========================================================
# Header (no extra pills, no junk)
# =========================================================
BASE_DIR = Path(__file__).resolve().parent
LOGO_PATHS = [
    BASE_DIR / "assets" / "Cordoba Capital Logo (500 x 200 px) (3).png",
    BASE_DIR / "assets" / "cordoba_logo.png",
    BASE_DIR / "assets" / "logo.png",
    BASE_DIR / "assets" / "cordoba_logo.jpg",
    BASE_DIR / "assets" / "logo.jpg",
]
logo_path = next((p for p in LOGO_PATHS if p.exists()), None)

st.markdown("<div class='crg-card soft'>", unsafe_allow_html=True)
hc1, hc2 = st.columns([1, 6], vertical_alignment="center")
with hc1:
    if logo_path:
        st.image(str(logo_path), use_container_width=True)
with hc2:
    st.markdown(
        """
        <div style="padding-left:6px;">
          <div class="crg-header-title">CRG Email Discovery</div>
          <div class="crg-subtitle">Paste websites, scan, and extract public contact emails.</div>
        </div>
        """,
        unsafe_allow_html=True,
    )
st.markdown("</div>", unsafe_allow_html=True)

st.markdown("<div style='height:14px;'></div>", unsafe_allow_html=True)


# =========================================================
# Scraper logic
# =========================================================
EMAIL_RE = re.compile(r"[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}", re.IGNORECASE)

DEFAULT_KEYWORDS = [
    "contact", "about", "team", "support", "help", "impressum", "imprint",
    "legal", "privacy", "terms", "people", "company", "partners", "partnership",
    "sponsor", "sponsorship", "media", "press", "brand", "advertise", "marketing",
    "institutional", "investor", "ir", "corporate"
]

HIGH_VALUE_HINTS = [
    "partnership", "partner", "sponsor", "sponsorship",
    "businessdevelopment", "bizdev", "marketing", "communications",
    "comms", "brand", "outreach", "alliances", "strategic", "institutional",
    "investorrelations", "investor-relations", "ir", "corporate", "pr", "press"
]
MEDIUM_VALUE_HINTS = ["info", "hello", "contact", "enquiries", "inquiries", "connect"]
LOW_VALUE_HINTS = ["support", "help", "careers", "jobs", "hr", "webmaster", "privacy", "legal", "security", "abuse", "dpo"]

TRAP_LOCALPART_HINTS = set([
    "abuse", "security", "privacy", "legal", "webmaster", "postmaster",
    "mailer-daemon", "noreply", "no-reply", "donotreply"
])

ORG_TYPE_KEYWORDS = {
    "Asset Manager": ["asset management", "investment management", "aum", "fund", "funds", "portfolio"],
    "Bank": ["bank", "banking", "capital markets", "treasury", "lending"],
    "Fintech": ["fintech", "payments", "api", "neobank", "crypto", "platform", "saas"],
    "Consulting": ["consulting", "advisory", "strategy", "transformation", "professional services"],
    "Media / Research": ["research", "insights", "analysis", "publication", "media"],
    "Education": ["university", "college", "school", "institute", "academic"],
}

TLD_GEO = {
    ".uk": "UK", ".ie": "Ireland", ".de": "Germany", ".fr": "France", ".nl": "Netherlands",
    ".it": "Italy", ".es": "Spain", ".se": "Sweden", ".no": "Norway", ".dk": "Denmark",
    ".ch": "Switzerland", ".be": "Belgium", ".at": "Austria", ".pl": "Poland",
    ".pt": "Portugal", ".fi": "Finland", ".eu": "Europe", ".com": "Global / Unknown",
    ".org": "Global / Unknown"
}

COMMON_FILE_EXTS = (".png", ".jpg", ".jpeg", ".webp", ".gif", ".svg", ".pdf", ".css", ".js", ".ico")

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-GB,en;q=0.9",
    "Connection": "keep-alive",
}


@st.cache_resource
def get_http_session() -> requests.Session:
    session = requests.Session()
    retry = Retry(
        total=3,
        connect=3,
        read=3,
        backoff_factor=0.7,
        status_forcelist=(429, 500, 502, 503, 504),
        allowed_methods=("GET",),
        raise_on_status=False,
    )
    adapter = HTTPAdapter(max_retries=retry, pool_connections=20, pool_maxsize=20)
    session.mount("http://", adapter)
    session.mount("https://", adapter)
    return session


def normalise_url(u: str) -> str:
    u = (u or "").strip()
    if not u:
        return ""
    if not u.startswith(("http://", "https://")):
        u = "https://" + u
    return u


def domain_of(url: str) -> str:
    try:
        return urlparse(url).netloc.lower()
    except Exception:
        return ""


def same_domain(a: str, b: str) -> bool:
    return domain_of(a) == domain_of(b)


def geo_hint_from_domain(dom: str) -> str:
    d = (dom or "").lower()
    for tld, geo in TLD_GEO.items():
        if d.endswith(tld):
            return geo
    return "Global / Unknown"


def safe_get(url: str, timeout: int = 15) -> Tuple[str, str]:
    session = get_http_session()
    r = session.get(url, headers=HEADERS, timeout=timeout, allow_redirects=True)
    if r.status_code >= 400:
        raise requests.HTTPError(f"HTTP {r.status_code} for {url} (final: {r.url})")
    final_url = r.url
    ctype = (r.headers.get("Content-Type", "") or "").lower()
    if ("text/html" not in ctype) and ("application/xhtml" not in ctype):
        return final_url, ""
    return final_url, r.text or ""


def guess_page_type(url: str) -> str:
    p = (urlparse(url).path or "").lower()
    if any(k in p for k in ["partner", "partnership", "sponsor", "sponsorship", "advertis", "media-kit", "press-kit"]):
        return "Partnerships"
    if "investor" in p or "/ir" in p:
        return "Investor Relations"
    if "contact" in p:
        return "Contact"
    if "about" in p:
        return "About"
    if "team" in p or "people" in p:
        return "Team"
    if "careers" in p or "jobs" in p:
        return "Careers"
    if any(x in p for x in ["privacy", "terms", "legal", "imprint", "impressum"]):
        return "Legal"
    if p in ("", "/"):
        return "Homepage"
    return "Other"


def page_text_snippet(html: str, limit_chars: int = 70000) -> str:
    if not html:
        return ""
    soup = BeautifulSoup(html, "html.parser")
    for tag in soup(["script", "style", "noscript"]):
        tag.decompose()
    text = " ".join((soup.get_text(" ", strip=True) or "").split())
    return text[:limit_chars]


def extract_company_name(html: str, fallback_domain: str) -> str:
    if not html:
        return fallback_domain
    soup = BeautifulSoup(html, "html.parser")
    og = soup.find("meta", property="og:site_name")
    if og and og.get("content"):
        return og.get("content").strip()[:120]
    title = soup.title.string.strip() if soup.title and soup.title.string else ""
    if title:
        cleaned = re.split(r"\||-|–|—", title)[0].strip()
        return cleaned[:120] if cleaned else fallback_domain
    return fallback_domain


def infer_org_type(text: str) -> Tuple[str, float]:
    t = (text or "").lower()
    best = ("Corporate / Other", 0.0)
    for org, kws in ORG_TYPE_KEYWORDS.items():
        hits = sum(1 for k in kws if k in t)
        if hits > best[1]:
            best = (org, float(hits))
    if best[0] == "Corporate / Other":
        return best[0], 0.25
    conf = min(0.95, 0.35 + 0.12 * best[1])
    return best[0], conf


def deobfuscate_text(text: str) -> str:
    if not text:
        return ""
    t = htmllib.unescape(text)
    t = re.sub(r"\s*\[\s*at\s*\]\s*", "@", t, flags=re.IGNORECASE)
    t = re.sub(r"\s*\(\s*at\s*\)\s*", "@", t, flags=re.IGNORECASE)
    t = re.sub(r"\s+at\s+", "@", t, flags=re.IGNORECASE)
    t = re.sub(r"\s*\[\s*dot\s*\]\s*", ".", t, flags=re.IGNORECASE)
    t = re.sub(r"\s*\(\s*dot\s*\)\s*", ".", t, flags=re.IGNORECASE)
    t = re.sub(r"\s+dot\s+", ".", t, flags=re.IGNORECASE)
    t = t.replace("\u200b", "").replace("\u200c", "").replace("\u200d", "")
    return t


def decode_cfemail(cfhex: str) -> Optional[str]:
    try:
        s = cfhex.strip()
        if not s or len(s) < 4:
            return None
        data = bytes.fromhex(s)
        key = data[0]
        decoded = bytes([b ^ key for b in data[1:]]).decode("utf-8", errors="ignore")
        if "@" in decoded and "." in decoded:
            return decoded
        return None
    except Exception:
        return None


def is_valid_email(email: str) -> bool:
    e = (email or "").strip()
    if not e:
        return False
    if any(e.lower().endswith(ext) for ext in COMMON_FILE_EXTS):
        return False
    if "/" in e or "\\" in e:
        return False
    return bool(EMAIL_RE.fullmatch(e))


def localpart(email: str) -> str:
    try:
        return (email.split("@", 1)[0] or "").lower()
    except Exception:
        return ""


def classify_email_relevance(email: str) -> str:
    lp = localpart(email)
    if any(h in lp for h in HIGH_VALUE_HINTS):
        return "High"
    if any(h in lp for h in LOW_VALUE_HINTS):
        return "Low"
    if any(h in lp for h in MEDIUM_VALUE_HINTS):
        return "Medium"
    return "Medium"


def is_trap_email(email: str) -> bool:
    lp = localpart(email)
    if lp in TRAP_LOCALPART_HINTS:
        return True
    if any(h in lp for h in TRAP_LOCALPART_HINTS):
        return True
    return False


def extract_mailto_with_context(soup: BeautifulSoup) -> List[Dict]:
    results = []
    for a in soup.find_all("a", href=True):
        href = (a.get("href") or "").strip()
        if not href.lower().startswith("mailto:"):
            continue
        em = href.split("mailto:", 1)[1].split("?", 1)[0].strip()
        em = deobfuscate_text(em)
        if not is_valid_email(em):
            continue
        anchor_text = " ".join((a.get_text(" ", strip=True) or "").split())[:120]
        parent = a.parent
        parent_text = ""
        for _ in range(2):
            if parent:
                parent_text = " ".join((parent.get_text(" ", strip=True) or "").split())[:240]
                parent = parent.parent
        context = f"{anchor_text} {parent_text}".strip()
        results.append({"email": em, "context": context[:300]})
    return results


def extract_cfemails(soup: BeautifulSoup) -> List[Dict]:
    results = []
    for tag in soup.find_all(attrs={"data-cfemail": True}):
        cfhex = tag.get("data-cfemail") or ""
        decoded = decode_cfemail(cfhex)
        if decoded and is_valid_email(decoded):
            context = " ".join((tag.get_text(" ", strip=True) or "").split())[:200]
            results.append({"email": decoded, "context": context})
    return results


def extract_emails_from_html(html: str) -> Set[str]:
    if not html:
        return set()
    text = deobfuscate_text(html)
    emails = set(m.group(0) for m in EMAIL_RE.finditer(text))
    return set(e for e in emails if is_valid_email(e))


GUESS_PATHS = [
    "/partnerships", "/partners", "/partner", "/sponsorship", "/sponsor", "/sponsors",
    "/media", "/press", "/advertise", "/advertising", "/brand", "/marketing",
    "/contact", "/contact-us", "/about", "/about-us", "/team", "/people",
    "/investor-relations", "/ir", "/institutional", "/corporate",
]


def build_base(url: str) -> str:
    p = urlparse(url)
    return f"{p.scheme}://{p.netloc}"


def guess_key_pages(base_url: str) -> List[str]:
    out = [base_url]
    for path in GUESS_PATHS:
        out.append(urljoin(base_url, path))
    seen = set()
    final = []
    for u in out:
        if u not in seen:
            final.append(u)
            seen.add(u)
    return final


def find_relevant_links(base_url: str, html: str, keywords: List[str], max_links: int = 25) -> List[str]:
    soup = BeautifulSoup(html, "html.parser")
    links = []
    for a in soup.find_all("a", href=True):
        href = (a.get("href") or "").strip()
        if not href or href.startswith(("mailto:", "tel:", "javascript:")):
            continue
        absolute = urljoin(base_url, href)
        if not same_domain(base_url, absolute):
            continue
        path = (urlparse(absolute).path or "").lower()
        if any(k in path for k in keywords):
            links.append(absolute)

    seen = set()
    out = []
    for l in links:
        if l not in seen:
            out.append(l)
            seen.add(l)
        if len(out) >= max_links:
            break
    return out


def try_fetch_sitemap(base_url: str, timeout: int) -> List[str]:
    candidates = [
        urljoin(base_url, "/sitemap.xml"),
        urljoin(base_url, "/sitemap_index.xml"),
        urljoin(base_url, "/sitemap-index.xml"),
    ]

    urls: List[str] = []
    for sm in candidates:
        try:
            _, xmltxt = safe_get(sm, timeout=timeout)
            if not xmltxt:
                continue
            root = ET.fromstring(xmltxt.encode("utf-8", errors="ignore"))
            tag = root.tag.lower()

            if "sitemapindex" in tag:
                sm_locs = []
                for el in root.iter():
                    if el.tag.lower().endswith("loc") and el.text:
                        sm_locs.append(el.text.strip())
                for child in sm_locs[:5]:
                    try:
                        _, child_xml = safe_get(child, timeout=timeout)
                        if not child_xml:
                            continue
                        child_root = ET.fromstring(child_xml.encode("utf-8", errors="ignore"))
                        for el in child_root.iter():
                            if el.tag.lower().endswith("loc") and el.text:
                                u = el.text.strip()
                                if u:
                                    urls.append(u)
                    except Exception:
                        continue

            if "urlset" in tag or ("urlset" in tag and not urls):
                for el in root.iter():
                    if el.tag.lower().endswith("loc") and el.text:
                        u = el.text.strip()
                        if u:
                            urls.append(u)

            if urls:
                break
        except Exception:
            continue

    urls = [u for u in urls if same_domain(base_url, u)]
    seen = set()
    out = []
    for u in urls:
        if u not in seen:
            out.append(u)
            seen.add(u)
    return out


@dataclass
class ScanResult:
    input_url: str
    final_url: str
    domain: str
    company: str
    pages_scanned: int
    org_type: str
    org_conf: float
    geo_hint: str
    errors: str
    emails: List[Dict]


def scan_site(
    start_url: str,
    keywords: List[str],
    max_pages: int,
    delay_s: float,
    timeout: int,
    use_sitemap: bool,
    include_low_value: bool
) -> ScanResult:
    start_url = normalise_url(start_url)
    dom = domain_of(start_url)

    final_url = start_url
    pages_scanned = 0
    errors = ""
    all_text = ""
    company = dom
    found_rows: List[Dict] = []
    visited: Set[str] = set()
    fetch_errors: List[str] = []

    try:
        final_url, home_html = safe_get(start_url, timeout=timeout)
        pages_scanned += 1
        base = build_base(final_url)
        dom = domain_of(final_url) or dom

        company = extract_company_name(home_html, dom)
        home_text = page_text_snippet(home_html)
        all_text += " " + home_text

        targets = guess_key_pages(base)
        if home_html:
            targets += find_relevant_links(final_url, home_html, keywords=keywords, max_links=25)

        if use_sitemap:
            sm_urls = try_fetch_sitemap(base, timeout=timeout)
            if sm_urls:
                intent = ["partner", "sponsor", "sponsorship", "advertis", "media", "press", "brand", "marketing", "investor", "institutional", "contact", "about", "team"]
                sm_filtered = [u for u in sm_urls if any(k in (urlparse(u).path or "").lower() for k in intent)]
                targets += sm_filtered[:25]

        seen = set()
        final_targets = []
        for u in targets:
            if u not in seen and same_domain(base, u):
                final_targets.append(u)
                seen.add(u)

        for url in final_targets:
            if pages_scanned >= max_pages:
                break
            if url in visited:
                continue
            visited.add(url)

            if url != final_url:
                time.sleep(delay_s)

            try:
                _, html = safe_get(url, timeout=timeout)
                pages_scanned += 1
                if not html:
                    continue

                txt = page_text_snippet(html)
                all_text += " " + txt

                soup = BeautifulSoup(html, "html.parser")
                rows = extract_cfemails(soup) + extract_mailto_with_context(soup)
                emails = extract_emails_from_html(html)
                for e in emails:
                    rows.append({"email": e, "context": ""})

                pt = guess_page_type(url)
                for r in rows:
                    em = (r.get("email") or "").strip()
                    if not is_valid_email(em):
                        continue

                    rel = classify_email_relevance(em)
                    if (not include_low_value) and rel == "Low":
                        continue
                    if is_trap_email(em):
                        continue

                    found_rows.append({
                        "email": em,
                        "relevance": rel,
                        "page_type": pt,
                        "page_url": url,
                        "context": (r.get("context") or "")[:300],
                    })

            except Exception as e:
                fetch_errors.append(f"{url} -> {str(e)[:180]}")
                continue

        org_type, org_conf = infer_org_type(all_text)
        geo_hint = geo_hint_from_domain(dom)

        page_rank = {"Partnerships": 5, "Investor Relations": 5, "Contact": 4, "About": 2, "Team": 1, "Homepage": 0, "Other": 0, "Legal": -1, "Careers": -1}
        rel_rank = {"High": 3, "Medium": 2, "Low": 1}

        dedup: Dict[str, Dict] = {}
        for row in found_rows:
            key = row["email"].lower()
            if key not in dedup:
                dedup[key] = row
            else:
                cur = dedup[key]
                cur_key = rel_rank.get(cur["relevance"], 1) * 10 + page_rank.get(cur["page_type"], 0)
                new_key = rel_rank.get(row["relevance"], 1) * 10 + page_rank.get(row["page_type"], 0)
                if new_key > cur_key:
                    dedup[key] = row

        emails_final = list(dedup.values())
        emails_final.sort(key=lambda x: (rel_rank.get(x["relevance"], 1), page_rank.get(x["page_type"], 0)), reverse=True)

        if fetch_errors:
            errors = "; ".join(fetch_errors[:3])

        return ScanResult(
            input_url=start_url,
            final_url=final_url,
            domain=dom,
            company=company,
            pages_scanned=pages_scanned,
            org_type=org_type,
            org_conf=org_conf,
            geo_hint=geo_hint,
            errors=errors,
            emails=emails_final
        )

    except Exception as e:
        errors = str(e)
        org_type, org_conf = "Corporate / Other", 0.2
        geo_hint = geo_hint_from_domain(dom)
        return ScanResult(
            input_url=start_url,
            final_url=start_url,
            domain=dom,
            company=dom,
            pages_scanned=pages_scanned,
            org_type=org_type,
            org_conf=org_conf,
            geo_hint=geo_hint,
            errors=errors,
            emails=[]
        )


# =========================================================
# Sidebar
# =========================================================
with st.sidebar:
    st.markdown("<div class='crg-sidebar-card'>", unsafe_allow_html=True)
    st.markdown("### Scan controls")
    max_pages = st.slider("Max pages per site", 1, 40, 12)
    delay_s = st.slider("Delay between requests (seconds)", 0.0, 3.0, 0.6, 0.1)
    timeout = st.slider("Request timeout (seconds)", 5, 30, 15)
    use_sitemap = st.checkbox("Use sitemap (if available)", value=True)
    include_low_value = st.checkbox("Include low-value inboxes (support/careers/etc.)", value=False)
    st.markdown("---")
    keywords = st.multiselect("Links to follow", DEFAULT_KEYWORDS, DEFAULT_KEYWORDS)
    st.caption("These are path keywords we’ll prioritise when crawling internal pages.")
    st.markdown("</div>", unsafe_allow_html=True)


# =========================================================
# State
# =========================================================
if "emails_df" not in st.session_state:
    st.session_state.emails_df = pd.DataFrame()
if "companies_df" not in st.session_state:
    st.session_state.companies_df = pd.DataFrame()
if "has_scanned" not in st.session_state:
    st.session_state.has_scanned = False
if "last_scan_message" not in st.session_state:
    st.session_state.last_scan_message = ""


# =========================================================
# Tabs
# =========================================================
tab_discover, tab_qualify = st.tabs(["Discover", "Qualify"])


# ----------------------------
# Discover
# ----------------------------
with tab_discover:
    st.markdown("<div class='crg-card'>", unsafe_allow_html=True)
    st.markdown("## Discover")
    st.markdown(f"<div class='crg-subtitle'>Paste target websites (one per line) and run a scan.</div>", unsafe_allow_html=True)

    urls_text = st.text_area(
        "URLs",
        height=180,
        placeholder="https://example.com\nhttps://example.org\nhttps://somefirm.co.uk"
    )

    b1, b2, b3 = st.columns([1, 1, 2])
    with b1:
        run_scan = st.button("Run scan", type="primary")
    with b2:
        clear = st.button("Clear", type="secondary")
    with b3:
        st.caption("Tip: start with a curated list (funds, banks, fintechs, consultancies, data providers).")

    st.markdown("</div>", unsafe_allow_html=True)

    if clear:
        st.session_state.emails_df = pd.DataFrame()
        st.session_state.companies_df = pd.DataFrame()
        st.session_state.has_scanned = False
        st.session_state.last_scan_message = ""
        st.success("Cleared.")

    if run_scan:
        raw_urls = [u.strip() for u in urls_text.splitlines() if u.strip()]
        if not raw_urls:
            st.warning("Paste at least one URL.")
            st.stop()

        progress = st.progress(0)
        status = st.empty()

        all_email_rows = []
        all_company_rows = []

        for i, u in enumerate(raw_urls, start=1):
            status.write(f"Scanning {i}/{len(raw_urls)}: {u}")

            res = scan_site(
                start_url=u,
                keywords=keywords,
                max_pages=max_pages,
                delay_s=delay_s,
                timeout=timeout,
                use_sitemap=use_sitemap,
                include_low_value=include_low_value
            )

            all_company_rows.append({
                "company": res.company,
                "domain": res.domain,
                "geo_hint": res.geo_hint,
                "org_type": res.org_type,
                "org_type_conf": round(res.org_conf, 2),
                "pages_scanned": res.pages_scanned,
                "errors": res.errors or ""
            })

            for e in res.emails:
                all_email_rows.append({
                    "company": res.company,
                    "domain": res.domain,
                    "geo_hint": res.geo_hint,
                    "org_type": res.org_type,
                    "email": e["email"],
                    "email_relevance": e["relevance"],
                    "page_type": e["page_type"],
                    "page_url": e["page_url"],
                    "context": e.get("context", ""),
                })

            progress.progress(i / len(raw_urls))

        st.session_state.companies_df = pd.DataFrame(all_company_rows).drop_duplicates(subset=["domain"])
        st.session_state.emails_df = pd.DataFrame(all_email_rows)
        st.session_state.has_scanned = True

        if st.session_state.emails_df.empty:
            st.session_state.last_scan_message = "Scan completed, but no emails were found (or pages were blocked). Check the errors column."
        else:
            st.session_state.last_scan_message = "Done. Use Qualify to filter down to the best contacts."

    if st.session_state.has_scanned:
        st.info(st.session_state.last_scan_message)

        st.markdown("<div class='crg-card soft'>", unsafe_allow_html=True)
        st.markdown("### Snapshot")
        c1, c2, c3, c4 = st.columns(4)
        with c1:
            st.metric("Domains scanned", int(st.session_state.companies_df.shape[0]) if not st.session_state.companies_df.empty else 0)
        with c2:
            st.metric("Emails found", int(st.session_state.emails_df.shape[0]) if not st.session_state.emails_df.empty else 0)
        with c3:
            st.metric("High relevance", int((st.session_state.emails_df["email_relevance"] == "High").sum()) if not st.session_state.emails_df.empty else 0)
        with c4:
            st.metric("Blocked / errors", int((st.session_state.companies_df["errors"].astype(str).str.len() > 0).sum()) if not st.session_state.companies_df.empty else 0)
        st.markdown("</div>", unsafe_allow_html=True)

        if not st.session_state.companies_df.empty:
            st.markdown("<div class='crg-card soft'>", unsafe_allow_html=True)
            st.markdown("### Sites")
            st.dataframe(
                st.session_state.companies_df.sort_values(["errors", "pages_scanned"], ascending=[True, False]),
                use_container_width=True,
                hide_index=True
            )
            st.markdown("</div>", unsafe_allow_html=True)

        if not st.session_state.emails_df.empty:
            st.markdown("<div class='crg-card soft'>", unsafe_allow_html=True)
            st.markdown("### Emails")
            st.dataframe(
                st.session_state.emails_df,
                use_container_width=True,
                hide_index=True
            )
            st.markdown("</div>", unsafe_allow_html=True)


# ----------------------------
# Qualify
# ----------------------------
with tab_qualify:
    st.markdown("<div class='crg-card'>", unsafe_allow_html=True)
    st.markdown("## Qualify")
    st.markdown(f"<div class='crg-subtitle'>Filter down to the most useful inboxes. Export the final list as CSV.</div>", unsafe_allow_html=True)
    st.markdown("</div>", unsafe_allow_html=True)

    emails_df = st.session_state.emails_df.copy()
    if emails_df.empty:
        st.info("No emails found yet. Go to Discover and run a scan.")
        st.stop()

    st.markdown("<div class='crg-card soft'>", unsafe_allow_html=True)
    col1, col2, col3 = st.columns([1, 1, 1])
    with col1:
        rel_filter = st.multiselect("Email relevance", ["High", "Medium", "Low"], ["High", "Medium"])
    with col2:
        org_filter = st.multiselect("Organisation type", sorted(emails_df["org_type"].dropna().unique().tolist()), [])
    with col3:
        geo_filter = st.multiselect("Geo hint", sorted(emails_df["geo_hint"].dropna().unique().tolist()),
                                    ["UK"] if "UK" in emails_df["geo_hint"].unique() else [])

    filtered = emails_df[emails_df["email_relevance"].isin(rel_filter)]
    if org_filter:
        filtered = filtered[filtered["org_type"].isin(org_filter)]
    if geo_filter:
        filtered = filtered[filtered["geo_hint"].isin(geo_filter)]
    st.markdown("</div>", unsafe_allow_html=True)

    st.markdown("<div class='crg-card soft'>", unsafe_allow_html=True)
    st.dataframe(filtered, use_container_width=True, hide_index=True)
    st.markdown("</div>", unsafe_allow_html=True)

    st.markdown("<div class='crg-card soft'>", unsafe_allow_html=True)
    st.markdown("### Export")
    csv_bytes = filtered.to_csv(index=False).encode("utf-8")
    st.download_button(
        "Download CSV",
        data=csv_bytes,
        file_name="crg_email_discovery.csv",
        mime="text/csv",
    )
    st.markdown("</div>", unsafe_allow_html=True)

st.caption("CRG internal tool. Always double-check emails before outreach.")
