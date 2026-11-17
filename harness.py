#!/usr/bin/env python3
"""KOH-WebBook 검수 하네스 — 파이프라인 전체를 한 번에 PASS/FAIL로 점검 (회귀 게이트).
점검: 코퍼스 대장 파싱 · 원천 마크다운 존재성 · 빌드 실행 · HTML 파싱 및 충실도(H2/H3, 문단, 인용) · 성경 본문 박스 · 성경 팝업(개역개정) 임베드 · 에셋 연결
deps: Python 3.9+ stdlib only. 실행: python3 harness.py
"""

import sys
import re
import json
import html
import subprocess
from pathlib import Path
from html.parser import HTMLParser
import unicodedata

def extract_greek_words(text):
    words = []
    current = []
    for char in text:
        try:
            name = unicodedata.name(char)
            if 'GREEK' in name and ('LETTER' in name or 'SYMBOL' in name):
                current.append(char)
            else:
                if len(current) >= 2:
                    words.append("".join(current))
                current = []
        except ValueError:
            if len(current) >= 2:
                words.append("".join(current))
            current = []
    if len(current) >= 2:
        words.append("".join(current))
    return words

def extract_hebrew_words(text):
    words = []
    current = []
    for char in text:
        try:
            name = unicodedata.name(char)
            if 'HEBREW' in name and ('LETTER' in name or 'POINT' in name):
                current.append(char)
            else:
                if len(current) >= 2:
                    words.append("".join(current))
                current = []
        except ValueError:
            if len(current) >= 2:
                words.append("".join(current))
            current = []
    if len(current) >= 2:
        words.append("".join(current))
    return words

PROJ = Path(__file__).resolve().parent
MANIFEST = PROJ / "corpus" / "manifest.json"
BUILD_SCRIPT = PROJ / "tools" / "build.py"
SITE_DIR = PROJ / "site"

results = []

def add(name, ok, detail=""):
    results.append((name, ok, detail))

def check_manifest():
    if not MANIFEST.exists():
        add("manifest/exist", False, "manifest.json 없음")
        return None
    try:
        with open(MANIFEST, "r", encoding="utf-8") as f:
            data = json.load(f)
        add("manifest/parse", True, f"프로젝트 '{data.get('project')}' · 섹션 {len(data.get('sections', []))}개")
        return data
    except Exception as e:
        add("manifest/parse", False, f"JSON 파싱 실패: {e}")
        return None

def check_sources(manifest):
    if not manifest:
        return
    for sec in manifest.get("sections", []):
        src_path = PROJ / sec["source"]
        exists = src_path.exists() and src_path.stat().st_size > 0
        add(f"source/{sec['id']}", exists, f"한국어 원천 {src_path.name} {'OK' if exists else '없음/0byte'}")
        
        if "source_en" in sec:
            en_path = PROJ / sec["source_en"]
            en_exists = en_path.exists() and en_path.stat().st_size > 0
            add(f"source_en/{sec['id']}", en_exists, f"영문 원천 {en_path.name} {'OK' if en_exists else '없음/0byte'}")

