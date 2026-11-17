#!/usr/bin/env python3
"""고은철 목사 마크다운(.md) 설교 원고 기반 정적 웹북 빌드 파이프라인.
sources/ 마크다운 강해 설교를 읽어 site/ 정적 HTML 웹북과 메인 목차, 인터랙티브 지식 그래프를 생성합니다.
개역개정(NKRV) 성경 구절 팝업(66권 전권+약어 지원), 상단 성경본문 박스, 굽은 따옴표, 원어(헬라어/히브리어) 타이포그래피,
H2/H3 계층 대지 및 기도문 박스를 100% 무손실로 렌더링합니다.
"""

import os
import sys
import re
import json
import html
import hashlib
import shutil
import urllib.parse
import unicodedata
from pathlib import Path

PROJ_ROOT = Path(__file__).resolve().parent.parent
MANIFEST_PATH = PROJ_ROOT / "corpus" / "manifest.json"
SITE_DIR = PROJ_ROOT / "site"
BIBLE_DIR = PROJ_ROOT / "bible" / "NKRV"

# 1. 성경 데이터베이스 로딩 (전체 66권 + 한글 약어 + 영문명)
BIBLE_DB = {}
BIBLE_INDEX = {}
ALL_BIBLE_NAMES = []

def load_bible_data():
    global BIBLE_DB, BIBLE_INDEX, ALL_BIBLE_NAMES
    index_file = BIBLE_DIR / "index.json"
    if not index_file.exists():
        print(f"[WARN] 개역개정 성경 index.json이 존재하지 않습니다: {index_file}")
        return

    with open(index_file, "r", encoding="utf-8") as f:
        BIBLE_INDEX = json.load(f)

    names_set = set()
    for b in BIBLE_INDEX.get("books", []):
        book_file = BIBLE_DIR / b["file"]
        if book_file.exists():
            with open(book_file, "r", encoding="utf-8") as f:
                data = json.load(f)
                names = [b["ko"], b["eng"]] + b.get("abbr", []) + b.get("aliases", [])
                for name in names:
                    BIBLE_DB[name] = data
                    names_set.add(name)

    ALL_BIBLE_NAMES = sorted(list(names_set), key=lambda x: -len(x))

load_bible_data()

def parse_verse_range(verses_str):
    """'1-2' -> (1, 2), '1' -> (1, 1), '24-29' -> (24, 29)"""
    if not verses_str:
        return 1, 1
    verses_str = str(verses_str).strip()
    if "-" in verses_str:
        parts = verses_str.split("-")
        return int(parts[0]), int(parts[1])
    elif "~" in verses_str:
        parts = verses_str.split("~")
        return int(parts[0]), int(parts[1])
    else:
        try:
            v = int(verses_str)
            return v, v
        except ValueError:
            return 1, 1

def get_scripture_verses(book_name, chap, start_v, end_v=None):
    if book_name not in BIBLE_DB:
        return []
    book_data = BIBLE_DB[book_name]
    chap_str = str(chap)
    if chap_str not in book_data.get("chapters", {}):
        return []
    
    verses_dict = book_data["chapters"][chap_str]
    abbr_name = book_data.get("ko", book_name)[:2]
    
    if end_v is None:
        end_v = start_v

    res = []
    for v in range(start_v, end_v + 1):
        v_str = str(v)
        if v_str in verses_dict:
            res.append({
                "v": v,
                "r": f"{abbr_name} {chap}:{v}",
                "t": verses_dict[v_str]
            })
    return res

def convert_to_smart_quotes(text, lang="ko"):
    """본문 안의 직선 따옴표(", ')를 출판 타이포그래피용 굽은 따옴표(“ ”, ‘ ’)로 변환"""
    if lang == "en":
        text = re.sub(r'(^|[\s\(\[\{>])"', r'\1“', text)
        text = re.sub(r'"', r'”', text)
        text = re.sub(r"([a-zA-Z0-9])'([a-zA-Z0-9])", r"\1’\2", text)
        text = re.sub(r"([a-zA-Z0-9.,!?])'", r"\1’", text)
        text = re.sub(r"(^|[\s\(\[\{>])'", r'\1‘', text)
        text = re.sub(r"'", r"’", text)
    else:
        text = re.sub(r'"([^"\n]+)"', r'“\1”', text)
        text = re.sub(r'(\s|^)"', r'\1“', text)
        text = re.sub(r"'([^'\n]+)'", r'‘\1’', text)
        text = re.sub(r"(\s|^)'", r'\1‘', text)
    return text

# 66권 전권 및 약어 정규표현식 패턴
if ALL_BIBLE_NAMES:
    _books_pat = r'(?:' + '|'.join(re.escape(k) for k in ALL_BIBLE_NAMES) + r')'
    _scripture_pattern = re.compile(
        rf'(?<![가-힣a-zA-Z0-9])({_books_pat})\s*'
        rf'(?:'
        rf'(\d+)장\s*(\d+)절(?:\s*(?:부터|에서|및|과|와|[\~–\-,])\s*(\d+)절?(?:까지)?)?'
        rf'|'
        rf'(\d+)\s*[:：]\s*(\d+)(?:\s*[\~–\-]\s*(\d+))?'
        rf')'
    )
else:
    _scripture_pattern = None

def transform_scripture_refs(text):
    """본문 안의 성경 구절 인용을 개역개정 팝업 링크(<span class="ref has-rv">)로 변환"""
    if not _scripture_pattern:
        return text

    def repl(m):
        bname = m.group(1)
        if m.group(2) is not None:
            chap = int(m.group(2))
            sv = int(m.group(3))
            ev = int(m.group(4)) if m.group(4) else sv
        else:
            chap = int(m.group(5))
            sv = int(m.group(6))
            ev = int(m.group(7)) if m.group(7) else sv

        raw_text = m.group(0)
        verses = get_scripture_verses(bname, chap, sv, ev)
        if not verses:
            return raw_text

        book_canon = BIBLE_DB[bname].get("ko", bname)
        ref_label = f"{book_canon} {chap}:{sv}" if sv == ev else f"{book_canon} {chap}:{sv}-{ev}"
        json_rv = html.escape(json.dumps(verses, ensure_ascii=False))
        return f'<span class="ref has-rv" data-ref="{ref_label}" data-rv="{json_rv}">{raw_text}</span>'

    return _scripture_pattern.sub(repl, text)

ORIGINAL_LANG_DICT = {
    "크리스토스": "크리스토스(<span class=\"greek\">Χριστός</span>)",
    "메시아": "메시아(<span class=\"hebrew\">מָשִׁיחַ</span>)",
    "둘로스": "둘로스(<span class=\"greek\">δοῦλος</span>)",
    "아포스톨로스": "아포스톨로스(<span class=\"greek\">ἀπόστολος</span>)",
    "디카이오수네": "디카이오수네(<span class=\"greek\">δικαιοσύνη</span>)",
    "유앙겔리온": "유앙겔리온(<span class=\"greek\">εὐαγγέλιον</span>)",
    "카리스": "카리스(<span class=\"greek\">χάρις</span>)",
    "페루심": "페루심(<span class=\"hebrew\">פְּרוּשִׁים</span>)",
    "스캔달론": "스캔달론(<span class=\"greek\">σκάνδαλον</span>)",
    "프로톤": "프로톤(<span class=\"greek\">πρῶτον</span>)",
    "피스티스": "피스티스(<span class=\"greek\">πίστις</span>)",
    "에무나": "에무나(<span class=\"hebrew\">אֱמוּנָה</span>)",
    "아만": "아만(<span class=\"hebrew\">אָמַן</span>)",
    "셰마": "셰마(<span class=\"hebrew\">שְׁמַع</span>)",
    "샤난": "샤난(<span class=\"hebrew\">שָׁנַן</span>)",
    "코데쉬": "코데쉬(<span class=\"hebrew\">קֹדֶשׁ</span>)",
    "카도시": "카도시(<span class=\"hebrew\">קָדוֹשׁ</span>)",
    "크리스티아누스": "크리스티아누스(Christianus)",
    "아노스": "아노스(<span class=\"greek\">-ιανός</span> / Latin: -ianus)",
    "아이노스": "아이노스(<span class=\"greek\">-ιανός</span> / Latin: -ianus)",
}

def transform_original_languages(text, used_keys=None):
    """신학 원어 음차어 최초 1회 병기 및 본문 내 수동 기재된 헬라어/히브리어 문자 서식 보정 (태그 내부 보호)"""
    if used_keys is None:
        used_keys = set()
    text = unicodedata.normalize('NFC', text)
    
    # 1. 신학 용어 음차어 사전 치환 (태그 밖 텍스트 대상)
    for key, val in ORIGINAL_LANG_DICT.items():
        if key in used_keys:
            continue
        pattern = re.compile(rf'(?<![가-힣a-zA-Z\(‘“])({key})(?!\s*[\(（])')
        if pattern.search(text):
            text = pattern.sub(val, text, count=1)
            used_keys.add(key)

    # 2. 태그 분할하여 이미 <span class="greek"> 등 태그 내부에 있는 문자는 중복 태깅 방지
    def repl_greek(m):
        return f'<span class="greek">{m.group(0)}</span>'
    def repl_hebrew(m):
        return f'<span class="hebrew">{m.group(0)}</span>'

    tokens = re.split(r'(<[^>]+>)', text)
    in_greek_span = False
    in_hebrew_span = False
    new_tokens = []
    
    for tok in tokens:
        if tok.startswith('<'):
            if 'class="greek"' in tok or "class='greek'" in tok:
                in_greek_span = True
            elif tok == '</span>' and in_greek_span:
                in_greek_span = False
            elif 'class="hebrew"' in tok or "class='hebrew'" in tok:
                in_hebrew_span = True
            elif tok == '</span>' and in_hebrew_span:
                in_hebrew_span = False
            new_tokens.append(tok)
        else:
            if in_greek_span or in_hebrew_span:
                new_tokens.append(tok)
            else:
                tok = re.sub(r'[\u0370-\u03FF\u1F00-\u1FFF]+', repl_greek, tok)
                tok = re.sub(r'[\u0590-\u05FF]+', repl_hebrew, tok)
                new_tokens.append(tok)

    return unicodedata.normalize('NFC', "".join(new_tokens))

