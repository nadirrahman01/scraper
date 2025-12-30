import re
import time
import html as htmllib
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from typing import Dict, List, Set, Tuple, Optional
from urllib.parse import urljoin, urlparse

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

import pandas as pd
import streamlit as st
from bs4 import BeautifulSoup


# =========================================================
# CRG / Cordoba Theme (UI)
# =========================================================
CRG = {
    "gold": "#9A690F",
    "gold_dark": "#7F560C",
    "soft": "#FFF7F0",
    "bg": "#0B0E14",
    "panel": "#11151D",
    "text": "#EDEDED",
    "muted": "#9CA3AF",
    "border": "rgba(255,255,255,0.08)",
}

st.set_page_config(
    page_title="CRG | Email Discovery Tool",
    page_icon="📡",
    layout="wide",
    initial_sidebar_state="expanded",
)

st.markdown(
    f"""
<style>
/* Base */
.stApp {{
  background: linear-gradient(180deg, {CRG["bg"]} 0%, #0E1117 100%);
  color: {CRG["text"]};
}}
html, body, [class*="css"] {{
  font-family: -apple-system, BlinkMacSystemFont, "Inter", "Helvetica Neue", Arial, sans-serif;
}}
h1, h2, h3 {{
  font-family: "Times New Roman", Times, serif;
  font-weight: 500;
  letter-spacing: 0.2px;
}}

/* Sidebar */
section[data-testid="stSidebar"] {{
  background-color: {CRG["panel"]};
  border-right: 1px solid {CRG["border"]};
}}
section[data-testid="stSidebar"] h1,
section[data-testid="stSidebar"] h2,
section[data-testid="stSidebar"] h3 {{
  color: {CRG["text"]};
}}

/* Inputs */
textarea, input, select {{
  background-color: {CRG["panel"]} !important;
  border: 1px solid {CRG["border"]} !important;
  border-radius: 12px !important;
}}
div[data-baseweb="textarea"] textarea {{
  border-radius: 12px !important;
}}
div[data-baseweb="input"] input {{
  border-radius: 12px !important;
}}

/* Sliders */
div[data-baseweb="slider"] > div > div {{
  background-color: {CRG["gold"]} !important;
}}

/* Buttons */
.stButton > button {{
  background: {CRG["gold"]};
  color: #0B0E14;
  border: none;
  border-radius: 12px;
  padding: 0.55rem 0.9rem;
  font-weight: 600;
  box-shadow: 0 6px 18px rgba(0,0,0,0.25);
}}
.stButton > button:hover {{
  background: {CRG["gold_dark"]};
  color: #ffffff;
}}
/* Make secondary buttons look neutral (Streamlit uses non-primary buttons as grey by default) */
button[kind="secondary"] {{
  background: transparent !important;
  color: {CRG["text"]} !important;
  border: 1px solid rgba(255,255,255,0.14) !important;
  border-radius: 12px !important;
}}
button[kind="secondary"]:hover {{
  background: rgba(255,255,255,0.04) !important;
}}

/* Tabs */
button[data-baseweb="tab"] {{
  font-weight: 600;
  color: rgba(237,237,237,0.78) !important;
}}
button[data-baseweb="tab"][aria-selected="true"] {{
  color: {CRG["gold"]} !important;
  border-bottom: 2px solid {CRG["gold"]} !important;
}}

/* Metrics */
div[data-testid="stMetric"] {{
  background: rgba(255,255,255,0.03);
  border: 1px solid {CRG["border"]};
  border-radius: 14px;
  padding: 10px 12px;
}}

/* Dataframes */
div[data-testid="stDataFrame"] {{
  border: 1px solid {CRG["border"]};
  border-radius: 14px;
  overflow: hidden;
}}

/* Dividers */
hr {{
  border-color: rgba(255,255,255,0.06);
}}

/* Small utility */
.crg-muted {{
  color: {CRG["muted"]};
}}
.crg-pill {{
  display: inline-block;
  padding: 6px 10px;
  border-radius: 999px;
  border: 1px solid rgba(255,255,255,0.10);
  background: rgba(255,255,255,0.03);
  font-size: 12px;
}}
</style>
""",
    unsafe_allow_html=True,
)