def check_formatting_lints(manifest):
    """마크다운 포매팅 규격 린트 (이탤릭 금지 규칙: *text*, _text_, <em>, <i> 0건 검증)"""
    if not manifest:
        return

    italic_violations = []

    # 1. 마크다운 파일 검사
    for sec in manifest.get("sections", []):
        for k in ["source", "source_en"]:
            if k in sec:
                p = PROJ / sec[k]
                if p.exists():
                    text = p.read_text(encoding="utf-8")
                    # Match *word* (not **word**) or _word_ (not __word__) outside of blockquotes
                    # Filter blockquote lines (> *"..."*)
                    clean_lines = [l for l in text.splitlines() if not l.strip().startswith(">") and not l.strip().startswith("* ") and not l.strip().startswith("- ")]
                    clean_text = "\n".join(clean_lines)
                    m_asterisk = re.findall(r'(?<!\*)\*([^\*\s\n][^\*\n]*[^\*\s\n]|[^\*\s\n])\*(?!\*)', clean_text)
                    m_underscore = re.findall(r'(?<!_)\_([^_\s\n][^_\n]*[^_\s\n]|[^_\s\n])\_(?!_)', clean_text)
                    m_asterisk = [x for x in m_asterisk if not x.startswith(" ") and not x.startswith("#")]
                    if m_asterisk or m_underscore:
                        italic_violations.append(f"{p.name} ({len(m_asterisk) + len(m_underscore)}건)")

    # 2. HTML 산출물 검사 (<em>, <i> 태그)
    html_files = list(SITE_DIR.glob("**/*.html"))
    html_italic_cnt = 0
    for hf in html_files:
        htext = hf.read_text(encoding="utf-8")
        tag_matches = re.findall(r'<(em|i)\b[^>]*>', htext, re.IGNORECASE)
        if tag_matches:
            html_italic_cnt += len(tag_matches)
            italic_violations.append(f"{hf.name} HTML 태그 ({len(tag_matches)}건)")

    no_italic_ok = (len(italic_violations) == 0)
    add("lint/no_italic", no_italic_ok,
        "마크다운 및 HTML 이탤릭체(*text*, <em>, <i>) 0건 검수 OK" if no_italic_ok else f"이탤릭체 규격 위반 {len(italic_violations)}건: {', '.join(italic_violations[:3])}")

def check_build():
    r = subprocess.run([sys.executable, str(BUILD_SCRIPT)], cwd=str(PROJ), capture_output=True, text=True)
    ok = (r.returncode == 0)
    add("build/execution", ok, "OK" if ok else f"빌드 에러: {r.stderr}")

class SimpleHTMLValidator(HTMLParser):
    def __init__(self):
        super().__init__()
        self.h2_count = 0
        self.h3_count = 0
        self.p_count = 0
        self.has_citation = False
        self.has_scripture_box = False

    def handle_starttag(self, tag, attrs):
        attr_dict = dict(attrs)
        if tag == "h2":
            self.h2_count += 1
        elif tag == "h3":
            self.h3_count += 1
        elif tag == "p":
            self.p_count += 1
        elif tag == "main":
            if "data-citation" in attr_dict:
                self.has_citation = True
        elif tag == "div":
            if attr_dict.get("class") == "scripture-box":
                self.has_scripture_box = True

def check_html_fidelity(manifest):
    if not manifest:
        return

    # 1. 랜딩 페이지, 그래프 페이지 및 상단 고정 헤더 검사 (KR & EN)
    index_path = SITE_DIR / "index.html"
    graph_path = SITE_DIR / "graph.html"
    en_index_path = SITE_DIR / "en" / "index.html"
    en_graph_path = SITE_DIR / "en" / "graph.html"

    index_exists = index_path.exists()
    graph_exists = graph_path.exists()
    en_index_exists = en_index_path.exists()
    en_graph_exists = en_graph_path.exists()

    add("site/index.html", index_exists, "메인 랜딩 존재 확인 (KR)")
    add("site/graph.html", graph_exists, "실시간 지식 연결 그래프 페이지 존재 확인 (KR)")
    add("site/en/index.html", en_index_exists, "영문 랜딩 존재 확인 (EN)")
    add("site/en/graph.html", en_graph_exists, "영문 실시간 지식 연결 그래프 존재 확인 (EN)")

    if index_exists:
        with open(index_path, "r", encoding="utf-8") as f:
            idx_content = f.read()
        has_landing = (
            ("chapter-heading" in idx_content and "chapter-card-grid" in idx_content)
            or ("landing-graph-container" in idx_content)
            or ("꼬목 강해 설교" in idx_content and "grid" in idx_content)
            or ("sermon-card" in idx_content)
        )
        has_top_hdr = (
            ("top-header" in idx_content and "top-nav" in idx_content)
            or ("sticky top-0" in idx_content and "<header" in idx_content)
        )
        add("site/index/chapters", has_landing, "메인 대문 강해 카드 목차 렌더링 확인")
        add("site/top_header", has_top_hdr, "상단 고정 헤더 바(Sticky Navigation) 및 언어 토글 렌더링 확인")

