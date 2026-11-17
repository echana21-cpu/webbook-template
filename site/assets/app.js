document.addEventListener('DOMContentLoaded', () => {
  initSidebar();
  initAccordion();
  initMainAccordion();
  initCitationCopy();
  initScriptureRefs();
  initIndexTabs();
  initCnTranslate();
});

// 1. Mobile Sidebar Toggle
function initSidebar() {
  const navToggle = document.getElementById('navToggle');
  const sidebar = document.getElementById('sidebar');
  const backdrop = document.getElementById('backdrop');

  if (navToggle && sidebar && backdrop) {
    navToggle.addEventListener('click', () => {
      sidebar.classList.toggle('open');
      backdrop.hidden = !sidebar.classList.contains('open');
    });

    backdrop.addEventListener('click', () => {
      sidebar.classList.remove('open');
      backdrop.hidden = true;
    });
  }
}

// 2. Citation Copy
function initCitationCopy() {
  const citeBtn = document.getElementById('citeBtn');
  const commentary = document.querySelector('.commentary');

  if (citeBtn && commentary) {
    citeBtn.addEventListener('click', () => {
      const citeText = commentary.getAttribute('data-citation') || 
                       '고은철, 설교 강해';
      navigator.clipboard.writeText(citeText).then(() => {
        showToast('학술 인용문이 클립보드에 복사되었습니다.');
      }).catch(err => {
        showToast('복사에 실패하였습니다.');
      });
    });
  }
}

// 3. 개역개정 성경 구절 팝업 (RefPop)
function initScriptureRefs() {
  const pop = document.getElementById("refpop");
  if (!pop) return;
  let pinned = null;

  const fill = (el) => {
    let verses;
    try { verses = JSON.parse(el.dataset.rv); } catch (_) { return false; }
    if (!verses || !verses.length) return false;

    const rows = verses.map(v => {
      const li = document.createElement("li");
      const n = document.createElement("span"); n.className = "rv-n"; n.textContent = v.r;
      const t = document.createElement("span"); t.className = "rv-t"; t.textContent = v.t;
      li.append(n, t);
      return li.outerHTML;
    }).join("");

    pop.innerHTML =
      `<div class="rv-h"><span class="rv-ref"></span><span class="rv-src">개역개정</span></div>` +
      `<ul class="rv-list">${rows}</ul>`;
    pop.querySelector(".rv-ref").textContent = el.dataset.ref || "성경 참조";
    return true;
  };

  const place = (el) => {
    pop.hidden = false;
    const r = el.getBoundingClientRect();
    const pr = pop.getBoundingClientRect();
    const left = Math.min(Math.max(8, r.left), window.innerWidth - pr.width - 8);
    let top = r.bottom + 8;
    if (top + pr.height > window.innerHeight - 8) {
      top = Math.max(8, r.top - pr.height - 8);
    }
    pop.style.left = `${left}px`;
    pop.style.top = `${top}px`;
  };

  const show = (el) => { if (fill(el)) place(el); };
  const hide = () => { pop.hidden = true; };

  let hideTimer = null;
  const cancelHide = () => { clearTimeout(hideTimer); hideTimer = null; };
  const scheduleHide = () => { cancelHide(); hideTimer = setTimeout(hide, 150); };

  pop.addEventListener("mouseenter", cancelHide);
  pop.addEventListener("mouseleave", () => { if (!pinned) scheduleHide(); });

  document.querySelectorAll(".ref.has-rv").forEach(el => {
    el.tabIndex = 0;
    el.addEventListener("mouseenter", () => { if (!pinned) { cancelHide(); show(el); } });
    el.addEventListener("mouseleave", () => { if (!pinned) scheduleHide(); });
    el.addEventListener("focus", () => { cancelHide(); show(el); });
    el.addEventListener("blur", () => { if (!pinned) scheduleHide(); });
    el.addEventListener("click", (e) => {
      e.preventDefault();
      cancelHide();
      if (pinned === el) { pinned = null; hide(); } else { pinned = el; show(el); }
    });
  });

  document.addEventListener("click", (e) => {
    if (pinned && !e.target.closest(".ref.has-rv") && !e.target.closest("#refpop")) {
      pinned = null; hide();
    }
  });

  window.addEventListener("scroll", () => { if (!pinned) hide(); }, { passive: true });
}

// 4. Toast Notification
function showToast(msg) {
  let toast = document.getElementById('toast');
  if (!toast) {
    toast = document.createElement('div');
    toast.id = 'toast';
    toast.className = 'toast';
    document.body.appendChild(toast);
  }
  toast.textContent = msg;
  toast.hidden = false;
  setTimeout(() => {
    toast.hidden = true;
  }, 2500);
}

// 5. Sidebar Chapter Accordion Toggle
function initAccordion() {
  document.querySelectorAll('.nav-chapter-header').forEach(btn => {
    btn.addEventListener('click', () => {
      const group = btn.closest('.nav-chapter-group');
      if (group) {
        const isOpen = group.classList.contains('open');
        group.classList.toggle('open');
        btn.setAttribute('aria-expanded', !isOpen);
      }
    });
  });
}