def format_theology_backticks(text):
    """원고의 백틱(`...`) 원어/신학 용어를 모노스페이스 코드가 아닌 미려한 세리프 원어 서식으로 변환"""
    def repl(m):
        content = m.group(1).strip()
        has_greek = any('\u0370' <= c <= '\u03FF' or '\u1F00' <= c <= '\u1FFF' for c in content)
        has_hebrew = any('\u0590' <= c <= '\u05FF' for c in content)
        
        if has_greek and not has_hebrew:
            words = content.split(' ')
            formatted_words = []
            for w in words:
                if any('\u0370' <= c <= '\u03FF' or '\u1F00' <= c <= '\u1FFF' for c in w):
                    formatted_words.append(f'<span class="greek">{w}</span>')
                else:
                    formatted_words.append(f'<span class="orig-term">{w}</span>')
            return " ".join(formatted_words)
        elif has_hebrew and not has_greek:
            words = content.split(' ')
            formatted_words = []
            for w in words:
                if any('\u0590' <= c <= '\u05FF' for c in w):
                    formatted_words.append(f'<span class="hebrew">{w}</span>')
                else:
                    formatted_words.append(f'<span class="orig-term">{w}</span>')
            return " ".join(formatted_words)
        else:
            return f'<span class="orig-term">{html.escape(content)}</span>'

    return re.sub(r'`([^`]+)`', repl, text)

def parse_inline_bold(text):
    return re.sub(r'\*\*(.+?)\*\*', r'<strong>\1</strong>', text)

def format_inline(text, used_orig_keys, lang="ko"):
    # 1. 텍스트 레벨 변환 (스마트 쿼트 및 볼드)
    text = convert_to_smart_quotes(text, lang=lang)
    text = parse_inline_bold(text)
    # 2. 백틱 신학 원어 서식 변환
    text = format_theology_backticks(text)
    # 3. 원어 문자 태깅 및 사전 치환
    text = transform_original_languages(text, used_orig_keys)
    # 4. 성경 참조 팝업 링크 변환
    text = transform_scripture_refs(text)
    return text

def parse_markdown_to_html(md_text, lang="ko"):
    """
    고은철 목사님의 고유 마크다운(.md) 설교 원고를 100% 무손실로 HTML로 변환합니다.
    - H2 대지: ## [서론], ## [본론 1], ## [결론] 등
    - H3 소대지: ### (1), ### [기도문], ### ✝️ [본문 읽기] 등
    - H4 세부항목
    - Blockquote: > *"..."* 성경 구절 및 강조 인용문
    - Prayer Section: ### [기도문] + > 블록 결합 감지 및 .prayer-box 렌더링
    - Lists: 순서형 1. 2. 및 비순서형 - * 리스트
    """
    lines = md_text.strip().split("\n")
    html_out = []
    
    current_list_type = None # 'ul' or 'ol'
    current_blockquote = []
    in_prayer_section = False
    used_orig_keys = set()

    def flush_list():
        nonlocal current_list_type
        if current_list_type:
            html_out.append(f"</{current_list_type}>")
            current_list_type = None

    def flush_blockquote():
        nonlocal current_blockquote, in_prayer_section
        if current_blockquote:
            bq_content = "\n".join(current_blockquote)
            # Remove wrapper quotes/italics if formatted as > *"..."*
            bq_content = re.sub(r'^\s*\*\s*["“]?(.*?)["”]?(?:\s*\*|(?:\s*\*\s*))?$', r'\1', bq_content.strip())
            formatted_bq = format_inline(bq_content, used_orig_keys, lang=lang)
            
            if in_prayer_section:
                html_out.append(f'<div class="prayer-box"><div class="prayer-label">기도문</div><blockquote><p>{formatted_bq}</p></blockquote></div>')
                in_prayer_section = False
            else:
                html_out.append(f'<blockquote><p>{formatted_bq}</p></blockquote>')
            current_blockquote = []

    for idx, raw_line in enumerate(lines):
        line = raw_line.rstrip()
        line_str = line.strip()

        # Blockquote 처리
        if line_str.startswith(">"):
            flush_list()
            bq_line = line_str.lstrip(">").strip()
            # 원고 서두 메타데이터(본문, 제목, 시간 등)는 본문 상단 헤더에서 처리하므로 스킵
            if re.match(r'^\s*\*\*(?:본문|제목|설교 형태|예상 전달 시간|설교 프레임)\*\*', bq_line):
                continue
            current_blockquote.append(bq_line)
            continue
        elif current_blockquote:
            flush_blockquote()

        if not line_str:
            flush_list()
            continue

        # 원고 상단 메타데이터 서두 줄 스킵
        if idx < 10 and (
            line_str.startswith("# ") or
            line_str.startswith("* **본문") or
            line_str.startswith("* 제목:") or
            re.match(r'^[^\#\>\*\-].*정주.*무너지지 않는 삶의 비밀', line_str)
        ):
            continue

        # Headings
        if line_str.startswith("#### "):
            flush_list()
            htext = format_inline(line_str[5:].strip(), used_orig_keys, lang=lang)
            html_out.append(f"<h4>{htext}</h4>")
        elif line_str.startswith("### "):
            flush_list()
            htext_raw = line_str[4:].strip()
            if "기도문" in htext_raw:
                in_prayer_section = True
                continue
            htext = format_inline(htext_raw, used_orig_keys, lang=lang)
            html_out.append(f"<h3>{htext}</h3>")
        elif line_str.startswith("## "):
            flush_list()
            htext = format_inline(line_str[3:].strip(), used_orig_keys, lang=lang)
            html_out.append(f"<h2>{htext}</h2>")
        elif line_str.startswith("---"):
            flush_list()
            continue
        # Numbered List
        elif re.match(r'^\s*\d+\.\s+', line):
            if current_list_type != 'ol':
                flush_list()
                html_out.append("<ol>")
                current_list_type = 'ol'
            item_text = re.sub(r'^\s*\d+\.\s+', '', line).strip()
            formatted_item = format_inline(item_text, used_orig_keys, lang=lang)
            html_out.append(f"<li>{formatted_item}</li>")
        # Unordered List
        elif re.match(r'^\s*[\-\*]\s+', line):
            if current_list_type != 'ul':
                flush_list()
                html_out.append("<ul>")
                current_list_type = 'ul'
            item_text = re.sub(r'^\s*[\-\*]\s+', '', line).strip()
            formatted_item = format_inline(item_text, used_orig_keys, lang=lang)
            html_out.append(f"<li>{formatted_item}</li>")
        else:
            flush_list()
            formatted_p = format_inline(line_str, used_orig_keys, lang=lang)
            html_out.append(f"<p>{formatted_p}</p>")

    flush_list()
    flush_blockquote()

    return "\n".join(html_out)

def render_scripture_box(sec, manifest):
    """각 강해 본문 상단 성경본문 박스 HTML 생성 (개론 제외)"""
    title = sec.get("title", "")
    if title.startswith("00.") or sec.get("is_intro"):
        return ""

    # 책 이름 동적 확인 (섹션별 book_name 우선, manifest 기본값 백업)
    book_name = sec.get("book_name") or manifest.get("book", {}).get("name", "로마서")
    chap = sec.get("chapter", 1)
    sv, ev = parse_verse_range(sec.get("verses", "1"))
    verses = get_scripture_verses(book_name, chap, sv, ev)

    if not verses:
        return ""

    ref_str = f"{book_name} {chap}장 {sv}절" if sv == ev else f"{book_name} {chap}장 {sv}절 ~ {ev}절"

    lines = []
    lines.append('<div class="scripture-box">')
    lines.append('  <div class="sb-header">')
    lines.append('    <span class="sb-title">성경 본문</span>')
    lines.append(f'    <span class="sb-ref">{ref_str} (개역개정)</span>')
    lines.append('  </div>')
    lines.append('  <div class="sb-body">')
    for item in verses:
        lines.append(f'    <p class="sb-verse"><sup class="v-num">{item["v"]}</sup> {item["t"]}</p>')
    lines.append('  </div>')
    lines.append('</div>')
    return "\n".join(lines)

def load_manifest():
    with open(MANIFEST_PATH, "r", encoding="utf-8") as f:
        return json.load(f)

def load_ontology():
    ontology_path = PROJ_ROOT / "corpus" / "ontology.json"
    if not ontology_path.exists():
        return {}
    with open(ontology_path, "r", encoding="utf-8") as f:
        return json.load(f)

def group_sections_by_category_and_series(sections, lang="ko"):
    """sections를 3개 카테고리(구약, 신약, 주제별 신학 강의)와 하위 series/book으로 2단계 그룹화"""
    cat_order = [
        ("OT", "Old Testament" if lang == "en" else "구약"),
        ("NT", "New Testament" if lang == "en" else "신약"),
        ("THEOLOGY", "Thematic Theology Lectures" if lang == "en" else "주제별 신학 강의"),
    ]
    
    grouped = {cat_label: {} for _, cat_label in cat_order}
    
    for sec in sections:
        t = sec.get("testament", "")
        if t == "OT":
            cat_name = "Old Testament" if lang == "en" else "구약"
        elif t == "NT":
            cat_name = "New Testament" if lang == "en" else "신약"
        else:
            cat_name = "Thematic Theology Lectures" if lang == "en" else "주제별 신학 강의"
            
        b_name = sec.get("book_name") or ""
        if lang == "en":
            b_name_en = sec.get("book_name_en") or ""
            if "Matthew" in b_name_en or sec.get("series_en") == "Sermon on the Mount" or "마태" in b_name or sec.get("series") in ["산상수훈", "마태복음"]:
                series_name = "Matthew"
            else:
                series_name = sec.get("series_en") or b_name_en or f"Chapter {sec.get('chapter', 1)}"
        else:
            if "마태" in b_name or sec.get("series") in ["산상수훈", "마태복음"]:
                series_name = "마태복음"
            else:
                series_name = sec.get("series") or b_name or f"{sec.get('chapter', 1)}장"
            
        if series_name not in grouped[cat_name]:
            grouped[cat_name][series_name] = []
        grouped[cat_name][series_name].append(sec)
        
    return grouped

