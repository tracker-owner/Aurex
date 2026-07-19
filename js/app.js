document.addEventListener('DOMContentLoaded', () => {
    const $ = (id) => document.getElementById(id);
    const $$ = (sel) => document.querySelectorAll(sel);

    const spotlight = $('spotlight');
    const toast = $('toast');
    const toastText = $('toastText');

    let currentUser = JSON.parse(localStorage.getItem('arcanum_user')) || null;
    let currentSearchType = 'username'; 

    function escapeHtml(text) {
        if (typeof text !== 'string') return text;
        const map = { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#039;' };
        return text.replace(/[&<>"']/g, m => map[m]);
    }

    const translations = {
        ru: {
            nav_modules: "Модули разведки", nav_breach: "Поиск утечек", nav_domain: "Анализ доменов", nav_ip: "IP Инфраструктура",
            nav_system: "Система", nav_payments: "Покупки", credits: "Кредиты", account: "Аккаунт", logout: "Выйти", login: "Вход", register: "Регистрация",
            hero_badge_breach: "14.8 МЛРД ЗАПИСЕЙ · РЕАЛЬНОЕ ВРЕМЯ", hero_title_breach: "Поиск по <span class='accent'>утечкам баз данных</span><br>в реальном времени.",
            hero_sub_breach: "",
            target_query: "Целевой запрос", execute: "Выполнить", filter_type: "Фильтр по типу", results: "Результаты поиска", no_probes: "Запросы не выполнялись",
            no_probes_desc: "Введите запрос выше и нажмите «Выполнить».", hero_badge_domain: "ПАССИВНЫЙ DNS · WHOIS · ПОДДОМЕНЫ", hero_title_domain: "Перечисление <span class='accent'>инфраструктуры домена</span><br>за секунды.",
            target_domain: "Целевой домен", resolve: "Найти", hero_badge_ip: "ASN · ПОРТЫ · ГЕОЛОКАЦИЯ", hero_title_ip: "Анализ <span class='accent'>IP инфраструктуры</span><br>в масштабе.",
            target_ip: "Целевой IP", scan: "Сканировать", awaiting_target: "Ожидание цели", auth_welcome: "С возвращением. Пожалуйста, введите данные.",
            email: "Почта", username: "Имя пользователя", password: "Пароль", no_account: "Нет аккаунта?", upgrade_plan: "Улучшить тариф",
            upgrade_desc: "Кредиты тратятся за запросы. Тарифы Pro и Enterprise — это подписка на месяц.", one_time: "Единоразово", per_month: "/ в месяц", 
            free_f1: "10 кредитов каждый день", free_f2: "10 кредитов за один поиск", free_f3: "Базовый поиск утечек", free_f4: "Community support", current_plan: "Текущий тариф", 
            pro_f1: "1000 кредитов сразу", pro_f2: "+50 кредитов каждый день", pro_f3: "Кастомный API ключ", pro_f5: "DNS, WHOIS, IP Инфраструктура", buy_pro: "Купить Pro",
            ent_f1: "Безлимит кредитов (∞)", ent_f2: "Кастомный API ключ", ent_f3: "Вебхуки и массовый экспорт", ent_f4: "Реальный мониторинг 24/7", ent_f5: "Приоритетная поддержка", buy_ent: "Купить Enterprise",
            type_name: "ФИО", search_cost: "10 кредитов за один поиск"
        },
        en: {
            nav_modules: "Recon Modules", nav_breach: "Breach Search", nav_domain: "Domain Lookup", nav_ip: "IP Infrastructure",
            nav_system: "System", nav_payments: "Payments", credits: "Credits", account: "Account", logout: "Logout", login: "Login", register: "Register",
            hero_badge_breach: "14.8B RECORDS INDEXED · REAL-TIME QUERY", hero_title_breach: "Search across <span class='accent'>leaked databases</span><br>in real-time.",
            hero_sub_breach: "",
            target_query: "Target Query", execute: "Execute", filter_type: "Filter by type", results: "Search Results", no_probes: "No probes executed",
            no_probes_desc: "Enter a query above and hit Execute to scan indexed databases.", hero_badge_domain: "PASSIVE DNS · WHOIS · SUBDOMAINS", hero_title_domain: "Enumerate <span class='accent'>domain infrastructure</span><br>in seconds.",
            target_domain: "Target Domain", resolve: "Resolve", hero_badge_ip: "ASN · PORTS · GEOLOCATION", hero_title_ip: "Analyze <span class='accent'>IP infrastructure</span><br>at scale.",
            target_ip: "Target IP", scan: "Scan", awaiting_target: "Awaiting target", auth_welcome: "Welcome back. Please enter your details.",
            email: "Email", username: "Username", password: "Password", no_account: "Don't have an account?", upgrade_plan: "Upgrade your plan",
            upgrade_desc: "Credits are used per query. Pro and Enterprise are monthly subscriptions.", one_time: "One-time", per_month: "/ per month", 
            free_f1: "10 credits every day", free_f2: "10 credits per search", free_f3: "Basic breach search", free_f4: "Community support", current_plan: "Current Plan", 
            pro_f1: "1000 credits instantly", pro_f2: "+50 credits every day", pro_f3: "Custom API key", pro_f5: "DNS, WHOIS, IP Infrastructure", buy_pro: "Buy Pro",
            ent_f1: "Unlimited credits (∞)", ent_f2: "Custom API key", ent_f3: "Webhooks & bulk export", ent_f4: "Real-time monitoring 24/7", ent_f5: "Priority support", buy_ent: "Buy Enterprise",
            type_name: "Name", search_cost: "10 credits per search"
        }
    };

    function getLang() {
        const activeBtn = document.querySelector('.lang-btn.active');
        return activeBtn ? (activeBtn.id === 'langRuBtn' ? 'ru' : 'en') : 'ru';
    }

    function applyLanguage(lang) {
        document.querySelectorAll('[data-i18n]').forEach(elem => {
            const key = elem.getAttribute('data-i18n');
            if (translations[lang][key] !== undefined) {
                elem.innerHTML = translations[lang][key];
                elem.style.display = translations[lang][key] === '' ? 'none' : 'block';
            }
        });
        if ($('langRuBtn')) $('langRuBtn').classList.toggle('active', lang === 'ru');
        if ($('langEnBtn')) $('langEnBtn').classList.toggle('active', lang === 'en');
        if ($('authModal') && $('authModal').classList.contains('show')) openAuth(authMode);
    }

    if ($('langRuBtn')) $('langRuBtn').addEventListener('click', () => applyLanguage('ru'));
    if ($('langEnBtn')) $('langEnBtn').addEventListener('click', () => applyLanguage('en'));
    applyLanguage('ru');

    function showToast(msg, type = 'info') {
        if (!toast || !toastText) return;
        toastText.textContent = msg;
        toast.className = 'toast show ' + type;
        clearTimeout(toast._t);
        toast._t = setTimeout(() => toast.classList.remove('show'), 3000);
    }

    async function checkServerStatus() {
        const start = performance.now();
        try {
            const res = await fetch('/api/status', { cache: 'no-store' });
            if (!res.ok) throw new Error('Server Down');
            const data = await res.json();
            const ping = Math.round(performance.now() - start);
            
            if ($('statusDot')) $('statusDot').classList.remove('offline');
            if ($('statusText')) $('statusText').textContent = 'ONLINE';
            if ($('pingVal')) $('pingVal').textContent = ping + 'ms';
            if ($('cpuVal')) $('cpuVal').textContent = data.cpu + '%';
        } catch (e) {
            if ($('statusDot')) $('statusDot').classList.add('offline');
            if ($('statusText')) $('statusText').textContent = 'OFFLINE';
            if ($('pingVal')) $('pingVal').textContent = 'N/A';
            if ($('cpuVal')) $('cpuVal').textContent = 'N/A';
        }
    }
    checkServerStatus();
    setInterval(checkServerStatus, 5000);

    function updateAuthUI() {
        if (currentUser) {
            const creditsDisplay = currentUser.plan === 'enterprise' ? '∞' : (currentUser.credits || 0).toLocaleString();
            if ($('creditsBox')) $('creditsBox').style.display = 'flex';
            if ($('accountBtn')) $('accountBtn').style.display = 'flex';
            if ($('logoutBtn')) $('logoutBtn').style.display = 'flex';
            if ($('loginBtn')) $('loginBtn').style.display = 'none';
            if ($('registerBtn')) $('registerBtn').style.display = 'none';
            if ($('accountBtn')) $('accountBtn').innerHTML = `${currentUser.username} (${currentUser.plan})`;
            if ($('creditsVal')) $('creditsVal').textContent = creditsDisplay;
        } else {
            if ($('creditsBox')) $('creditsBox').style.display = 'none';
            if ($('accountBtn')) $('accountBtn').style.display = 'none';
            if ($('logoutBtn')) $('logoutBtn').style.display = 'none';
            if ($('loginBtn')) $('loginBtn').style.display = 'flex';
            if ($('registerBtn')) $('registerBtn').style.display = 'flex';
        }
    }

    const authModal = $('authModal');
    let authMode = 'login';

    function openAuth(mode) {
        authMode = mode;
        if (authModal) authModal.classList.add('show');
        const isLogin = mode === 'login';
        const lang = getLang();
        
        if ($('authUser')) $('authUser').value = '';
        if ($('authPass')) $('authPass').value = '';
        if ($('authEmail')) $('authEmail').value = '';
        
        if ($('authModalTitle')) $('authModalTitle').textContent = isLogin ? translations[lang].login : translations[lang].register;
        if ($('authModalSub')) $('authModalSub').textContent = isLogin ? translations[lang].auth_welcome : (lang === 'ru' ? "Создайте аккаунт и получите 100 кредитов." : "Create an account to get 100 free credits.");
        if ($('authSubmit')) $('authSubmit').textContent = isLogin ? translations[lang].login : translations[lang].register;
        if ($('authSwitchText')) $('authSwitchText').textContent = isLogin ? translations[lang].no_account : (lang === 'ru' ? "Уже есть аккаунт?" : "Already have an account?");
        if ($('authSwitchBtn')) $('authSwitchBtn').textContent = isLogin ? translations[lang].register : translations[lang].login;
        if ($('emailGroup')) $('emailGroup').style.display = isLogin ? 'none' : 'flex';
    }

    if ($('loginBtn')) $('loginBtn').addEventListener('click', () => openAuth('login'));
    if ($('registerBtn')) $('registerBtn').addEventListener('click', () => openAuth('register'));
    if ($('authModalClose')) $('authModalClose').addEventListener('click', () => { if (authModal) authModal.classList.remove('show'); });
    if ($('authSwitchBtn')) $('authSwitchBtn').addEventListener('click', () => openAuth(authMode === 'login' ? 'register' : 'login'));

    if ($('authSubmit')) {
        $('authSubmit').addEventListener('click', async () => {
            const username = $('authUser').value.trim();
            const password = $('authPass').value;
            const email = $('authEmail').value.trim();
            const endpoint = authMode === 'login' ? '/api/login' : '/api/register';
            try {
                const res = await fetch(endpoint, {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify(authMode === 'login' ? { username, password } : { username, email, password })
                });
                const data = await res.json();
                if (res.ok) {
                    if (authMode === 'login') {
                        currentUser = data.user;
                        localStorage.setItem('arcanum_user', JSON.stringify(currentUser));
                        showToast('Welcome back, ' + username + '!', 'success');
                        if (authModal) authModal.classList.remove('show');
                    } else {
                        showToast('Registration successful! Please login.', 'success');
                        openAuth('login');
                    }
                    updateAuthUI();
                } else {
                    showToast(data.detail || 'Error', 'error');
                }
            } catch (err) {
                showToast('Server connection failed.', 'error');
            }
        });
    }

    if ($('logoutBtn')) {
        $('logoutBtn').addEventListener('click', () => {
            currentUser = null;
            localStorage.removeItem('arcanum_user');
            updateAuthUI();
            showToast('Logged out', 'success');
        });
    }

    const pricingModal = $('pricingModal');
    function openPricing() {
        if (!currentUser) { showToast('Please login first', 'error'); openAuth('login'); return; }
        if (pricingModal) pricingModal.classList.add('show');
        updatePricingButtons();
    }
    if ($('paymentsNavBtn')) $('paymentsNavBtn').addEventListener('click', openPricing);
    if ($('accountBtn')) $('accountBtn').addEventListener('click', openPricing);
    if ($('pricingModalClose')) $('pricingModalClose').addEventListener('click', () => { if (pricingModal) pricingModal.classList.remove('show'); });

    function updatePricingButtons() {
        ['free', 'pro', 'ent'].forEach(p => {
            const btn = document.querySelector(`#card-${p} .buy-btn`);
            if (!btn) return;
            if (currentUser && currentUser.plan === (p === 'ent' ? 'enterprise' : p)) {
                btn.classList.add('current');
                btn.textContent = getLang() === 'ru' ? 'Текущий тариф' : 'Current Plan';
            } else {
                btn.classList.remove('current');
                btn.textContent = p === 'free' ? (getLang() === 'ru' ? 'Перейти на Free' : 'Switch to Free') : (p === 'pro' ? (getLang() === 'ru' ? 'Купить Pro' : 'Buy Pro') : (getLang() === 'ru' ? 'Купить Enterprise' : 'Buy Enterprise'));
            }
        });
    }

    $$('.buy-btn').forEach(btn => {
        btn.addEventListener('click', async () => {
            const plan = btn.dataset.plan;
            if (!currentUser) return;
            try {
                const res = await fetch('/api/upgrade', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ username: currentUser.username, plan })
                });
                const data = await res.json();
                if (res.ok) {
                    currentUser.plan = data.plan;
                    currentUser.credits = data.credits;
                    localStorage.setItem('arcanum_user', JSON.stringify(currentUser));
                    updateAuthUI();
                    updatePricingButtons();
                    showToast('Payment successful!', 'success');
                    if (pricingModal) pricingModal.classList.remove('show');
                } else {
                    showToast(data.detail || 'Upgrade failed', 'error');
                }
            } catch (err) {
                showToast('Server error', 'error');
            }
        });
    });

    $$('.nav-item[data-view]').forEach(item => {
        item.addEventListener('click', (e) => {
            e.preventDefault();
            const view = item.dataset.view;
            if (!view) return;
            $$('.nav-item').forEach(i => i.classList.remove('active'));
            item.classList.add('active');
            $$('.view').forEach(v => v.classList.remove('active'));
            const activeView = document.getElementById(`view-${view}`);
            if (activeView) activeView.classList.add('active');
            if ($('breadcrumbView')) $('breadcrumbView').textContent = view === 'breach' ? 'breach_search' : view + '_module';
        });
    });

    $$('#types-breach .type-btn').forEach(btn => {
        btn.addEventListener('click', () => {
            $$('#types-breach .type-btn').forEach(b => b.classList.remove('active'));
            btn.classList.add('active');
            currentSearchType = btn.dataset.type;
            const prefixMap = { 'phone': '+' };
            if ($('prefix-breach')) $('prefix-breach').textContent = prefixMap[currentSearchType] || '';
        });
    });

    async function executeProbe(viewName) {
        if (!currentUser) { showToast('Please login to search', 'error'); openAuth('login'); return; }
        if (currentUser.plan !== 'enterprise' && currentUser.credits < 10) { showToast('Insufficient credits', 'error'); openPricing(); return; }

        const input = $(`input-${viewName}`);
        const query = input.value.trim();
        if (!query) { showToast('Query cannot be empty', 'error'); return; }

        let typeToSearch = currentSearchType;
        if (viewName === 'domain') typeToSearch = 'domain';
        if (viewName === 'ip') typeToSearch = 'ip';

        const btn = $(`exec-btn-${viewName}`);
        const resultsList = $(`results-${viewName}`);
        const countEl = $(`count-${viewName}`); 
        
        if (btn) btn.classList.add('loading');
        if (resultsList) resultsList.innerHTML = '<div class="results-empty">Scanning...</div>';
        if (countEl) countEl.textContent = '0 / 0'; 

        try {
            const res = await fetch('/api/search', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ query, type: typeToSearch })
            });
            const data = await res.json();
            if (resultsList) resultsList.innerHTML = '';
            
            if (data && data.results && data.results.length > 0) {
                if (countEl) countEl.textContent = `${data.results.length} / ${data.results.length}`;

                const grouped = {};
                data.results.forEach(item => {
                    const source = item.source || 'Database';
                    if (!grouped[source]) grouped[source] = [];
                    grouped[source].push(item.data);
                });

                for (const source in grouped) {
                    const card = document.createElement('div');
                    card.className = 'result-card';
                    
                    let recordsHtml = grouped[source].map(recordStr => {
                        let escaped = escapeHtml(recordStr);
                        let lines = escaped.split('\n');
                        let linesHtml = lines.map(line => {
                            let match = line.match(/^([^:]+):\s*(.*)$/);
                            if (match) {
                                return `<div class="result-data-line"><strong>${match[1]}:</strong> ${match[2]}</div>`;
                            }
                            return `<div class="result-data-line">${line}</div>`;
                        }).join('');
                        return `<div class="record-block">${linesHtml}</div>`;
                    }).join('');
                    
                    card.innerHTML = `<div class="result-card-header">${escapeHtml(source)}</div><div class="result-card-body">${recordsHtml}</div>`;
                    if (resultsList) resultsList.appendChild(card);
                }
            } else {
                if (resultsList) resultsList.innerHTML = '<div class="results-empty">No records found.</div>';
                if (countEl) countEl.textContent = '0 / 0'; 
            }

            if (currentUser.plan !== 'enterprise') {
                currentUser.credits -= 10;
                localStorage.setItem('arcanum_user', JSON.stringify(currentUser));
                updateAuthUI();
            }
        } catch (err) {
            if (resultsList) resultsList.innerHTML = '<div class="results-empty">Error connecting to API.</div>';
            if (countEl) countEl.textContent = '0 / 0';
        } finally {
            if (btn) btn.classList.remove('loading');
        }
    }

    if ($('form-breach')) $('form-breach').addEventListener('submit', (e) => { e.preventDefault(); executeProbe('breach'); });
    if ($('form-domain')) $('form-domain').addEventListener('submit', (e) => { e.preventDefault(); executeProbe('domain'); });
    if ($('form-ip')) $('form-ip').addEventListener('submit', (e) => { e.preventDefault(); executeProbe('ip'); });

    document.addEventListener('mousemove', (e) => {
        if (spotlight) {
            spotlight.style.setProperty('--mx', e.clientX + 'px');
            spotlight.style.setProperty('--my', e.clientY + 'px');
        }
    });

    updateAuthUI();
});