LOGO_PATHS = ["assets/Cordoba Capital Logo (500 x 200 px) (2).png"]
logo_used = False
for p in LOGO_PATHS:
    try:
        st.image(p, height=48)
        logo_used = True
        break
    except Exception:
        pass

st.markdown(
    """
<h1 style="margin-bottom:0.2rem;">CRG Email Discovery Tool</h1>
<p class="crg-muted" style="margin-top:0;">
Paste websites, scan, and extract public contact emails.
<span class="crg-pill" style="margin-left:8px;">Public-source only</span>
<span class="crg-pill" style="margin-left:6px;">Outreach-ready</span>
</p>
""",
    unsafe_allow_html=True,
)


# =========================================================
# Core logic (unchanged)
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
    "abuse", "security", "privacy", "legal", "webmaster", "postmaster", "mailer-daemon", "noreply", "no-reply", "donotreply"
])

ORG_TYPE_KEYWORDS = {
    "Asset Manager": [
        "asset management", "investment management", "portfolio", "aum",
        "fund", "funds", "hedge fund", "private equity", "credit", "fixed income",
        "wealth management", "institutional clients", "asset manager"
    ],
    "Bank": [
        "bank", "banking", "commercial bank", "investment bank", "retail bank",
        "capital markets", "treasury", "lending", "deposit"
    ],
    "Fintech": [
        "fintech", "payments", "api", "digital bank", "neobank", "crypto",
        "blockchain", "trading platform", "brokerage", "risk platform", "saas"
    ],
    "Consulting": [
        "consulting", "advisory", "strategy", "transformation",
        "professional services", "management consulting"
    ],
    "Media / Research": [
        "research", "insights", "analysis", "newsletter", "publication",
        "press", "media", "journalism"
    ],
    "Education": [
        "university", "college", "school", "institute", "students",
        "academic", "alumni"
    ],
}

SPONSOR_LANGUAGE = [
    "sponsor", "sponsorship", "partner", "partnership", "partners",
    "collaborate", "collaboration", "brand partnership", "media kit",
    "press kit", "advertise", "advertising", "work with us", "become a partner",
    "events partner", "strategic partnership"
]

ROLE_HINTS = [
    "head of partnerships", "partnerships manager", "partnership manager",
    "head of marketing", "marketing director", "brand director", "head of brand",
    "head of communications", "communications director", "pr director", "press office",
    "business development", "biz dev", "institutional sales", "client solutions",
    "investor relations", "corporate development", "strategic alliances"
]

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
    if "privacy" in p or "terms" in p or "legal" in p or "imprint" in p or "impressum" in p:
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


def infer_size_proxy(signals: Dict[str, bool], text: str) -> Tuple[str, float]:
    t = (text or "").lower()
    has_careers = signals.get("has_careers_page", False)
    has_team = signals.get("has_team_page", False)
    has_global = any(w in t for w in ["global", "worldwide", "offices", "our offices", "international"])
    has_aum = "aum" in t or "assets under management" in t
    has_clients = "clients" in t or "institutional" in t

    score = 0
    score += 2 if has_careers else 0
    score += 1 if has_team else 0
    score += 2 if has_global else 0
    score += 2 if has_aum else 0
    score += 1 if has_clients else 0

    if score >= 6:
        return "Large / Institutional", 0.8
    if score >= 3:
        return "Mid-sized", 0.65
    return "Small", 0.55


def sponsor_language_score(text: str) -> int:
    t = (text or "").lower()
    return sum(1 for w in SPONSOR_LANGUAGE if w in t)


def confidence_label(pages_scanned: int, org_conf: float, size_conf: float, sponsor_lang_hits: int) -> str:
    c = 0
    c += 1 if pages_scanned >= 6 else 0
    c += 1 if org_conf >= 0.6 else 0
    c += 1 if size_conf >= 0.65 else 0
    c += 1 if sponsor_lang_hits >= 2 else 0
    if c >= 3:
        return "High"
    if c == 2:
        return "Medium"
    return "Low"


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