def render_top_header(manifest, active_nav="index", is_subfolder=False, lang="ko", root_prefix=None):
    if root_prefix is None:
        root_prefix = "../" if is_subfolder else ""
    idx_cls = " active" if active_nav == "index" else ""
    theo_cls = " active" if active_nav == "theology" else ""
    lectures_cls = " active" if active_nav == "lectures" else ""
    graph_cls = " active" if active_nav == "graph" else ""

    if lang == "en":
        nav_label = manifest.get("title_en", manifest.get("title", "Pastor Eun-Chul Koh Webbook"))
        idx_text = "Sermons"
        theo_text = "Theology"
        lectures_text = "Lectures"
        graph_text = "Knowledge Graph"
        kr_href = f"{root_prefix}index.html"
        lang_toggle = f'<div class="lang-toggle"><a class="lang-btn" href="{kr_href}">KR</a><span class="lang-btn active">EN</span><button type="button" class="lang-btn" id="cnTranslateBtn" title="中文翻译">CN</button></div>'
    else:
        nav_label = manifest.get("title", "꼬목 강해 설교")
        idx_text = "강해 목차"
        theo_text = "주제별 신학"
        lectures_text = "강의 자료"
        graph_text = "실시간 지식 그래프"
        en_href = f"{root_prefix}en/index.html"
        lang_toggle = f'<div class="lang-toggle"><span class="lang-btn active">KR</span><a class="lang-btn" href="{en_href}">EN</a><button type="button" class="lang-btn" id="cnTranslateBtn" title="中文翻译">CN</button></div>'

    return f'''<header class="top-header">
  <div class="top-header-inner">
    <a class="top-brand" href="{root_prefix}index.html">
      <span class="brand-title">{nav_label}</span>
    </a>
    <nav class="top-nav">
      <a class="top-nav-item{idx_cls}" href="{root_prefix}index.html">{idx_text}</a>
      <a class="top-nav-item{theo_cls}" href="{root_prefix}index.html#theology">{theo_text}</a>
      <a class="top-nav-item{lectures_cls}" href="{root_prefix}lectures.html">{lectures_text}</a>
      <a class="top-nav-item{graph_cls}" href="{root_prefix}graph.html">{graph_text}</a>
      {lang_toggle}
    </nav>
  </div>
</header>'''

def render_theology_graph_card(sec, ontology, is_subfolder=True, lang="ko"):
    """각 강해 본문 하단에 표시되는 실시간 신학 지식그래프 연결 카드"""
    is_en = (lang == "en")
    sec_id = sec["id"]
    
    # 1. 이 세션의 Claim 찾기
    claims = ontology.get("claims", {})
    sec_claims = [cinfo for cid, cinfo in claims.items() if cinfo.get("session_id") == sec_id]
    
    # 2. 관련 개념(Concepts) 추출
    concepts = ontology.get("concepts", {})
    
    card_title = "Theological Knowledge Graph" if is_en else "신학 지식 연결 그래프"
    view_graph_btn = "View Full Graph" if is_en else "전체 그래프 보기"
    desc_text = "This sermon is organically connected through the following theological concepts and redemptive-historical claims:" if is_en else "본 강해는 다음과 같은 신학적 핵심 개념 및 구속사적 명제와 유기적으로 연결되어 있습니다:"
    core_claim_hdr = "Core Claim" if is_en else "핵심 구속사적 명제"
    
    graph_url = "../graph.html" if is_subfolder else "graph.html"
    
    badges_html = []
    for cid, cinfo in concepts.items():
        c_name = cinfo.get("name_en", cinfo["name"]) if is_en else cinfo["name"]
        c_cat = cinfo.get("category_en", cinfo.get("category", "개념")) if is_en else cinfo.get("category", "개념")
        badges_html.append(f'<span class="tg-badge cat">{c_cat}</span><span class="tg-badge">{c_name}</span>')
    
    claim_box_html = ""
    if sec_claims:
        first_claim = sec_claims[0]
        c_text = first_claim.get("claim_en", first_claim.get("claim", "")) if is_en else first_claim.get("claim", "")
        claim_box_html = f'<div class="tg-claim-box"><strong>{core_claim_hdr}:</strong> {c_text}</div>'
    
    network_icon_svg = '<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" style="vertical-align:middle; display:inline-block; margin-right:4px;"><circle cx="18" cy="5" r="3"></circle><circle cx="6" cy="12" r="3"></circle><circle cx="18" cy="19" r="3"></circle><line x1="8.59" y1="13.51" x2="15.42" y2="17.49"></line><line x1="15.41" y1="6.51" x2="8.59" y2="10.49"></line></svg>'

    return f"""
    <div class="theology-graph-card">
      <div class="tg-header">
        <div class="tg-title-wrap">
          <span class="tg-title">{network_icon_svg}{card_title}</span>
        </div>
        <a href="{graph_url}" class="tg-link-btn">{view_graph_btn} &rarr;</a>
      </div>
      <p class="tg-desc">{desc_text}</p>
      <div class="tg-concepts">
        {''.join(badges_html)}
      </div>
      {claim_box_html}
    </div>
    """

def render_sidebar(manifest, active_id=None, is_subfolder=False, lang="ko", root_prefix=None, active_nav=None):
    if root_prefix is None:
        root_prefix = "../" if is_subfolder else ""

    html_parts = []
    html_parts.append('<aside class="sidebar" id="sidebar">')
    html_parts.append('  <div class="side-nav" style="padding-top: 1.25rem;">')
    
    # 4대 핵심 바로가기 버튼 (성경 강해 목차 / 주제별 신학 강의 / 강의 자료실 / 실시간 지식 그래프)
    index_btn_text = "Sermon Index" if lang == "en" else "성경 강해 목차"
    index_rel = f"{root_prefix}index.html"
    bible_icon_svg = '<svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" style="vertical-align:middle; display:inline-block; flex-shrink:0;"><path d="M2 3h6a4 4 0 0 1 4 4v14a3 3 0 0 0-3-3H2z"></path><path d="M22 3h-6a4 4 0 0 0-4 4v14a3 3 0 0 1 3-3h7z"></path></svg>'
    
    theology_btn_text = "Thematic Theology" if lang == "en" else "주제별 신학 강의"
    theology_rel = f"{root_prefix}index.html#theology"
    theology_icon_svg = '<svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" style="vertical-align:middle; display:inline-block; flex-shrink:0;"><path d="M12 2L2 7l10 5 10-5-10-5z"></path><path d="M2 17l10 5 10-5"></path><path d="M2 12l10 5 10-5"></path></svg>'

    lectures_btn_text = "Lecture Materials" if lang == "en" else "강의 자료실"
    lectures_rel = f"{root_prefix}lectures.html"
    book_icon_svg = '<svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" style="vertical-align:middle; display:inline-block; flex-shrink:0;"><path d="M4 19.5A2.5 2.5 0 0 1 6.5 17H20"></path><path d="M6.5 2H20v20H6.5A2.5 2.5 0 0 1 4 19.5v-15A2.5 2.5 0 0 1 6.5 2z"></path></svg>'
    
    graph_btn_text = "Knowledge Graph" if lang == "en" else "실시간 지식 그래프"
    graph_rel = f"{root_prefix}graph.html"
    network_icon_svg = '<svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" style="vertical-align:middle; display:inline-block; flex-shrink:0;"><circle cx="18" cy="5" r="3"></circle><circle cx="6" cy="12" r="3"></circle><circle cx="18" cy="19" r="3"></circle><line x1="8.59" y1="13.51" x2="15.42" y2="17.49"></line><line x1="15.41" y1="6.51" x2="8.59" y2="10.49"></line></svg>'
    
    is_theo_active = (active_nav == "theology") or (active_id and str(active_id).startswith("th-"))
    idx_cls = " active" if (active_nav == "index" and not is_theo_active) else ""
    th_cls = " active" if is_theo_active else ""
    lec_cls = " active" if active_nav == "lectures" else ""
    grp_cls = " active" if active_nav == "graph" else ""

    html_parts.append('    <div class="sidebar-action-btns">')
    html_parts.append(f'      <a class="sidebar-nav-btn{idx_cls}" href="{index_rel}">{bible_icon_svg}<span>{index_btn_text}</span></a>')
    html_parts.append(f'      <a class="sidebar-nav-btn{th_cls}" href="{theology_rel}">{theology_icon_svg}<span>{theology_btn_text}</span></a>')
    html_parts.append(f'      <a class="sidebar-nav-btn{lec_cls}" href="{lectures_rel}">{book_icon_svg}<span>{lectures_btn_text}</span></a>')
    html_parts.append(f'      <a class="sidebar-nav-btn{grp_cls}" href="{graph_rel}">{network_icon_svg}<span>{graph_btn_text}</span></a>')
    html_parts.append('    </div>')
    
    group_title = "Sermon Chapters" if lang == "en" else "세부 강해 목록"
    html_parts.append(f'    <div class="nav-group-title">{group_title}</div>')

    cat_grouped = group_sections_by_category_and_series(manifest.get("sections", []), lang=lang)

    global_open_set = False

    for cat_name, series_dict in cat_grouped.items():
        if not series_dict:
            continue
            
        total_cat_count = sum(len(secs) for secs in series_dict.values())
        count_unit = " sermons" if lang == "en" else "개 강해"
        
        html_parts.append(f'    <div class="nav-category-header">')
        html_parts.append(f'      <span class="cat-title">{cat_name}</span>')
        html_parts.append(f'      <span class="cat-count">{total_cat_count}{count_unit}</span>')
        html_parts.append(f'    </div>')

        for grp_idx, (grp_name, sec_list) in enumerate(series_dict.items()):
            contains_active = any(sec["id"] == active_id for sec in sec_list)

            if active_id is None or active_id == "graph":
                if not global_open_set:
                    is_open = True
                    global_open_set = True
                else:
                    is_open = False
            else:
                is_open = contains_active

            open_cls = " open" if is_open else ""
            aria_exp = "true" if is_open else "false"
            ch_label = grp_name
            count_label = f"{len(sec_list)} sermons" if lang == "en" else f"{len(sec_list)}개 강해"

            html_parts.append(f'    <div class="nav-chapter-group{open_cls}">')
            html_parts.append(f'      <button class="nav-chapter-header" aria-expanded="{aria_exp}">')
            html_parts.append(f'        <span class="ch-title">{ch_label}</span>')
            html_parts.append(f'        <span class="ch-count">{count_label}</span>')
            html_parts.append('        <span class="ch-arrow">▼</span>')
            html_parts.append('      </button>')
            html_parts.append('      <div class="nav-chapter-list">')

            for sec in sec_list:
                is_active = (sec["id"] == active_id)
                active_cls = " active" if is_active else ""
                sec_title = sec.get("title_en", sec["title"]) if lang == "en" else sec["title"]
                
                # 링크 상대경로 계산
                out_key = "output_en" if lang == "en" else "output"
                sec_out = sec.get(out_key, sec.get("output", ""))
                rel_path = str(Path(sec_out).relative_to("site" if lang != "en" else "site/en"))
                rel_link = f"{root_prefix}{rel_path}"

                html_parts.append(f'        <a class="nav-item{active_cls}" href="{rel_link}">')
                html_parts.append(f'          <span>{sec_title}</span>')
                html_parts.append('        </a>')

            html_parts.append('      </div>')
            html_parts.append('    </div>')

    html_parts.append('  </div>')
    html_parts.append('</aside>')
    return "\n".join(html_parts)