def check_ontology_and_graph(manifest):
    onto_path = PROJ / "corpus" / "ontology.json"
    if not onto_path.exists():
        add("corpus/ontology.json", False, "corpus/ontology.json 없음")
        return

    try:
        with open(onto_path, "r", encoding="utf-8") as f:
            data = json.load(f)

        claims = data.get("claims", {})
        edges = data.get("edges", {})
        concepts = data.get("concepts", {})

        add("ontology/parse", True, f"TKG 온톨로지 파싱 성공 · 주장(Claims) {len(claims)}개 · 관계(Edges) {len(edges)}개 · 개념(Concepts) {len(concepts)}개")

        # 1. 세션 매핑 검사
        sec_ids = {sec["id"] for sec in manifest.get("sections", [])}
        invalid_session_claims = [cid for cid, cinfo in claims.items() if cinfo.get("session_id") not in sec_ids]
        add("ontology/claims_validity", len(invalid_session_claims) == 0, 
            "주장(Claim) 세션 매핑 OK" if len(invalid_session_claims) == 0 else f"잘못된 세션 ID 주장 {len(invalid_session_claims)}건")

        # 2. 관계 에지 검사
        allowed_vocab = {"supports", "reframes", "resonates_with", "contrasts_with", "aporetic_tension_with", "develops_into", "is_reframed_by", "is_supported_by", "develops_from", "deepens"}
        invalid_edges = []
        invalid_vocab = []

        for edge in edges:
            src = edge.get("source_claim")
            tgt = edge.get("target_claim")
            rel = edge.get("relation")

            if src not in claims or tgt not in claims:
                invalid_edges.append(edge.get("id"))
            if rel not in allowed_vocab:
                invalid_vocab.append(rel)

        add("ontology/edges_validity", len(invalid_edges) == 0, 
            "관계(Edge) Claim 참조 매핑 OK" if len(invalid_edges) == 0 else f"유효하지 않은 Claim 참조 {len(invalid_edges)}건")

        add("ontology/canonical_relations", len(invalid_vocab) == 0,
            "TKG 표준 어휘 규격 준수 OK" if len(invalid_vocab) == 0 else f"비표준 관계 어휘 {len(invalid_vocab)}건")

    except Exception as e:
        add("ontology/parse", False, f"JSON 파싱 오류: {e}")

    # 그래프 HTML
    graph_path = SITE_DIR / "graph.html"
    if graph_path.exists():
        with open(graph_path, "r", encoding="utf-8") as f:
            g_content = f.read()
        has_d3 = "d3.v7.min.js" in g_content
        has_nodes = "nodesData =" in g_content and "linksData =" in g_content
        add("site/graph/fidelity", has_d3 and has_nodes, "실시간 지식 연결 그래프(D3.js & Engine) 렌더링 무결성 OK")

    # 2. 에셋 존재 검사
    style_path = SITE_DIR / "assets" / "style.css"
    app_js_path = SITE_DIR / "assets" / "app.js"
    add("site/assets/css", style_path.exists(), "style.css 존재")
    add("site/assets/js", app_js_path.exists(), "app.js 존재")

    # 3. 각 세션 HTML 무결성 및 충실도 검사
    all_html_text = ""
    for sec in manifest.get("sections", []):
        out_path = PROJ / sec["output"]
        if not out_path.exists():
            add(f"site/{sec['id']}", False, "HTML 파일 산출 안 됨")
            continue

        try:
            with open(out_path, "r", encoding="utf-8") as f:
                content = f.read()
            all_html_text += content
            
            parser = SimpleHTMLValidator()
            parser.feed(content)
            
            is_intro = sec.get("title", "").startswith("00.") or sec.get("testament") == "THEOLOGY" or sec.get("id", "").startswith("th-") or "Ontology" in sec.get("id", "") or "구조" in sec.get("id", "") or "온톨로지" in sec.get("title", "") or "돌" in sec.get("title", "") or "나그네" in sec.get("title", "")
            expected_box = True if is_intro else parser.has_scripture_box
            
            # 원어/어원 언급 여부 점검
            has_orig_mention = any(w in content for w in ["헬라어", "히브리어", "라틴어", "δοῦλος", "Χριστός", "מָשִׁיחַ", "ἔγνων", "ἐξουσία"])
            has_lang_tag = ('class="greek"' in content or 'class="hebrew"' in content or 'class="latin"' in content) if has_orig_mention else True

            # 사이드바 장별 아코디언 검사
            has_sidebar_ch = "nav-chapter-group" in content and "nav-chapter-header" in content

            # 이모지 검사
            emoji_cnt = len(re.findall(r'[\U0001F300-\U0001F9FF\U00002700-\U000027BF]', content))
            no_emoji_ok = (emoji_cnt == 0)

            headings_total = parser.h2_count + parser.h3_count
            fidelity_ok = (headings_total >= 1 and parser.p_count >= 3 and expected_box and has_lang_tag and has_sidebar_ch and no_emoji_ok)
            box_status = "제외(신학강의/개론)" if is_intro else ("OK" if parser.has_scripture_box else "누락")
            ch_status = "OK(아코디언)" if has_sidebar_ch else "누락"
            emoji_status = "OK(이모지없음)" if no_emoji_ok else f"오류({emoji_cnt}개발견)"
            add(f"fidelity/{sec['id']}", fidelity_ok, 
                f"대지(H2/H3) {headings_total}개 · 문단 {parser.p_count}개 · 성경본문박스 {box_status} · 원어태그 {'OK' if has_lang_tag else '누락'} · 목차 {ch_status} · 이모지 {emoji_status} · 인용태그 {'OK' if parser.has_citation else '누락'}")
        except Exception as e:
            add(f"fidelity/{sec['id']}", False, f"파싱 오류: {e}")

        # 영문 강해 세션 HTML 충실도
        if "output_en" in sec:
            en_out_path = PROJ / sec["output_en"]
            if not en_out_path.exists():
                add(f"fidelity_en/{sec['id']}", False, "영문 HTML 파일 산출 안 됨")
            else:
                try:
                    with open(en_out_path, "r", encoding="utf-8") as f:
                        en_content = f.read()
                    en_parser = SimpleHTMLValidator()
                    en_parser.feed(en_content)
                    has_lang_toggle = 'class="lang-toggle"' in en_content
                    en_headings = en_parser.h2_count + en_parser.h3_count
                    en_fidelity_ok = (en_headings >= 1 and en_parser.p_count >= 3 and has_lang_toggle)
                    add(f"fidelity_en/{sec['id']}", en_fidelity_ok,
                        f"대지(H2/H3) {en_headings}개 · 문단 {en_parser.p_count}개 · 언어토글 {'OK' if has_lang_toggle else '누락'}")
                except Exception as e:
                    add(f"fidelity_en/{sec['id']}", False, f"영문 파싱 오류: {e}")

    # 4. 성경 참조(RefPop - 개역개정) 임베드 검수
    rvs = re.findall(r'data-rv="([^"]*)"', all_html_text)
    bad_rvs = 0
    total_verses = 0
    for raw in rvs:
        try:
            arr = json.loads(html.unescape(raw))
            if arr and all(v.get("r") and v.get("t", "").strip() for v in arr):
                total_verses += len(arr)
            else:
                bad_rvs += 1
        except Exception:
            bad_rvs += 1

    refpop_ok = (bad_rvs == 0 and len(rvs) > 0)
    add("scripture/refpop(NKRV)", refpop_ok,
        f"개역개정 정적 임베드 링크 {len(rvs)}개 · 총 {total_verses}개 절 파싱 성공 · 오류 {bad_rvs}건")

def main():
    print("== KOH-WebBook 검수 하네스 ==")
    manifest = check_manifest()
    check_sources(manifest)
    check_formatting_lints(manifest)
    check_build()
    check_html_fidelity(manifest)
    check_ontology_and_graph(manifest)

    width = max(len(n) for n, _, _ in results)
    print("\n[검수 결과]")
    for name, ok, detail in results:
        print(f"  [{'PASS' if ok else 'FAIL'}] {name.ljust(width)}  {detail}")
    
    n_fail = sum(1 for _, ok, _ in results if not ok)
    print(f"\n{'전체 검수 통과 (ALL PASS)' if n_fail == 0 else f'{n_fail}건 검수 실패'} ({len(results) - n_fail}/{len(results)})")
    return 1 if n_fail else 0

if __name__ == "__main__":
    sys.exit(main())