def context_score(context: str) -> int:
    c = (context or "").lower()
    score = 0
    strong = ["partnership", "partners", "sponsor", "sponsorship", "brand", "marketing",
              "media kit", "press", "advertis", "investor relations", "institutional"]
    medium = ["contact", "enquiry", "inquiry", "collaborat", "work with us", "business development", "biz dev"]
    score += 8 * sum(1 for w in strong if w in c)
    score += 4 * sum(1 for w in medium if w in c)
    return min(40, score)


def extract_mailto_with_context(soup: BeautifulSoup, base_url: str) -> List[Dict]:
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
        results.append({
            "email": em,
            "context": context[:300],
            "context_score": context_score(context)
        })
    return results


def extract_cfemails(soup: BeautifulSoup) -> List[Dict]:
    results = []
    for tag in soup.find_all(attrs={"data-cfemail": True}):
        cfhex = tag.get("data-cfemail") or ""
        decoded = decode_cfemail(cfhex)
        if decoded and is_valid_email(decoded):
            context = " ".join((tag.get_text(" ", strip=True) or "").split())[:200]
            results.append({
                "email": decoded,
                "context": context,
                "context_score": context_score(context)
            })
    return results


def extract_emails_from_html(html: str) -> Set[str]:
    if not html:
        return set()
    text = deobfuscate_text(html)
    emails = set(m.group(0) for m in EMAIL_RE.finditer(text))
    return set(e for e in emails if is_valid_email(e))


def domain_match_bonus(email: str, domain: str) -> int:
    try:
        ed = email.split("@", 1)[1].lower()
    except Exception:
        return 0
    dom = (domain or "").lower()
    free = ("gmail.com", "yahoo.com", "hotmail.com", "outlook.com", "live.com", "icloud.com", "proton.me", "protonmail.com")
    if ed in free:
        return -10
    if dom and (ed == dom or ed.endswith("." + dom) or dom.endswith("." + ed)):
        return 10
    return 0


def extract_role_hints(text: str) -> str:
    t = (text or "").lower()
    hits = []
    for r in ROLE_HINTS:
        if r in t:
            hits.append(r)
    hits = sorted(set(hits))
    return ", ".join(hits[:8])