def build_section(sec, manifest, ontology, lang="ko"):
    if lang == "en":
        src_key = "source_en"
        out_key = "output_en"
        sec_title = sec.get("title_en", sec["title"])
        site_lang = "en"
        html_lang = "en"
        nav_open = "read"
        assets_prefix = "../../assets"
        script_prefix = "../../assets"
        refpop_label = "ESV Scripture Reference"
        nav_toggle_label = "Index"
        t = sec.get("testament", "")
        series_label = sec.get("series_en") or sec.get("book_name_en") or "Scripture Exposition"
        cat_prefix = "OT" if t == "OT" else ("NT" if t == "NT" else "Theology")
        breadcrumb_text = f"{cat_prefix} · {series_label}"
        citation = f"Eun-Chul Koh, Sermon Commentary: {sec_title}"
    else:
        src_key = "source"
        out_key = "output"
        sec_title = sec["title"]
        site_lang = "ko"
        html_lang = "ko"
        nav_open = "read"
        assets_prefix = "../assets"
        script_prefix = "../assets"
        refpop_label = "개역개정 참조 본문"
        nav_toggle_label = "목차"
        t = sec.get("testament", "")
        series_label = sec.get("series") or sec.get("book_name") or f"{sec.get('chapter', 1)}장"
        cat_prefix = "구약" if t == "OT" else ("신약" if t == "NT" else "주제별 신학")
        breadcrumb_text = f"{cat_prefix} · " + (sec.get("series") or sec.get("book_name") or "본문")
        citation = f"고은철, 설교 강해: {sec_title}"

    src_path = PROJ_ROOT / sec.get(src_key, sec.get("source", ""))
    if not src_path.exists():
        if lang == "en":
            print(f"[SKIP] EN 소스 없음: {src_path}")
            return
        print(f"[WARN] 원천 소스 없음: {src_path}")
        return

    with open(src_path, "r", encoding="utf-8") as f:
        md_text = f.read()

    body_html = parse_markdown_to_html(md_text, lang=lang)
    scripture_box_html = render_scripture_box(sec, manifest) if lang == "ko" else ""
    theology_graph_card = render_theology_graph_card(sec, ontology, is_subfolder=True, lang=lang)
    sidebar_html = render_sidebar(manifest, active_id=sec["id"], is_subfolder=True, lang=lang, active_nav="index")
    top_header_html = render_top_header(manifest, active_nav=nav_open, is_subfolder=True, lang=lang)

    # Per-page KR/EN/CN toggle URL
    if lang == "en":
        kr_out = sec.get("output", "")
        kr_rel = str(Path(kr_out).relative_to("site"))
        lang_toggle_html = f'<div class="lang-toggle"><a class="lang-btn" href="../../{kr_rel}">KR</a><span class="lang-btn active">EN</span><button type="button" class="lang-btn" id="cnTranslateBtn" title="中文翻译">CN</button></div>'
    else:
        en_out = sec.get("output_en")
        if en_out and (PROJ_ROOT / en_out).exists():
            en_rel = str(Path(en_out).relative_to("site/en"))
            lang_toggle_html = f'<div class="lang-toggle"><span class="lang-btn active">KR</span><a class="lang-btn" href="../en/{en_rel}">EN</a><button type="button" class="lang-btn" id="cnTranslateBtn" title="中文翻译">CN</button></div>'
        else:
            lang_toggle_html = f'<div class="lang-toggle"><span class="lang-btn active">KR</span><a class="lang-btn" href="../en/index.html">EN</a><button type="button" class="lang-btn" id="cnTranslateBtn" title="中文翻译">CN</button></div>'

    top_header_html_final = re.sub(
        r'<div class="lang-toggle">.*?</div>',
        lang_toggle_html,
        top_header_html,
        flags=re.DOTALL
    )

    page_html = f"""<!DOCTYPE html>
<html lang="{html_lang}" class="light">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>{sec_title} — {manifest.get('title_en', manifest.get('title')) if lang=='en' else manifest.get('title')}</title>
<link rel="stylesheet" href="{assets_prefix}/style.css">
</head>
<body>
{top_header_html_final}
<button id="navToggle" class="nav-toggle" aria-label="{nav_toggle_label}">{nav_toggle_label}</button>
<div id="backdrop" class="backdrop" hidden></div>
<div class="app">
{sidebar_html}
<div class="main-col">
<div class="wrap">
  <header class="masthead">
    <nav class="breadcrumb"><span>{breadcrumb_text}</span><span class="sep">/</span><span>{series_label}</span></nav>
    <div class="bk">{manifest.get('title_en', manifest.get('title')) if lang=='en' else manifest.get('title')}</div>
    <h1>{sec_title}</h1>
  </header>

  <main class="commentary" data-citation="{citation}">
{scripture_box_html}
{body_html}
{theology_graph_card}
  </main>

  <footer class="colophon">
    <p class="cite">{citation}</p>
  </footer>
</div>
</div>
</div>
<div id="refpop" class="refpop" role="dialog" aria-label="{refpop_label}" hidden></div>
<div id="toast" class="toast" hidden></div>
<script src="{script_prefix}/app.js"></script>
</body>
</html>
"""
    out_path = PROJ_ROOT / sec.get(out_key, sec.get("output", ""))
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with open(out_path, "w", encoding="utf-8") as f:
        f.write(page_html)
    print(f"[OK] 빌드 완료 ({lang.upper()}): {out_path}")