// 6. Main Index Chapter Card Accordion Toggle
function initMainAccordion() {
  document.querySelectorAll('.index-chapter-section .chapter-heading').forEach(btn => {
    btn.addEventListener('click', () => {
      const section = btn.closest('.index-chapter-section');
      if (section) {
        const isOpen = section.classList.contains('open');
        section.classList.toggle('open');
        btn.setAttribute('aria-expanded', !isOpen);

        const labelTxt = btn.querySelector('.label-txt');
        const arrow = btn.querySelector('.ch-toggle-arrow');
        if (labelTxt && arrow) {
          const isEn = document.documentElement.lang === 'en';
          labelTxt.textContent = !isOpen ? (isEn ? 'Collapse' : '접기') : (isEn ? 'Expand' : '펼치기');
          arrow.textContent = !isOpen ? '▲' : '▼';
        }
      }
    });
  });
}

// 7. Index Category Tabs (구약 / 신약 / 주제별 신학 강의 / 강의 자료 필터링)
function initIndexTabs() {
  const tabContainer = document.getElementById('indexTabs');
  if (!tabContainer) return;

  const tabBtns = tabContainer.querySelectorAll('.index-tab-btn');
  const catBlocks = document.querySelectorAll('.index-category-block');

  function switchTab(tabType) {
    tabBtns.forEach(b => {
      const isActive = b.getAttribute('data-tab') === tabType;
      b.classList.toggle('active', isActive);
      b.setAttribute('aria-selected', isActive);
    });

    catBlocks.forEach(block => {
      const blockType = block.getAttribute('data-cat-type') || 'sermons';
      if (tabType === 'all') {
        block.classList.remove('tab-hidden');
      } else {
        block.classList.toggle('tab-hidden', blockType !== tabType);
      }
    });
  }

  tabBtns.forEach(btn => {
    btn.addEventListener('click', () => {
      const tab = btn.getAttribute('data-tab');
      switchTab(tab);
    });
  });

  // URL Hash 감지 (#theology, #humanities, #ot, #nt 등)
  function checkHash() {
    const hash = window.location.hash.replace('#', '').replace('cat-', '');
    if (['ot', 'nt', 'theology', 'humanities'].includes(hash)) {
      switchTab(hash);
      const target = document.getElementById(`cat-${hash}`);
      if (target) {
        setTimeout(() => target.scrollIntoView({ behavior: 'smooth' }), 100);
      }
    }
  }

  checkHash();
  window.addEventListener('hashchange', checkHash);
}

// 8. Chinese (CN) Real-time Translation
function initCnTranslate() {
  const cnBtn = document.getElementById('cnTranslateBtn');
  if (!cnBtn) return;

  // 번역 상태 체크 (쿠키 확인)
  function isCnActive() {
    return document.cookie.split(';').some(item => item.trim().startsWith('googtrans=') && item.includes('zh-CN'));
  }

  if (isCnActive()) {
    cnBtn.classList.add('cn-active');
  }

  function loadGoogleTranslateScript(callback) {
    if (window.google && window.google.translate) {
      if (callback) callback();
      return;
    }

    if (!document.getElementById('google_translate_element')) {
      const div = document.createElement('div');
      div.id = 'google_translate_element';
      div.style.display = 'none';
      document.body.appendChild(div);
    }

    window.googleTranslateElementInit = function() {
      new window.google.translate.TranslateElement({
        pageLanguage: 'auto',
        includedLanguages: 'zh-CN,ko,en',
        autoDisplay: false
      }, 'google_translate_element');
      if (callback) callback();
    };

    const script = document.createElement('script');
    script.src = '//translate.google.com/translate_a/element.js?cb=googleTranslateElementInit';
    script.async = true;
    document.head.appendChild(script);
  }

  function setTranslateCookie(val) {
    const domain = window.location.hostname;
    document.cookie = `googtrans=${val}; path=/;`;
    if (domain !== 'localhost' && !domain.includes('127.0.0.1')) {
      document.cookie = `googtrans=${val}; path=/; domain=.${domain};`;
    }
  }

  cnBtn.addEventListener('click', (e) => {
    e.preventDefault();
    if (isCnActive()) {
      // 복원 (번역 해제)
      setTranslateCookie('');
      const domain = window.location.hostname;
      document.cookie = `googtrans=; expires=Thu, 01 Jan 1970 00:00:00 UTC; path=/;`;
      if (domain !== 'localhost') {
        document.cookie = `googtrans=; expires=Thu, 01 Jan 1970 00:00:00 UTC; path=/; domain=.${domain};`;
      }
      cnBtn.classList.remove('cn-active');
      showToast('원문 언어로 복원되었습니다.');
      window.location.reload();
    } else {
      // 중국어로 실시간 번역
      setTranslateCookie('/auto/zh-CN');
      cnBtn.classList.add('cn-active');
      showToast('중국어(中文)로 실시간 번역을 적용합니다...');
      loadGoogleTranslateScript(() => {
        setTimeout(() => {
          const select = document.querySelector('.goog-te-combo');
          if (select) {
            select.value = 'zh-CN';
            select.dispatchEvent(new Event('change'));
          } else {
            window.location.reload();
          }
        }, 300);
      });
    }
  });
}