GUESS_PATHS = [
    "/partnerships", "/partners", "/partner", "/sponsorship", "/sponsor", "/sponsors",
    "/media", "/press", "/advertise", "/advertising", "/brand", "/marketing",
    "/contact", "/contact-us", "/about", "/about-us", "/team", "/people",
    "/investor-relations", "/ir", "/institutional", "/corporate",
    "/contact/", "/about/", "/team/", "/partners/", "/partnerships/"
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


def sponsor_fit_score(
    email_relevance: str,
    org_type: str,
    size_proxy: str,
    geo_hint: str,
    sponsor_lang_hits: int,
    ctx_score: int,
    dom_bonus: int,
) -> int:
    score = 0
    score += {"High": 35, "Medium": 20, "Low": 5}.get(email_relevance, 15)

    if org_type in ("Asset Manager", "Bank", "Fintech", "Consulting"):
        score += 25
    elif org_type in ("Media / Research", "Education"):
        score += 12
    else:
        score += 8

    score += {"Large / Institutional": 20, "Mid-sized": 12, "Small": 6}.get(size_proxy, 8)
    score += min(15, sponsor_lang_hits * 3)
    score += min(20, ctx_score)
    score += dom_bonus

    if geo_hint == "UK":
        score += 8
    elif geo_hint in ("Europe", "Ireland", "Germany", "France", "Netherlands", "Switzerland", "Belgium", "Austria", "Denmark", "Norway", "Sweden", "Finland", "Italy", "Spain", "Portugal", "Poland"):
        score += 5
    else:
        score += 2

    return max(0, min(100, score))


def reason_string(email_relevance: str, page_type: str, ctx_score: int, dom_bonus: int) -> str:
    parts = [f"{email_relevance} relevance", f"found on {page_type} page"]
    if ctx_score >= 12:
        parts.append("strong sponsor context")
    elif ctx_score >= 6:
        parts.append("moderate sponsor context")
    if dom_bonus > 0:
        parts.append("matches company domain")
    elif dom_bonus < 0:
        parts.append("likely personal/free email")
    return "; ".join(parts)


def make_outreach_notes(
    company: str,
    org_type: str,
    size_proxy: str,
    geo_hint: str,
    best_email: str,
    best_email_relevance: str,
    score: int,
    role_hints: str,
    cordoba_profile: Dict[str, str]
) -> str:
    audience = cordoba_profile["audience"]
    universities = cordoba_profile["universities"]
    content = cordoba_profile["content"]
    description = cordoba_profile["description"]

    if org_type in ("Asset Manager", "Bank"):
        angle = "Research sponsorship / partnership"
        value = f"Reach {audience}. Sponsor a short research series, an event, or a guest speaker session."
    elif org_type == "Fintech":
        angle = "Student adoption + pilot"
        value = "Run a workshop, offer student licences, or test a feature with feedback from active users."
    elif org_type == "Consulting":
        angle = "Brand exposure + events"
        value = "Sponsor a case workshop or fireside chat. Good for visibility and meeting strong students."
    elif org_type in ("Media / Research", "Education"):
        angle = "Collaboration + distribution"
        value = "Co-publish a short note series or co-host a speaker."
    else:
        angle = "Exploratory partnership"
        value = "Start simple: a small sponsorship, guest speaker, or one-off collaboration."

    roles_line = f"\nRole hints from their site:\n- {role_hints}\n" if role_hints else ""

    return (
        f"Quick summary:\n"
        f"- Type: {org_type} | Size: {size_proxy} | Geo: {geo_hint}\n"
        f"- Sponsor fit score: {score}/100 (best inbox: {best_email_relevance})\n"
        f"{roles_line}\n"
        f"Cordoba snapshot:\n"
        f"- {description}\n"
        f"- Audience: {audience}\n"
        f"- Universities: {universities}\n"
        f"- Focus: {content}\n\n"
        f"Suggested angle:\n"
        f"- {angle}\n\n"
        f"Why it could work:\n"
        f"- {value}\n\n"
        f"Best contact:\n"
        f"- {best_email}\n"
    )


@dataclass
class ScanResult:
    input_url: str
    final_url: str
    domain: str
    company: str
    pages_scanned: int
    sponsor_lang_hits: int
    org_type: str
    org_conf: float
    size_proxy: str
    size_conf: float
    geo_hint: str
    role_hints: str
    errors: str
    emails: List[Dict]


def scan_site(
    start_url: str,
    keywords: List[str],
    max_pages: int,
    delay_s: float,
    timeout: int,
    use_sitemap: bool,
    allow_low_value: bool
) -> ScanResult:
    start_url = normalise_url(start_url)
    dom = domain_of(start_url)

    signals = {"has_careers_page": False, "has_team_page": False}

    final_url = start_url
    pages_scanned = 0
    errors = ""
    all_text = ""
    sponsor_hits = 0
    company = dom
    role_hints = ""
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
        sponsor_hits += sponsor_language_score(home_text)
        role_hints = extract_role_hints(home_text)

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

                pt = guess_page_type(url)
                if pt == "Careers":
                    signals["has_careers_page"] = True
                if pt == "Team":
                    signals["has_team_page"] = True

                if not html:
                    continue

                txt = page_text_snippet(html)
                all_text += " " + txt
                sponsor_hits += sponsor_language_score(txt)

                if not role_hints:
                    role_hints = extract_role_hints(txt)

                soup = BeautifulSoup(html, "html.parser")

                cf_rows = extract_cfemails(soup)
                mailto_rows = extract_mailto_with_context(soup, base_url=url)
                emails = extract_emails_from_html(html)

                source_rows: List[Dict] = []
                for r in cf_rows + mailto_rows:
                    source_rows.append(r)

                default_ctx = 10 if pt in ("Partnerships", "Investor Relations", "Contact") else 2
                for e in emails:
                    source_rows.append({"email": e, "context": "", "context_score": default_ctx})

                for r in source_rows:
                    e = (r.get("email") or "").strip()
                    if not is_valid_email(e):
                        continue
                    rel = classify_email_relevance(e)

                    if (not allow_low_value) and rel == "Low":
                        continue
                    if is_trap_email(e):
                        continue

                    ctx_s = int(r.get("context_score") or 0)
                    dom_bonus = domain_match_bonus(e, dom)

                    found_rows.append({
                        "email": e,
                        "relevance": rel,
                        "page_url": url,
                        "page_type": pt,
                        "context": (r.get("context") or "")[:300],
                        "context_score": ctx_s,
                        "domain_bonus": dom_bonus
                    })

            except Exception as e:
                fetch_errors.append(f"{url} -> {str(e)[:180]}")
                continue

        org_type, org_conf = infer_org_type(all_text)
        size_proxy, size_conf = infer_size_proxy(signals, all_text)
        geo_hint = geo_hint_from_domain(dom)

        page_type_rank = {
            "Partnerships": 6, "Investor Relations": 6, "Contact": 5, "About": 3, "Team": 2,
            "Homepage": 1, "Other": 0, "Legal": -2, "Careers": -2
        }
        rel_rank = {"High": 3, "Medium": 2, "Low": 1}

        dedup: Dict[str, Dict] = {}
        for row in found_rows:
            email = row["email"].lower()

            score = sponsor_fit_score(
                email_relevance=row["relevance"],
                org_type=org_type,
                size_proxy=size_proxy,
                geo_hint=geo_hint,
                sponsor_lang_hits=sponsor_hits,
                ctx_score=row["context_score"],
                dom_bonus=row["domain_bonus"],
            )

            reason = reason_string(row["relevance"], row["page_type"], row["context_score"], row["domain_bonus"])
            enriched = {
                **row,
                "org_type": org_type,
                "size_proxy": size_proxy,
                "geo_hint": geo_hint,
                "sponsor_language_hits": sponsor_hits,
                "sponsor_fit_score": score,
                "reason": reason,
            }

            if email not in dedup:
                dedup[email] = enriched
            else:
                cur = dedup[email]
                cur_key = cur["sponsor_fit_score"] * 10 + page_type_rank.get(cur["page_type"], 0) + rel_rank.get(cur["relevance"], 1)
                new_key = score * 10 + page_type_rank.get(row["page_type"], 0) + rel_rank.get(row["relevance"], 1)
                if new_key > cur_key:
                    dedup[email] = enriched

        emails_final = list(dedup.values())
        emails_final.sort(key=lambda x: x["sponsor_fit_score"], reverse=True)

        if fetch_errors:
            errors = "; ".join(fetch_errors[:3])

        return ScanResult(
            input_url=start_url,
            final_url=final_url,
            domain=dom,
            company=company,
            pages_scanned=pages_scanned,
            sponsor_lang_hits=sponsor_hits,
            org_type=org_type,
            org_conf=org_conf,
            size_proxy=size_proxy,
            size_conf=size_conf,
            geo_hint=geo_hint,
            role_hints=role_hints,
            errors=errors,
            emails=emails_final
        )

    except Exception as e:
        errors = str(e)
        org_type, org_conf = "Corporate / Other", 0.2
        size_proxy, size_conf = "Small", 0.5
        geo_hint = geo_hint_from_domain(dom)
        return ScanResult(
            input_url=start_url,
            final_url=start_url,
            domain=dom,
            company=dom,
            pages_scanned=pages_scanned,
            sponsor_lang_hits=0,
            org_type=org_type,
            org_conf=org_conf,
            size_proxy=size_proxy,
            size_conf=size_conf,
            geo_hint=geo_hint,
            role_hints="",
            errors=errors,
            emails=[]
        )


# =========================================================
# Streamlit UI (copy/wording upgraded, logic same)
# =========================================================
with st.sidebar:
    st.subheader("Scan controls")
    max_pages = st.slider("Max pages per site (cap)", 1, 40, 12)
    delay_s = st.slider("Delay between requests (seconds)", 0.0, 3.0, 0.6, 0.1)
    timeout = st.slider("Request timeout (seconds)", 5, 30, 15)
    use_sitemap = st.checkbox("Use sitemap (if available)", value=True)
    allow_low_value = st.checkbox("Include generic contact addresses (support/careers/etc.)", value=False)

    keywords = st.multiselect("Links to follow (nav crawl)", DEFAULT_KEYWORDS, DEFAULT_KEYWORDS)

    st.markdown("---")
    st.subheader("Cordoba context (used for notes)")
    cordoba_description = st.text_area(
        "Short description",
        value="Cordoba Research Group is a student-led research and learning platform publishing macro and cross-asset notes, built to help the next generation learn how to think about markets.",
        height=90
    )
    cordoba_audience = st.text_input("Audience", value="students and early-career analysts across UK and Europe")
    cordoba_unis = st.text_input("Universities", value="multi-university network (UK + Europe)")
    cordoba_content = st.text_input("Focus", value="macro, fixed income, EM, commodities, and thematic research")

    cordoba_profile = {
        "description": cordoba_description.strip(),
        "audience": cordoba_audience.strip(),
        "universities": cordoba_unis.strip(),
        "content": cordoba_content.strip()
    }

tab_discover, tab_qualify, tab_outreach = st.tabs(["Discover", "Qualify", "Outreach Prep"])

if "emails_df" not in st.session_state:
    st.session_state.emails_df = pd.DataFrame()
if "companies_df" not in st.session_state:
    st.session_state.companies_df = pd.DataFrame()
if "shortlist_df" not in st.session_state:
    st.session_state.shortlist_df = pd.DataFrame()
if "has_scanned" not in st.session_state:
    st.session_state.has_scanned = False
if "last_scan_message" not in st.session_state:
    st.session_state.last_scan_message = ""


# ----------------------------
# Tab 1: Discover
# ----------------------------
with tab_discover:
    st.subheader("Discover")
    st.write("Paste target websites (one per line) and run a discovery scan.")

    urls_text = st.text_area(
        "URLs",
        height=190,
        placeholder="https://example.com\nhttps://example.org\nhttps://somefirm.co.uk"
    )

    colA, colB, colC = st.columns([1, 1, 2])
    with colA:
        run_scan = st.button("Run discovery scan", type="primary")
    with colB:
        clear = st.button("Clear results")
    with colC:
        st.caption("Tip: start with a curated list (funds, banks, fintechs, consultancies, data providers).")

    if clear:
        st.session_state.emails_df = pd.DataFrame()
        st.session_state.companies_df = pd.DataFrame()
        st.session_state.shortlist_df = pd.DataFrame()
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
                allow_low_value=allow_low_value
            )

            all_company_rows.append({
                "company": res.company,
                "domain": res.domain,
                "geo_hint": res.geo_hint,
                "org_type": res.org_type,
                "org_type_conf": round(res.org_conf, 2),
                "size_proxy": res.size_proxy,
                "size_conf": round(res.size_conf, 2),
                "role_hints": res.role_hints,
                "sponsor_language_hits": res.sponsor_lang_hits,
                "pages_scanned": res.pages_scanned,
                "errors": res.errors or ""
            })

            conf = confidence_label(res.pages_scanned, res.org_conf, res.size_conf, res.sponsor_lang_hits)

            for e in res.emails:
                all_email_rows.append({
                    "company": res.company,
                    "domain": res.domain,
                    "geo_hint": res.geo_hint,
                    "org_type": res.org_type,
                    "size_proxy": res.size_proxy,
                    "role_hints": res.role_hints,
                    "email": e["email"],
                    "email_relevance": e["relevance"],
                    "page_type": e["page_type"],
                    "page_url": e["page_url"],
                    "context": e.get("context", ""),
                    "context_score": int(e.get("context_score", 0)),
                    "sponsor_fit_score": int(e.get("sponsor_fit_score", 0)),
                    "confidence": conf,
                    "reason": e.get("reason", ""),
                    "sponsor_language_hits": res.sponsor_lang_hits
                })

            progress.progress(i / len(raw_urls))

        companies_df = pd.DataFrame(all_company_rows).drop_duplicates(subset=["domain"])
        emails_df = pd.DataFrame(all_email_rows)

        st.session_state.companies_df = companies_df
        st.session_state.emails_df = emails_df
        st.session_state.has_scanned = True

        if emails_df.empty:
            st.session_state.last_scan_message = "Scan completed, but no emails were found (or pages were blocked). Check the errors column."
        else:
            st.session_state.last_scan_message = "Done. Use Qualify to filter down to the best contacts."

    if st.session_state.has_scanned:
        st.info(st.session_state.last_scan_message)

        st.markdown("### Scan snapshot")
        c1, c2, c3, c4 = st.columns(4)
        with c1:
            st.metric("Domains scanned", int(st.session_state.companies_df.shape[0]) if not st.session_state.companies_df.empty else 0)
        with c2:
            st.metric("Emails kept", int(st.session_state.emails_df.shape[0]) if not st.session_state.emails_df.empty else 0)
        with c3:
            st.metric("High relevance", int((st.session_state.emails_df["email_relevance"] == "High").sum()) if not st.session_state.emails_df.empty else 0)
        with c4:
            st.metric("Score ≥ 70", int((st.session_state.emails_df["sponsor_fit_score"] >= 70).sum()) if not st.session_state.emails_df.empty else 0)

        if not st.session_state.companies_df.empty:
            st.dataframe(
                st.session_state.companies_df.sort_values(["errors", "sponsor_language_hits"], ascending=[True, False]),
                use_container_width=True,
                hide_index=True
            )

        if not st.session_state.emails_df.empty:
            st.markdown("### Emails found")
            st.dataframe(
                st.session_state.emails_df.sort_values(["sponsor_fit_score"], ascending=[False]),
                use_container_width=True,
                hide_index=True
            )