def build_index(manifest, ontology, lang="ko"):
    sidebar_html = render_sidebar(manifest, active_id=None, is_subfolder=False, lang=lang, active_nav="index")
    top_header_html = render_top_header(manifest, active_nav="index", is_subfolder=False, lang=lang)
    cat_grouped = group_sections_by_category_and_series(manifest.get("sections", []), lang=lang)

    is_en = (lang == "en")
    site_title = manifest.get("title_en", manifest.get("title", "")) if is_en else manifest.get("title", "")
    site_desc = manifest.get("description_en", manifest.get("description", "")) if is_en else manifest.get("description", "")
    read_btn_text = "Read" if is_en else "강해 읽기"
    out_dir = SITE_DIR / "en" if is_en else SITE_DIR
    assets_rel = "../assets" if is_en else "assets"
    nav_toggle_label = "Index" if is_en else "목차"
    html_lang = "en" if is_en else "ko"

    # Landing page real-time knowledge graph banner
    graph_box_title = "Real-time Theological Knowledge Graph" if is_en else "실시간 신학 지식 그래프 연결망"
    graph_box_desc = "Explore the organic theological network connecting sermon expositions, biblical concepts, and redemptive-historical claims." if is_en else "성경 강해 설교, 핵심 신학 개념, 구속사적 명제가 유기적으로 연결된 지식망을 실시간으로 탐색합니다."
    graph_box_btn = "Open Interactive Graph" if is_en else "전체 실시간 지식 그래프 열기"
    graph_box_link = "graph.html"

    network_icon_svg = '<svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" style="vertical-align:middle; display:inline-block; margin-right:6px;"><circle cx="18" cy="5" r="3"></circle><circle cx="6" cy="12" r="3"></circle><circle cx="18" cy="19" r="3"></circle><line x1="8.59" y1="13.51" x2="15.42" y2="17.49"></line><line x1="15.41" y1="6.51" x2="8.59" y2="10.49"></line></svg>'

    landing_graph_html = f"""
    <div class="landing-graph-box">
      <div class="lgb-header">
        <span class="lgb-title">{network_icon_svg}{graph_box_title}</span>
        <a href="{graph_box_link}" class="btn" style="background:var(--brand-brown); color:#fff;">{graph_box_btn} &rarr;</a>
      </div>
      <p style="margin:0 0 1rem; color:var(--text-secondary); font-size:0.92rem;">{graph_box_desc}</p>
    </div>
    """

    category_blocks = []
    global_open_idx = 0

    cat_counts = {"ot": 0, "nt": 0, "theology": 0}

    for cat_name, series_dict in cat_grouped.items():
        if not series_dict:
            continue
            
        is_ot = (cat_name in ["Old Testament", "구약"])
        is_nt = (cat_name in ["New Testament", "신약"])
        is_theology = (cat_name in ["Thematic Theology Lectures", "주제별 신학 강의"])

        if is_ot:
            cat_type = "ot"
        elif is_nt:
            cat_type = "nt"
        else:
            cat_type = "theology"

        cat_sermons_cnt = sum(len(secs) for secs in series_dict.values())
        cat_counts[cat_type] = cat_counts.get(cat_type, 0) + cat_sermons_cnt

        cat_meta = f"Total {cat_sermons_cnt} sessions" if is_en else f"총 {cat_sermons_cnt}개 강해 세션"
        
        chapter_blocks = []
        for grp_name, sec_list in series_dict.items():
            cards_html = []
            for sec in sec_list:
                sec_title = sec.get("title_en", sec["title"]) if is_en else sec["title"]
                passage = sec.get("passage_en", sec.get("passage", "")) if is_en else sec.get("passage", "")
                passage_html = f'<div class="card-passage">{passage}</div>' if passage else ''
                
                out_key = "output_en" if is_en else "output"
                sec_out = sec.get(out_key, sec.get("output", ""))
                rel_link = str(Path(sec_out).relative_to("site" if not is_en else "site/en"))

                cards_html.append(f"""
                <div class="sermon-card">
                  {passage_html}
                  <h3 class="card-title"><a href="{rel_link}">{sec_title}</a></h3>
                  <a href="{rel_link}" class="btn card-btn">{read_btn_text}</a>
                </div>
                """)

            is_open = (global_open_idx == 0)
            global_open_idx += 1
            open_cls = " open" if is_open else ""
            aria_exp = "true" if is_open else "false"
            if is_en:
                label_txt = "Collapse" if is_open else "Expand"
                ch_badge = grp_name
                ch_meta = f"{len(sec_list)} sessions"
            else:
                label_txt = "접기" if is_open else "펼치기"
                ch_badge = grp_name
                ch_meta = f"{len(sec_list)}개 강해"
            arrow_txt = "▲" if is_open else "▼"

            chapter_blocks.append(f"""
            <div class="index-chapter-section{open_cls}">
              <button class="chapter-heading" aria-expanded="{aria_exp}">
                <div class="ch-heading-left">
                  <span class="ch-badge">{ch_badge}</span>
                  <span class="ch-meta">{ch_meta}</span>
                </div>
                <span class="ch-toggle-label"><span class="label-txt">{label_txt}</span> <span class="ch-toggle-arrow">{arrow_txt}</span></span>
              </button>
              <div class="chapter-card-grid">
                {''.join(cards_html)}
              </div>
            </div>
            """)

        category_blocks.append(f"""
        <section class="index-category-block" data-cat-type="{cat_type}" id="cat-{cat_type}">
          <div class="index-category-header">
            <h2 class="index-category-title">{cat_name}</h2>
            <span class="index-category-meta">{cat_meta}</span>
          </div>
          {''.join(chapter_blocks)}
        </section>
        """)

    total_all = sum(cat_counts.values())
    tab_all_label = "All Sermons" if is_en else "전체 강해 목차"
    tab_ot_label = "Old Testament" if is_en else "구약 강해"
    tab_nt_label = "New Testament" if is_en else "신약 강해"
    tab_theo_label = "Thematic Theology" if is_en else "주제별 신학 강의"

    index_tabs_html = f"""
    <div class="index-nav-tabs" id="indexTabs" role="tablist">
      <button class="index-tab-btn active" data-tab="all" role="tab" aria-selected="true">
        <span class="tab-label">{tab_all_label}</span>
        <span class="tab-count">{total_all}</span>
      </button>
      <button class="index-tab-btn" data-tab="ot" role="tab" aria-selected="false">
        <span class="tab-label">{tab_ot_label}</span>
        <span class="tab-count">{cat_counts.get('ot', 0)}</span>
      </button>
      <button class="index-tab-btn" data-tab="nt" role="tab" aria-selected="false">
        <span class="tab-label">{tab_nt_label}</span>
        <span class="tab-count">{cat_counts.get('nt', 0)}</span>
      </button>
      <button class="index-tab-btn" data-tab="theology" role="tab" aria-selected="false">
        <span class="tab-label">{tab_theo_label}</span>
        <span class="tab-count">{cat_counts.get('theology', 0)}</span>
      </button>
    </div>
    """

    index_html = f"""<!DOCTYPE html>
<html lang="{html_lang}" class="light">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>{site_title}</title>
<link rel="stylesheet" href="{assets_rel}/style.css">
</head>
<body>
{top_header_html}
<button id="navToggle" class="nav-toggle" aria-label="{nav_toggle_label}">{nav_toggle_label}</button>
<div id="backdrop" class="backdrop" hidden></div>
<div class="app">
{sidebar_html}
<div class="main-col">
<div class="wrap">
  <header class="masthead">
    <h1>{site_title}</h1>
    <div class="byline">{site_desc}</div>
  </header>

  <main class="commentary">
    {landing_graph_html}
    {index_tabs_html}
    {''.join(category_blocks)}
  </main>
</div>
</div>
</div>
<script src="{assets_rel}/app.js"></script>
</body>
</html>
"""
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / "index.html"
    if lang == "ko":
        try:
            if str(PROJ_ROOT) not in sys.path:
                sys.path.insert(0, str(PROJ_ROOT))
            if str(PROJ_ROOT / "tools") not in sys.path:
                sys.path.insert(0, str(PROJ_ROOT / "tools"))
            try:
                from tools.generate_modern_index import build_modern_index_html
            except ImportError:
                from generate_modern_index import build_modern_index_html
            build_modern_index_html(PROJ_ROOT)
        except Exception as e:
            print(f"[WARN] 모던 아카이브 빌더 실행 실패({e}), 템플릿 대체 시도...")
            modern_tpl = PROJ_ROOT / "templates" / "modern_index.html"
            if modern_tpl.exists():
                import shutil
                shutil.copyfile(modern_tpl, out_path)
                print(f"[OK] 모던 아카이브 index.html 템플릿 복사 완료 (KR): {out_path}")
            else:
                with open(out_path, "w", encoding="utf-8") as f:
                    f.write(index_html)
                print(f"[OK] 목차 랜딩 빌드 완료 ({lang.upper()}): {out_path}")
    else:
        with open(out_path, "w", encoding="utf-8") as f:
            f.write(index_html)
        print(f"[OK] 목차 랜딩 빌드 완료 ({lang.upper()}): {out_path}")

import shutil
import urllib.parse

def slugify(text):
    """안전한 파일명/URL 슬러그 생성"""
    text = re.sub(r'[\\/*?:"<>|]', "", text)
    text = re.sub(r'\s+', "_", text.strip())
    return text

