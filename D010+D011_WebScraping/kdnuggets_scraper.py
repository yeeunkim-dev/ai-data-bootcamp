"""
KDnuggets 기사 수집기 (AI·데이터 기술 트렌드 파악용)

수집 항목: 제목, URL, 요약문, 저자, 발행일(UTC), 카테고리, 태그, 수집일
수집 방식: ① WordPress REST API (구조화된 JSON, 가장 안정적)
           ② 실패 시 RSS 피드로 대체 (최신 10~20건 정도만 제공)

필요 패키지: requests, beautifulsoup4, pandas  (Anaconda 기본 포함)
실행: python kdnuggets_scraper.py
"""
import html
import re
import time
import urllib.robotparser
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime

import pandas as pd
import requests
from bs4 import BeautifulSoup

BASE = "https://www.kdnuggets.com"
HEADERS = {"User-Agent": "Mozilla/5.0 (personal study project)"}
DELAY = 1.0          # 요청 간 대기(초) - 서버 부담 줄이기
MAX_PAGES = 4        # API 페이지 수 (페이지당 50건 → 최대 200건)
PER_PAGE = 50
COLUMNS = ["title", "url", "summary", "author", "published", "category", "tags", "collected_at"]


def is_allowed(url: str) -> bool:
    """robots.txt 에서 수집이 허용된 경로인지 확인"""
    rp = urllib.robotparser.RobotFileParser(f"{BASE}/robots.txt")
    try:
        rp.read()
    except Exception:
        return True  # robots.txt 를 못 읽으면 진행 (직접 확인 권장)
    return rp.can_fetch(HEADERS["User-Agent"], url)


def clean_text(raw: str) -> str:
    """HTML 태그·엔티티 제거 후 공백 정리"""
    if not raw:
        return ""
    text = BeautifulSoup(raw, "html.parser").get_text(" ", strip=True)
    text = re.sub(r"\s+", " ", html.unescape(text)).strip()
    return text.replace("The post appeared first on KDnuggets.", "").strip()


def now_str() -> str:
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


# ① WordPress REST API ------------------------------------------------------
def collect_via_api() -> list[dict]:
    endpoint = f"{BASE}/wp-json/wp/v2/posts"
    if not is_allowed(endpoint):
        print("robots.txt 에서 API 경로가 허용되지 않아 건너뜁니다.")
        return []

    rows, collected_at = [], now_str()
    for page in range(1, MAX_PAGES + 1):
        try:
            r = requests.get(
                endpoint,
                params={"per_page": PER_PAGE, "page": page, "_embed": 1},
                headers=HEADERS,
                timeout=20,
            )
        except requests.RequestException as e:
            print(f"API 요청 실패: {e}")
            break
        if r.status_code != 200:        # 마지막 페이지를 넘기면 400 반환
            break
        posts = r.json()
        if not posts:
            break

        for p in posts:
            emb = p.get("_embedded", {})
            authors = [a.get("name", "") for a in emb.get("author", []) if "name" in a]
            terms = [t for group in emb.get("wp:term", []) for t in group]
            cats = [t.get("name", "") for t in terms if t.get("taxonomy") == "category"]
            # 카테고리는 대부분 "Originals"라 주제 분석에는 태그가 더 유용함
            tags = [t.get("name", "") for t in terms if t.get("taxonomy") == "post_tag"]
            rows.append({
                "title": clean_text(p["title"]["rendered"]),
                "url": p.get("link", ""),
                "summary": clean_text(p.get("excerpt", {}).get("rendered", "")),
                "author": ", ".join(authors),
                "published": p.get("date_gmt", ""),   # UTC 기준
                "category": ", ".join(cats),
                "tags": ", ".join(tags),
                "collected_at": collected_at,
            })
        print(f"API {page}페이지: {len(posts)}건")
        time.sleep(DELAY)
    return rows


# ② RSS 피드 (대체 경로) ----------------------------------------------------
def collect_via_rss() -> list[dict]:
    feed_url = f"{BASE}/feed"
    try:
        r = requests.get(feed_url, headers=HEADERS, timeout=20)
        r.raise_for_status()
    except requests.RequestException as e:
        print(f"RSS 요청 실패: {e}")
        return []

    ns = {"dc": "http://purl.org/dc/elements/1.1/"}
    root = ET.fromstring(r.content)
    rows, collected_at = [], now_str()
    for item in root.iter("item"):
        pub = item.findtext("pubDate", "")
        try:
            pub = parsedate_to_datetime(pub).astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S")
        except (TypeError, ValueError):
            pass
        rows.append({
            "title": clean_text(item.findtext("title", "")),
            "url": item.findtext("link", ""),
            "summary": clean_text(item.findtext("description", "")),
            "author": item.findtext("dc:creator", "", ns),
            "published": pub,
            # RSS의 category 에는 카테고리와 태그가 섞여 있음
            "category": ", ".join(c.text for c in item.findall("category") if c.text),
            "tags": "",  # RSS에서는 카테고리와 구분되지 않아 비워 둠
            "collected_at": collected_at,
        })
    return rows


def main():
    rows, source = collect_via_api(), "REST API"
    if not rows:
        print("API 수집 결과가 없어 RSS 로 전환합니다.")
        rows, source = collect_via_rss(), "RSS"
    if not rows:
        print("수집 실패: 사이트 구조가 바뀌었거나 접근이 차단됐을 수 있어요.")
        return

    df = pd.DataFrame(rows, columns=COLUMNS).drop_duplicates(subset="url")
    df["published"] = pd.to_datetime(df["published"], errors="coerce")
    df = df.sort_values("published", ascending=False).reset_index(drop=True)

    fname = f"kdnuggets_articles_{datetime.now():%Y%m%d}.csv"
    df.to_csv(fname, index=False, encoding="utf-8-sig")  # 엑셀에서 한글 깨짐 방지

    print(f"\n[{source}] {len(df)}건 저장 → {fname}")
    print(f"기간: {df['published'].min()} ~ {df['published'].max()}")
    print(df[["published", "title", "category"]].head(10).to_string())


if __name__ == "__main__":
    main()