# ----------------------------
# Tab 2: Qualify
# ----------------------------
with tab_qualify:
    st.subheader("Qualify")
    st.write("Filter results down to the contacts that look most relevant for partnerships / outreach.")

    emails_df = st.session_state.emails_df.copy()
    if emails_df.empty:
        st.info("No emails found yet. Go back to Discover and check the errors column (some sites block scanning).")
        st.stop()

    col1, col2, col3, col4 = st.columns([1, 1, 1, 1])
    with col1:
        min_score = st.slider("Min sponsor fit score", 0, 100, 70)
    with col2:
        rel_filter = st.multiselect("Email relevance", ["High", "Medium", "Low"], ["High", "Medium"])
    with col3:
        org_filter = st.multiselect(
            "Organisation type",
            sorted(emails_df["org_type"].dropna().unique().tolist()),
            ["Asset Manager", "Bank", "Fintech"] if set(["Asset Manager", "Bank", "Fintech"]).issubset(set(emails_df["org_type"].unique())) else None
        )
    with col4:
        geo_filter = st.multiselect(
            "Geo hint",
            sorted(emails_df["geo_hint"].dropna().unique().tolist()),
            ["UK"] if "UK" in emails_df["geo_hint"].unique() else None
        )

    filtered = emails_df[
        (emails_df["sponsor_fit_score"] >= min_score) &
        (emails_df["email_relevance"].isin(rel_filter))
    ]

    if org_filter:
        filtered = filtered[filtered["org_type"].isin(org_filter)]
    if geo_filter:
        filtered = filtered[filtered["geo_hint"].isin(geo_filter)]

    filtered = filtered.sort_values(["sponsor_fit_score", "email_relevance", "context_score"], ascending=[False, True, False])

    shortlist_view = filtered.copy()
    if "shortlist" not in shortlist_view.columns:
        shortlist_view.insert(0, "shortlist", False)

    edited = st.data_editor(
        shortlist_view[
            ["shortlist", "company", "domain", "org_type", "size_proxy", "geo_hint",
             "email", "email_relevance", "sponsor_fit_score", "confidence",
             "page_type", "page_url", "reason"]
        ],
        use_container_width=True,
        hide_index=True
    )

    add_shortlist = st.button("Save shortlist")
    if add_shortlist:
        picked = edited[edited["shortlist"] == True].copy()
        if picked.empty:
            st.warning("Select at least one row using the shortlist checkbox.")
        else:
            picked = picked.sort_values("sponsor_fit_score", ascending=False)
            picked = picked.drop_duplicates(subset=["domain", "email"], keep="first")
            st.session_state.shortlist_df = picked
            st.success(f"Saved shortlist: {picked.shape[0]} contact(s).")

    st.markdown("### Export filtered results")
    csv_bytes = filtered.to_csv(index=False).encode("utf-8")
    st.download_button("Download filtered CSV", data=csv_bytes, file_name="crg_sponsor_candidates.csv", mime="text/csv")