def build_all_lecture_documents(manifest, ontology):
    """인물별 신학 강의 및 인문학 강의 마크다운 파일들을 개별 정적 HTML 문서로 빌드"""
    theo_dir = PROJ_ROOT / "sources" / "lectures" / "theology"
    hum_dir = PROJ_ROOT / "sources" / "lectures" / "humanities"
    
    out_lec_dir = SITE_DIR / "lectures"
    if out_lec_dir.exists():
        shutil.rmtree(out_lec_dir, ignore_errors=True)
    out_lec_dir.mkdir(parents=True, exist_ok=True)

    author_ascii_map = {
        "게르할더스 보스": "vos",
        "발트 아이히로트": "eichrodt",
        "칼 바르트": "barth",
        "본회퍼": "bonhoeffer",
        "바르트, 본회퍼 미래신학": "barth-bonhoeffer",
        "폰 라드": "vonrad",
        "판넨베르크": "pannenberg",
        "토마스 아퀴나스": "aquinas",
        "c.s 루이스": "cslewis",
        "키르케고르": "kierkegaard",
        "토마스 라이트": "ntwright",
        "루터": "luther",
        "신(김용규)": "kim-theology",
        "에버하르트 융엘": "jungel"
    }

    lecture_data = {
        "theology_by_author": {},
        "humanities": [],
        "all_docs": []
    }

    # 1. 인물별 신학 강의 마크다운 빌드
    if theo_dir.exists():
        for author_dir in sorted(theo_dir.iterdir()):
            if not author_dir.is_dir():
                continue
            author_name = unicodedata.normalize('NFC', author_dir.name)
            author_key = author_ascii_map.get(author_name, hashlib.md5(author_name.encode('utf-8')).hexdigest()[:6])
            lecture_data["theology_by_author"][author_name] = []

            for md_path in sorted(author_dir.glob("*.md")):
                doc_title = unicodedata.normalize('NFC', md_path.stem)
                doc_hash = hashlib.md5(f"{author_name}:{doc_title}".encode('utf-8')).hexdigest()[:8]
                file_name = f"lec-{author_key}-{doc_hash}.html"
                doc_out_path = out_lec_dir / file_name
                rel_url = f"lectures/{file_name}"

                try:
                    with open(md_path, "r", encoding="utf-8") as f:
                        raw_md = f.read()
                except Exception:
                    continue

                body_html = parse_markdown_to_html(raw_md, lang="ko")
                top_header = render_top_header(manifest, active_nav="lectures", is_subfolder=True, lang="ko")
                sidebar = render_sidebar(manifest, active_id=None, is_subfolder=True, lang="ko", active_nav="lectures")
                citation = f"고은철, 신학 강의 교안: {doc_title} ({author_name})"

                doc_html = f"""<!DOCTYPE html>
<html lang="ko" class="light">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>{doc_title} — {author_name} 신학 강의</title>
<link rel="stylesheet" href="../assets/style.css">
</head>
<body>
{top_header}
<button id="navToggle" class="nav-toggle" aria-label="목차">목차</button>
<div id="backdrop" class="backdrop" hidden></div>
<div class="app">
{sidebar}
<div class="main-col">
<div class="wrap">
  <header class="masthead">
    <nav class="breadcrumb">
      <a href="../lectures.html" style="color:var(--text-muted); text-decoration:none;">강의 자료실</a>
      <span class="sep">/</span>
      <span>{author_name}</span>
    </nav>
    <div class="bk">{author_name} 성경신학 강의 교안</div>
    <h1>{doc_title}</h1>
  </header>

  <main class="commentary" data-citation="{citation}">
    <div class="lecture-doc-banner">
      <span class="lc-badge">인물별 신학 강의</span>
      <span style="font-size:0.88rem; color:var(--text-secondary); margin-left:0.5rem;">연구자: 고은철 목사 · 주제: {author_name}</span>
    </div>
    {body_html}
    <div style="margin-top:2.5rem; padding-top:1.5rem; border-top:1px solid var(--border-color); display:flex; justify-content:space-between; align-items:center;">
      <a href="../lectures.html" class="btn" style="background:var(--brand-brown); color:#fff;">&larr; 강의 자료실 목록으로</a>
      <button id="citeBtn" class="btn" style="background:var(--accent-color); color:#fff;">인용 복사</button>
    </div>
  </main>

  <footer class="colophon">
    <p class="cite">{citation}</p>
  </footer>
</div>
</div>
</div>
<div id="refpop" class="refpop" role="dialog" aria-label="개역개정 참조 본문" hidden></div>
<div id="toast" class="toast" hidden></div>
<script src="../assets/app.js"></script>
</body>
</html>
"""
                with open(doc_out_path, "w", encoding="utf-8") as f:
                    f.write(doc_html)

                doc_info = {
                    "title": doc_title,
                    "author": author_name,
                    "url": rel_url,
                    "category": "theology"
                }
                lecture_data["theology_by_author"][author_name].append(doc_info)
                lecture_data["all_docs"].append(doc_info)

    # 2. 인문학 강의 통합 노트 마크다운 빌드
    if hum_dir.exists():
        for md_path in sorted(hum_dir.glob("*.md")):
            doc_title = unicodedata.normalize('NFC', md_path.stem)
            doc_hash = hashlib.md5(doc_title.encode('utf-8')).hexdigest()[:8]
            file_name = f"lec-hum-{doc_hash}.html"
            doc_out_path = out_lec_dir / file_name
            rel_url = f"lectures/{file_name}"

            try:
                with open(md_path, "r", encoding="utf-8") as f:
                    raw_md = f.read()
            except Exception:
                continue

            body_html = parse_markdown_to_html(raw_md, lang="ko")
            top_header = render_top_header(manifest, active_nav="lectures", is_subfolder=True, lang="ko")
            sidebar = render_sidebar(manifest, active_id=None, is_subfolder=True, lang="ko", active_nav="lectures")
            citation = f"고은철, 인문학 강의 노트: {doc_title}"

            doc_html = f"""<!DOCTYPE html>
<html lang="ko" class="light">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>{doc_title} — 인문학 강의 노트</title>
<link rel="stylesheet" href="../assets/style.css">
</head>
<body>
{top_header}
<button id="navToggle" class="nav-toggle" aria-label="목차">목차</button>
<div id="backdrop" class="backdrop" hidden></div>
<div class="app">
{sidebar}
<div class="main-col">
<div class="wrap">
  <header class="masthead">
    <nav class="breadcrumb">
      <a href="../lectures.html" style="color:var(--text-muted); text-decoration:none;">강의 자료실</a>
      <span class="sep">/</span>
      <span>인문학·철학 통섭 강의</span>
    </nav>
    <div class="bk">인문학 & 서양사상사 강의 노트</div>
    <h1>{doc_title}</h1>
  </header>

  <main class="commentary" data-citation="{citation}">
    <div class="lecture-doc-banner">
      <span class="lc-badge" style="background:rgba(92,59,36,0.08); color:var(--brand-brown);">인문학 강의 노트</span>
      <span style="font-size:0.88rem; color:var(--text-secondary); margin-left:0.5rem;">고은철 목사 서양사상사 & 철학 통합 강의</span>
    </div>
    {body_html}
    <div style="margin-top:2.5rem; padding-top:1.5rem; border-top:1px solid var(--border-color); display:flex; justify-content:space-between; align-items:center;">
      <a href="../lectures.html" class="btn" style="background:var(--brand-brown); color:#fff;">&larr; 강의 자료실 목록으로</a>
      <button id="citeBtn" class="btn" style="background:var(--accent-color); color:#fff;">인용 복사</button>
    </div>
  </main>

  <footer class="colophon">
    <p class="cite">{citation}</p>
  </footer>
</div>
</div>
</div>
<div id="refpop" class="refpop" role="dialog" aria-label="개역개정 참조 본문" hidden></div>
<div id="toast" class="toast" hidden></div>
<script src="../assets/app.js"></script>
</body>
</html>
"""
            with open(doc_out_path, "w", encoding="utf-8") as f:
                f.write(doc_html)

            doc_info = {
                "title": doc_title,
                "author": "인문학·철학",
                "url": rel_url,
                "category": "humanities"
            }
            lecture_data["humanities"].append(doc_info)
            lecture_data["all_docs"].append(doc_info)

    print(f"[OK] 전체 강의 자료 HTML 빌드 완료: 총 {len(lecture_data['all_docs'])}편 문서")
    return lecture_data