# ----------------------------
# Tab 3: Outreach Prep
# ----------------------------
with tab_outreach:
    st.subheader("Outreach Prep")

    shortlist = st.session_state.shortlist_df.copy()
    if shortlist.empty:
        st.info("Build and save a shortlist in Qualify first.")
        st.stop()

    shortlist = shortlist.sort_values(["domain", "sponsor_fit_score"], ascending=[True, False])

    per_company_rows = []
    notes_rows = []

    for dom, grp in shortlist.groupby("domain"):
        grp_sorted = grp.sort_values("sponsor_fit_score", ascending=False).reset_index(drop=True)
        best = grp_sorted.iloc[0]
        backups = grp_sorted.iloc[1:3] if len(grp_sorted) > 1 else pd.DataFrame()

        best_email = best["email"]
        best_score = int(best["sponsor_fit_score"])
        org_type = best["org_type"]
        size_proxy = best["size_proxy"]
        geo_hint = best["geo_hint"]
        role_hints = best.get("role_hints", "") or ""

        notes = make_outreach_notes(
            company=best["company"],
            org_type=org_type,
            size_proxy=size_proxy,
            geo_hint=geo_hint,
            best_email=best_email,
            best_email_relevance=best["email_relevance"],
            score=best_score,
            role_hints=role_hints,
            cordoba_profile=cordoba_profile
        )

        backup_list = []
        for _, r in backups.iterrows():
            backup_list.append(f"{r['email']} (score {int(r['sponsor_fit_score'])})")

        per_company_rows.append({
            "company": best["company"],
            "domain": dom,
            "org_type": org_type,
            "size_proxy": size_proxy,
            "geo_hint": geo_hint,
            "recommended_contact": f"{best_email} (score {best_score})",
            "backup_contacts": " | ".join(backup_list) if backup_list else "",
            "role_hints": role_hints
        })

        notes_rows.append({
            "company": best["company"],
            "domain": dom,
            "recommended_contact": best_email,
            "best_score": best_score,
            "outreach_notes": notes
        })

    summary_df = pd.DataFrame(per_company_rows).sort_values("recommended_contact", ascending=True)
    notes_df = pd.DataFrame(notes_rows).sort_values("best_score", ascending=False)

    st.markdown("### Recommended contacts per company")
    st.dataframe(summary_df, use_container_width=True, hide_index=True)

    st.markdown("### Notes")
    chosen = st.selectbox("Select a company", notes_df["company"].tolist())
    chosen_row = notes_df[notes_df["company"] == chosen].iloc[0]
    st.text_area("Outreach notes (copy/paste)", value=chosen_row["outreach_notes"], height=360)

    st.markdown("### Export")
    out_csv = notes_df.to_csv(index=False).encode("utf-8")
    st.download_button("Download outreach notes CSV", data=out_csv, file_name="crg_outreach_notes.csv", mime="text/csv")


st.markdown("---")
st.caption("CRG internal tooling. Always double-check emails before using them.")