def build_lectures_page(manifest, ontology, lecture_data=None, lang="ko"):
    """강의 자료 전용 아카이브 페이지 (index.html과 완전히 동일한 탭/아코디언/카드 그리드 레이아웃)"""
    if lecture_data is None:
        lecture_data = {"theology_by_author": {}, "humanities": [], "all_docs": []}

    is_en = (lang == "en")
    out_dir = SITE_DIR / "en" if is_en else SITE_DIR
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / "lectures.html"

    sidebar_html = render_sidebar(manifest, active_id=None, is_subfolder=is_en, lang=lang, active_nav="lectures")
    top_header_html = render_top_header(manifest, active_nav="lectures", is_subfolder=is_en, lang=lang)
    assets_rel = "../assets" if is_en else "assets"
    nav_toggle_label = "Index" if is_en else "목차"
    html_lang = "en" if is_en else "ko"
    read_btn_text = "Read" if is_en else "강의 읽기"

    theology_by_author = lecture_data.get("theology_by_author", {})
    humanities_docs = lecture_data.get("humanities", [])
    
    theology_docs_cnt = sum(len(l) for l in theology_by_author.values())
    humanities_docs_cnt = len(humanities_docs)
    total_all = theology_docs_cnt + humanities_docs_cnt

    site_title = f"Lecture Archive — {manifest.get('title_en', manifest.get('title'))}" if is_en else f"강의 자료실 — {manifest.get('title')}"
    site_desc = "Pastor Eun-Chul Koh's systematic theological lecture outlines and humanities lecture notes." if is_en else f"고은철 목사(그말씀하나교회)의 인물별 성경신학 강의 교안 및 인문학·철학 통섭 강의록 전문 아카이브 (총 {total_all}편)"

    # Landing page real-time knowledge graph banner
    graph_box_title = "Real-time Theological Knowledge Graph" if is_en else "실시간 신학 지식 그래프 연결망"
    graph_box_desc = "Explore the organic theological network connecting sermon expositions, biblical concepts, and redemptive-historical claims." if is_en else "성경 강해 설교, 신학 강의 교안, 핵심 신학 개념이 유기적으로 연결된 지식망을 실시간으로 탐색합니다."
    graph_box_btn = "Open Interactive Graph" if is_en else "전체 실시간 지식 그래프 열기"
    graph_box_link = "../graph.html" if is_en else "graph.html"

    network_icon_svg = '<svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" style="vertical-align:middle; display:inline-block; margin-right:6px;"><circle cx="18" cy="5" r="3"></circle><circle cx="6" cy="12" r="3"></circle><circle cx="18" cy="19" r="3"></circle><line x1="8.59" y1="13.51" x2="15.42" y2="17.49"></line><line x1="15.41" y1="6.51" x2="8.59" y2="10.49"></line></svg>'

    landing_graph_html = f"""
    <div class="landing-graph-box">
      <div class="lgb-header">
        <span class="lgb-title">{network_icon_svg}{graph_box_title}</span>
        <a href="{graph_box_link}" class="btn" style="background:var(--brand-brown); color:#fff;">{graph_box_btn} &rarr;</a>
      </div>
      <p style="margin:0 0 1rem; color:var(--text-secondary); font-size:0.92rem;">{graph_box_desc}</p>
    </div>
    """

    theo_author_meta = {
        "게르할더스 보스": {"badge": "성경신학 / 구속사", "desc": "구속사적 성경신학의 아버지"},
        "발트 아이히로트": {"badge": "구약신학 / 언약", "desc": "언약 중심의 구약신학 대계"},
        "칼 바르트": {"badge": "현대신학 / 교의학", "desc": "말씀의 신학과 교회 교의학"},
        "본회퍼": {"badge": "기독교윤리 / 제자도", "desc": "값비싼 은혜와 제자도의 대가"},
        "바르트, 본회퍼 미래신학": {"badge": "미래신학 / 교회론", "desc": "기독론적 교회론의 발전"},
        "폰 라드": {"badge": "구약신학 / 전승사", "desc": "전승사 비평과 구약신학"},
        "판넨베르크": {"badge": "조직신학 / 계시론", "desc": "역사로서의 계시와 보편성"},
        "토마스 아퀴나스": {"badge": "고전신학 / 스콜라", "desc": "신학대전과 고전 변증학"},
        "c.s 루이스": {"badge": "기독교 변증학", "desc": "순전한 기독교와 영광의 무게"},
        "키르케고르": {"badge": "실존신학 / 신앙", "desc": "신 앞의 단독자와 실존"},
        "토마스 라이트": {"badge": "신약신학 / 바울", "desc": "바울 신학과 하나님의 승리"},
        "루터": {"badge": "종교개혁 / 복음", "desc": "오직 의인은 믿음으로"},
        "신(김용규)": {"badge": "철학신학 / 신론", "desc": "서양 사상과 신론의 전개"},
        "에버하르트 융엘": {"badge": "신학적 해석학", "desc": "세상의 신비로서의 하나님"}
    }

    # 탭 네비게이션
    tab_all_label = "All Lectures" if is_en else "전체 강의 목차"
    tab_theo_label = "Theology Outlines" if is_en else "인물별 신학 강의"
    tab_hum_label = "Humanities & Philosophy" if is_en else "인문학·철학 강의록"

    index_tabs_html = f"""
    <div class="index-nav-tabs" id="indexTabs" role="tablist">
      <button class="index-tab-btn active" data-tab="all" role="tab" aria-selected="true">
        <span class="tab-label">{tab_all_label}</span>
        <span class="tab-count">{total_all}</span>
      </button>
      <button class="index-tab-btn" data-tab="theology" role="tab" aria-selected="false">
        <span class="tab-label">{tab_theo_label}</span>
        <span class="tab-count">{theology_docs_cnt}</span>
      </button>
      <button class="index-tab-btn" data-tab="humanities" role="tab" aria-selected="false">
        <span class="tab-label">{tab_hum_label}</span>
        <span class="tab-count">{humanities_docs_cnt}</span>
      </button>
    </div>
    """

    category_blocks = []
    global_open_idx = 0

    # 1. 인물별 신학 강의 카테고리 블록
    if theology_by_author:
        theo_chapter_blocks = []
        for author, doc_list in theology_by_author.items():
            meta = theo_author_meta.get(author, {"badge": "신학 강의"})
            badge_name = meta["badge"]

            cards_html = []
            for d in doc_list:
                doc_title = d["title"]
                doc_url = f"../{d['url']}" if is_en else d["url"]
                passage_html = f'<div class="card-passage">{author} · {badge_name}</div>'
                
                cards_html.append(f"""
                <div class="sermon-card">
                  {passage_html}
                  <h3 class="card-title"><a href="{doc_url}">{doc_title}</a></h3>
                  <a href="{doc_url}" class="btn card-btn">{read_btn_text}</a>
                </div>
                """)

            is_open = (global_open_idx == 0)
            global_open_idx += 1
            open_cls = " open" if is_open else ""
            aria_exp = "true" if is_open else "false"
            if is_en:
                label_txt = "Collapse" if is_open else "Expand"
                ch_badge = f"{author} ({badge_name})"
                ch_meta = f"{len(doc_list)} outlines"
            else:
                label_txt = "접기" if is_open else "펼치기"
                ch_badge = f"{author}"
                ch_meta = f"{len(doc_list)}개 강의안"
            arrow_txt = "▲" if is_open else "▼"

            theo_chapter_blocks.append(f"""
            <div class="index-chapter-section{open_cls}">
              <button class="chapter-heading" aria-expanded="{aria_exp}">
                <div class="ch-heading-left">
                  <span class="ch-badge">{ch_badge}</span>
                  <span class="ch-meta">{ch_meta}</span>
                </div>
                <span class="ch-toggle-label"><span class="label-txt">{label_txt}</span> <span class="ch-toggle-arrow">{arrow_txt}</span></span>
              </button>
              <div class="chapter-card-grid">
                {''.join(cards_html)}
              </div>
            </div>
            """)

        cat_title = "Theological Lecture Outlines" if is_en else "인물별 신학 강의 교안"
        cat_meta = f"Total {theology_docs_cnt} outlines ({len(theology_by_author)} scholars)" if is_en else f"총 {theology_docs_cnt}개 강의 교안 ({len(theology_by_author)}명 신학자 연구)"

        category_blocks.append(f"""
        <section class="index-category-block" data-cat-type="theology" id="cat-theology">
          <div class="index-category-header">
            <h2 class="index-category-title">{cat_title}</h2>
            <span class="index-category-meta">{cat_meta}</span>
          </div>
          {''.join(theo_chapter_blocks)}
        </section>
        """)

    # 2. 인문학·철학 통섭 강의록 카테고리 블록
    if humanities_docs:
        hum_cards_html = []
        for d in humanities_docs:
            doc_title = d["title"]
            doc_url = f"../{d['url']}" if is_en else d["url"]
            passage_html = '<div class="card-passage">서양사상사 & 철학</div>' if not is_en else '<div class="card-passage">Humanities & Philosophy</div>'
            
            hum_cards_html.append(f"""
            <div class="sermon-card">
              {passage_html}
              <h3 class="card-title"><a href="{doc_url}">{doc_title}</a></h3>
              <a href="{doc_url}" class="btn card-btn">{read_btn_text}</a>
            </div>
            """)

        is_open = (global_open_idx == 0)
        global_open_idx += 1
        open_cls = " open" if is_open else ""
        aria_exp = "true" if is_open else "false"
        if is_en:
            label_txt = "Collapse" if is_open else "Expand"
            ch_badge = "Humanities & Western Philosophy"
            ch_meta = f"{humanities_docs_cnt} lecture notes"
        else:
            label_txt = "접기" if is_open else "펼치기"
            ch_badge = "인문학·철학 통섭 강의"
            ch_meta = f"{humanities_docs_cnt}개 강의록"
        arrow_txt = "▲" if is_open else "▼"

        hum_chapter_blocks = [f"""
        <div class="index-chapter-section{open_cls}">
          <button class="chapter-heading" aria-expanded="{aria_exp}">
            <div class="ch-heading-left">
              <span class="ch-badge">{ch_badge}</span>
              <span class="ch-meta">{ch_meta}</span>
            </div>
            <span class="ch-toggle-label"><span class="label-txt">{label_txt}</span> <span class="ch-toggle-arrow">{arrow_txt}</span></span>
          </button>
          <div class="chapter-card-grid">
            {''.join(hum_cards_html)}
          </div>
        </div>
        """]

        cat_title = "Humanities & Philosophy Lectures" if is_en else "인문학·철학 통섭 강의록"
        cat_meta = f"Total {humanities_docs_cnt} lecture notes" if is_en else f"총 {humanities_docs_cnt}개 강의록 전문 (서양사상사 및 철학)"

        category_blocks.append(f"""
        <section class="index-category-block" data-cat-type="humanities" id="cat-humanities">
          <div class="index-category-header">
            <h2 class="index-category-title">{cat_title}</h2>
            <span class="index-category-meta">{cat_meta}</span>
          </div>
          {''.join(hum_chapter_blocks)}
        </section>
        """)

    lectures_html = f"""<!DOCTYPE html>
<html lang="{html_lang}" class="light">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>{site_title}</title>
<link rel="stylesheet" href="{assets_rel}/style.css">
</head>
<body>
{top_header_html}
<button id="navToggle" class="nav-toggle" aria-label="{nav_toggle_label}">{nav_toggle_label}</button>
<div id="backdrop" class="backdrop" hidden></div>
<div class="app">
{sidebar_html}
<div class="main-col">
<div class="wrap">
  <header class="masthead">
    <h1>{site_title}</h1>
    <div class="byline">{site_desc}</div>
  </header>

  <main class="commentary">
    {landing_graph_html}
    {index_tabs_html}
    {''.join(category_blocks)}
  </main>
</div>
</div>
</div>
<script src="{assets_rel}/app.js"></script>
</body>
</html>
"""
    modern_lec_tpl = PROJ_ROOT / "templates" / "modern_lectures.html"
    if lang == "ko" and modern_lec_tpl.exists():
        import shutil
        shutil.copyfile(modern_lec_tpl, out_path)
        print(f"[OK] 모던 강의 자료실 리디렉션 적용 완료 (KR): {out_path}")
    else:
        with open(out_path, "w", encoding="utf-8") as f:
            f.write(lectures_html)
        print(f"[OK] 강의 자료실 목차 빌드 완료 ({lang.upper()}): {out_path}")


def build_graph_page(manifest, ontology, lang="ko"):
    is_en = (lang == "en")
    out_dir = SITE_DIR / "en" if is_en else SITE_DIR
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / "graph.html"

    sidebar_html = render_sidebar(manifest, active_id="graph", is_subfolder=is_en, lang=lang, active_nav="graph")
    top_header_html = render_top_header(manifest, active_nav="graph", is_subfolder=is_en, lang=lang)
    assets_rel = "../assets" if is_en else "assets"
    
    page_title = f"Real-time Theological Knowledge Graph — {manifest.get('title_en', manifest.get('title'))}" if is_en else f"실시간 신학 지식 그래프 — {manifest.get('title')}"

    nodes = []
    session_ids = set()
    for sec in manifest.get("sections", []):
        nid = sec["id"]
        session_ids.add(nid)
        if is_en:
            rel_link = str(Path(sec.get("output_en", "")).relative_to("site/en")) if "output_en" in sec else str(Path(sec.get("output", "")).relative_to("site"))
            title_text = sec.get("title_en", sec["title"])
        else:
            rel_link = str(Path(sec.get("output", "")).relative_to("site"))
            title_text = sec["title"]

        nodes.append({
            "id": nid,
            "label": title_text,
            "group": "session",
            "url": rel_link,
            "chapter": sec.get("chapter", 1)
        })

    def norm_id(s):
        if not s:
            return ""
        if s.startswith("concept:"):
            return s
        if s in ontology.get("concepts", {}):
            return f"concept:{s}"
        return s

    nodes = []
    node_ids = set()

    # 1. Session Nodes
    for sec in manifest.get("sections", []):
        nid = sec["id"]
        node_ids.add(nid)
        if is_en:
            rel_link = str(Path(sec.get("output_en", "")).relative_to("site/en")) if "output_en" in sec else str(Path(sec.get("output", "")).relative_to("site"))
            title_text = sec.get("title_en", sec["title"])
        else:
            rel_link = str(Path(sec.get("output", "")).relative_to("site"))
            title_text = sec["title"]

        nodes.append({
            "id": nid,
            "label": title_text,
            "group": "session",
            "url": rel_link,
            "chapter": sec.get("chapter", 1)
        })

    # 2. Concept Nodes
    for cid, cinfo in ontology.get("concepts", {}).items():
        nid = norm_id(cinfo.get("id") or cid)
        node_ids.add(nid)
        if is_en:
            c_label = cinfo.get("name_en", cinfo["name"])
            c_desc = cinfo.get("description_en", cinfo.get("description", ""))
            c_cat = cinfo.get("category_en", cinfo.get("category", "Concept"))
        else:
            c_label = cinfo["name"]
            c_desc = cinfo.get("description", "")
            c_cat = cinfo.get("category", "개념")

        nodes.append({
            "id": nid,
            "label": c_label,
            "group": "concept",
            "category": c_cat,
            "desc": c_desc
        })

    links = []
    # 1. Concept-Concept links
    for cedge in ontology.get("concept_edges", []):
        src = norm_id(cedge.get("source_concept") or cedge.get("source"))
        tgt = norm_id(cedge.get("target_concept") or cedge.get("target"))
        lbl = cedge.get("label_en" if is_en else "label", "")
        if src in node_ids and tgt in node_ids:
            links.append({
                "source": src,
                "target": tgt,
                "relation": cedge.get("relation", "연계"),
                "label": lbl,
                "type": "concept-concept"
            })

    # 2. Claim/Session links
    claims = ontology.get("claims", {})
    for edge in ontology.get("edges", []):
        s_claim = claims.get(edge.get("source_claim"), {})
        t_claim = claims.get(edge.get("target_claim"), {})
        s_sec = s_claim.get("session_id")
        t_sec = t_claim.get("session_id")
        if s_sec in node_ids and t_sec in node_ids:
            lbl = edge.get("label_en" if is_en else "label", "")
            links.append({
                "source": s_sec,
                "target": t_sec,
                "relation": edge.get("relation", "주장 연계"),
                "label": lbl,
                "type": "session-session"
            })

    # 3. Session-Concept associative links
    for sec in manifest.get("sections", []):
        sid = sec["id"]
        for cid in ontology.get("concepts", {}).keys():
            cnid = norm_id(cid)
            if sid in node_ids and cnid in node_ids:
                links.append({
                    "source": sid,
                    "target": cnid,
                    "relation": "포함 개념",
                    "label": "",
                    "type": "session-concept"
                })

    nodes_json = json.dumps(nodes, ensure_ascii=False)
    links_json = json.dumps(links, ensure_ascii=False)

    btn_reset = "Reset" if is_en else "초기화"
    nav_label = "Contents" if is_en else "목차"

    graph_html = f"""<!DOCTYPE html>
<html lang="{lang}" class="light">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>{page_title}</title>
<link rel="stylesheet" href="{assets_rel}/style.css">
<script src="{assets_rel}/d3.v7.min.js"></script>
<style>
.graph-container {{ width: 100%; height: calc(100vh - 4.5rem); position: relative; background: var(--bg-primary); overflow: hidden; }}
svg.graph-svg {{ width: 100%; height: 100%; display: block; }}
.g-node {{ cursor: pointer; stroke: var(--bg-surface); stroke-width: 2.5px; transition: r 0.2s, stroke-width 0.2s; }}
.g-node.session {{ fill: var(--brand-brown); }}
.g-node.concept {{ fill: var(--accent-color); }}
.g-node:hover {{ stroke: var(--accent-hover); stroke-width: 4px; }}
.g-link {{ stroke: var(--border-color); stroke-opacity: 0.7; stroke-width: 2px; }}
.g-link.session-concept {{ stroke-dasharray: 4,4; stroke-opacity: 0.45; stroke-width: 1.5px; }}
.g-label {{ font-family: var(--font-sans); font-size: 0.82rem; font-weight: 600; fill: var(--text-primary); pointer-events: none; text-shadow: 0 1px 3px rgba(255,255,255,0.9); }}
.graph-ctrls {{ position: absolute; top: 1.2rem; right: 1.2rem; z-index: 10; display: flex; gap: 0.5rem; }}
.graph-legend {{ position: absolute; bottom: 1.5rem; left: 1.5rem; z-index: 10; background: var(--bg-surface); border: 1px solid var(--border-color); border-radius: 8px; padding: 0.75rem 1rem; box-shadow: var(--shadow-sm); font-family: var(--font-sans); font-size: 0.8rem; display: flex; flex-direction: column; gap: 0.4rem; }}
.legend-item {{ display: flex; align-items: center; gap: 0.5rem; }}
.legend-dot {{ width: 12px; height: 12px; border-radius: 50%; display: inline-block; }}
.legend-dot.session {{ background: var(--brand-brown); }}
.legend-dot.concept {{ background: var(--accent-color); }}
.graph-tooltip {{ position: absolute; display: none; background: var(--bg-surface); border: 1px solid var(--border-color); padding: 0.75rem 1rem; border-radius: 8px; box-shadow: var(--shadow-md); font-family: var(--font-sans); font-size: 0.85rem; z-index: 100; max-width: 300px; pointer-events: none; line-height: 1.5; }}
</style>
</head>
<body>
{top_header_html}
<button id="navToggle" class="nav-toggle" aria-label="{nav_label}">{nav_label}</button>
<div id="backdrop" class="backdrop" hidden></div>
<div class="app">
{sidebar_html}
<div class="main-col" style="padding:0; width:100%;">
  <div class="graph-container">
    <div class="graph-ctrls">
      <button class="btn" onclick="zoomIn()">+</button>
      <button class="btn" onclick="zoomOut()">-</button>
      <button class="btn" onclick="resetZoom()">{btn_reset}</button>
    </div>
    <div class="graph-legend">
      <div class="legend-item"><span class="legend-dot session"></span><strong>{'Sermon Exposition' if is_en else '성경 강해 설교'}</strong></div>
      <div class="legend-item"><span class="legend-dot concept"></span><strong>{'Theological Concept' if is_en else '핵심 신학 개념'}</strong></div>
    </div>
    <div id="graphTooltip" class="graph-tooltip"></div>
    <svg class="graph-svg" id="graphSvg"></svg>
  </div>
</div>
</div>
<script>
const nodesData = {nodes_json};
const linksData = {links_json};

const container = document.querySelector(".graph-container");
const width = container.clientWidth || window.innerWidth;
const height = container.clientHeight || (window.innerHeight - 70);

const svg = d3.select("#graphSvg")
  .attr("width", width)
  .attr("height", height);

const g = svg.append("g");
const zoom = d3.zoom().scaleExtent([0.2, 4]).on("zoom", (e) => g.attr("transform", e.transform));
svg.call(zoom);

const simulation = d3.forceSimulation(nodesData)
  .force("link", d3.forceLink(linksData).id(d => d.id).distance(140))
  .force("charge", d3.forceManyBody().strength(-400))
  .force("center", d3.forceCenter(width / 2, height / 2))
  .force("collision", d3.forceCollide().radius(50));

const link = g.append("g")
  .selectAll("line")
  .data(linksData)
  .join("line")
  .attr("class", d => "g-link " + (d.type || ""));

const node = g.append("g")
  .selectAll("circle")
  .data(nodesData)
  .join("circle")
  .attr("class", d => "g-node " + d.group)
  .attr("r", d => d.group === "session" ? 16 : 12)
  .call(d3.drag()
    .on("start", dragstarted)
    .on("drag", dragged)
    .on("end", dragended));

const label = g.append("g")
  .selectAll("text")
  .data(nodesData)
  .join("text")
  .attr("class", "g-label")
  .attr("dx", 18)
  .attr("dy", 5)
  .text(d => d.label);

const tooltip = d3.select("#graphTooltip");
node.on("mouseover", (event, d) => {{
  const desc = d.desc ? `<div style="margin-top:4px; color:var(--text-secondary);">${{d.desc}}</div>` : "";
  const cat = d.category ? `<div style="font-size:0.75rem; color:var(--accent-color); font-weight:700; text-transform:uppercase;">${{d.category}}</div>` : "";
  tooltip.html(`${{cat}}<strong>${{d.label}}</strong>${{desc}}`)
    .style("left", (event.clientX + 14) + "px")
    .style("top", (event.clientY + 14) + "px")
    .style("display", "block");
}}).on("mouseout", () => {{
  tooltip.style("display", "none");
}}).on("click", (event, d) => {{
  if (d.url) window.location.href = d.url;
}});

simulation.on("tick", () => {{
  link
    .attr("x1", d => d.source.x)
    .attr("y1", d => d.source.y)
    .attr("x2", d => d.target.x)
    .attr("y2", d => d.target.y);
  node
    .attr("cx", d => d.x)
    .attr("cy", d => d.y);
  label
    .attr("x", d => d.x)
    .attr("y", d => d.y);
}});

function dragstarted(event, d) {{
  if (!event.active) simulation.alphaTarget(0.3).restart();
  d.fx = d.x;
  d.fy = d.y;
}}
function dragged(event, d) {{
  d.fx = event.x;
  d.fy = event.y;
}}
function dragended(event, d) {{
  if (!event.active) simulation.alphaTarget(0);
  d.fx = null;
  d.fy = null;
}}

function zoomIn() {{ svg.transition().duration(300).call(zoom.scaleBy, 1.3); }}
function zoomOut() {{ svg.transition().duration(300).call(zoom.scaleBy, 0.7); }}
function resetZoom() {{ svg.transition().duration(300).call(zoom.transform, d3.zoomIdentity); }}
</script>
<script src="{assets_rel}/app.js"></script>
</body>
</html>
"""
    with open(out_path, "w", encoding="utf-8") as f:
        f.write(graph_html)
    print(f"[OK] 지식 연결 그래프 페이지 완료 ({lang.upper()}): {out_path}")

def main():
    manifest = load_manifest()
    ontology = load_ontology()

    # 1. 강의 자료 전체 문서(377편) 및 PDF 빌드
    lecture_data = build_all_lecture_documents(manifest, ontology)

    # 2. KR 빌드
    for sec in manifest.get("sections", []):
        build_section(sec, manifest, ontology, lang="ko")
    build_index(manifest, ontology, lang="ko")
    build_lectures_page(manifest, ontology, lecture_data=lecture_data, lang="ko")
    build_graph_page(manifest, ontology, lang="ko")

    # 3. EN 빌드
    for sec in manifest.get("sections", []):
        build_section(sec, manifest, ontology, lang="en")
    build_index(manifest, ontology, lang="en")
    build_lectures_page(manifest, ontology, lecture_data=lecture_data, lang="en")
    build_graph_page(manifest, ontology, lang="en")

    print(f"고은철 목사 설교 웹북 빌드 완료! (KR + EN + {len(lecture_data['all_docs'])}편 강의 자료)")

if __name__ == "__main__":
    main()
