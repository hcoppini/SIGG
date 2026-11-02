document.addEventListener('DOMContentLoaded', () => {
    if (window.lucide) {
        window.lucide.createIcons();
    }

    // ==========================================
    // 0. TOASTS, AUDIO CHIME & HAPTICS
    // ==========================================
    const toastContainer = document.getElementById('mobileToastContainer');
    let audioCtx = null;

    function triggerHaptic(duration = 25) {
        if ('vibrate' in navigator) {
            try {
                navigator.vibrate(duration);
            } catch (e) {}
        }
    }

    function playMobileChime() {
        try {
            const soundEnabled = document.getElementById('mobileSoundToggle')?.checked ?? true;
            if (!soundEnabled) return;

            if (!audioCtx) {
                audioCtx = new (window.AudioContext || window.webkitAudioContext)();
            }
            if (audioCtx.state === 'suspended') {
                audioCtx.resume();
            }

            const now = audioCtx.currentTime;
            const osc1 = audioCtx.createOscillator();
            const osc2 = audioCtx.createOscillator();
            const gain = audioCtx.createGain();

            osc1.type = 'sine';
            osc1.frequency.setValueAtTime(587.33, now); // D5
            osc1.frequency.exponentialRampToValueAtTime(880, now + 0.10); // A5

            osc2.type = 'triangle';
            osc2.frequency.setValueAtTime(880, now + 0.10); // A5
            osc2.frequency.exponentialRampToValueAtTime(1174.66, now + 0.24); // D6

            gain.gain.setValueAtTime(0.12, now);
            gain.gain.exponentialRampToValueAtTime(0.001, now + 0.40);

            osc1.connect(gain);
            osc2.connect(gain);
            gain.connect(audioCtx.destination);

            osc1.start(now);
            osc2.start(now + 0.10);
            osc1.stop(now + 0.10);
            osc2.stop(now + 0.40);
        } catch (e) {
            // Audio context may be waiting for user touch
        }
    }

    function showMobileToast(title, message, type = 'info', duration = 3500) {
        if (!toastContainer) return;
        const toast = document.createElement('div');
        toast.className = `mobile-toast ${type}`;
        toast.innerHTML = `
            <div class="mobile-toast-title">${title}</div>
            <div class="mobile-toast-msg">${message}</div>
        `;
        toastContainer.appendChild(toast);

        setTimeout(() => {
            toast.style.opacity = '0';
            toast.style.transform = 'translateY(-20px)';
            toast.style.transition = 'all 0.2s ease';
            setTimeout(() => toast.remove(), 200);
        }, duration);
    }

    // ==========================================
    // 1. BOTTOM TAB BAR NAVIGATION
    // ==========================================
    const tabBtns = document.querySelectorAll('.mobile-tab-btn');
    const views = document.querySelectorAll('.mobile-view');

    function switchMobileTab(targetId) {
        tabBtns.forEach(btn => {
            if (btn.getAttribute('data-target') === targetId) {
                btn.classList.add('active');
            } else {
                btn.classList.remove('active');
            }
        });

        views.forEach(v => {
            if (v.id === targetId) {
                v.classList.add('active');
            } else {
                v.classList.remove('active');
            }
        });

        window.scrollTo({ top: 0, behavior: 'instant' });

        if (targetId === 'portfolioView') {
            fetchMobilePortfolio();
        } else if (targetId === 'alertsView') {
            loadMobileSettings();
        }

        if (window.lucide) {
            window.lucide.createIcons();
        }
    }

    tabBtns.forEach(btn => {
        btn.addEventListener('click', (e) => {
            e.preventDefault();
            const target = btn.getAttribute('data-target');
            if (target) {
                triggerHaptic(15);
                switchMobileTab(target);
            }
        });
    });

    // ==========================================
    // 2. SIGNALS FEED & SCANNER
    // ==========================================
    const mobileSignalsFeed = document.getElementById('mobileSignalsFeed');
    const mobileSignalsLoading = document.getElementById('mobileSignalsLoading');
    const mobileSignalsEmpty = document.getElementById('mobileSignalsEmpty');
    const mobileSignalCount = document.getElementById('mobileSignalCount');
    const mobileRunScanBtn = document.getElementById('mobileRunScanBtn');

    const mobileRegimeStrip = document.getElementById('mobileRegimeStrip');
    const mobileRegimeTag = document.getElementById('mobileRegimeTag');
    const mobileRegimeText = document.getElementById('mobileRegimeText');

    function renderRegime(regime) {
        if (!mobileRegimeStrip || !regime) return;
        const reg = regime.regime || 'GREEN';
        mobileRegimeStrip.className = 'regime-strip';
        if (reg === 'RED') mobileRegimeStrip.classList.add('regime-red');
        else if (reg === 'YELLOW') mobileRegimeStrip.classList.add('regime-yellow');
        else mobileRegimeStrip.classList.add('regime-green');

        if (mobileRegimeTag) mobileRegimeTag.textContent = `${reg} REGIME`;
        if (mobileRegimeText) {
            const brd = Number(regime.breadth_above_sma20_pct || 0).toFixed(0);
            const chg = Number(regime.index_change_pct || 0);
            mobileRegimeText.textContent = `Breadth: ${brd}% | Δ: ${chg >= 0 ? '+' : ''}${chg.toFixed(1)}% | Max 3 Slots`;
        }
    }

    function renderSignalCards(data) {
        if (!mobileSignalsFeed) return;
        mobileSignalsFeed.innerHTML = '';

        if (!data || data.length === 0) {
            if (mobileSignalsEmpty) mobileSignalsEmpty.classList.remove('hidden');
            if (mobileSignalCount) mobileSignalCount.textContent = '0 signals';
            return;
        }

        if (mobileSignalsEmpty) mobileSignalsEmpty.classList.add('hidden');
        if (mobileSignalCount) mobileSignalCount.textContent = `${data.length} qualified`;

        data.forEach(row => {
            const ticker = row.Ticker || '';
            const tvSymbol = (row.Yahoo_Ticker || row.Ticker || '').replace('.WA', '').replace('.W', '');
            const tvUrl = `https://pl.tradingview.com/symbols/GPW-${tvSymbol}/`;
            const isBuy = (row.Strategy_Signal === 'Buy');
            const dayGain = Number(row.Day_Gain_Pct || 0);
            const rScore = Number(row.Runner_Score || 0);
            const closeP = Number(row.Close || 0);
            const shares = row.Order_Shares || Math.floor(6600 / (closeP || 1));
            const ticket = row.Order_Ticket || `KUPNO | ${ticker} | ${shares} szt. | LIMIT ${(closeP * 1.005).toFixed(2)} PLN`;
            const trRatio = Number(row.TR_Ratio || 0);
            const volS = Number(row.Volume_Surge || 0);
            const atrPct = Number(row.ATR_Pct || 0);
            const atrVal = (row.ATR_Pct ? (closeP * (row.ATR_Pct / 100)) : (closeP * 0.03)).toFixed(2);

            const card = document.createElement('div');
            card.className = `signal-card ${isBuy ? 'tier-strict' : ''}`;
            card.innerHTML = `
                <div class="signal-card-header">
                    <div class="signal-ticker-group">
                        <span class="signal-ticker">${ticker}</span>
                        <span class="signal-name">${row.Name || 'GPW Stock'}</span>
                    </div>
                    <div class="signal-badges">
                        <span class="${isBuy ? 'badge-signal-buy' : 'badge-signal-watch'}">${row.Strategy_Signal || 'Hold'}</span>
                        <span class="runner-score-pill">★ ${rScore.toFixed(2)}</span>
                    </div>
                </div>

                <div class="card-metrics-grid">
                    <div class="card-metric">
                        <span class="metric-label">Close</span>
                        <span class="metric-val">${closeP.toFixed(2)}</span>
                    </div>
                    <div class="card-metric">
                        <span class="metric-label">Day Δ</span>
                        <span class="metric-val ${dayGain >= 2.5 ? 'text-green' : (dayGain < 0 ? 'text-red' : '')}">${dayGain >= 0 ? '+' : ''}${dayGain.toFixed(1)}%</span>
                    </div>
                    <div class="card-metric">
                        <span class="metric-label">TR/ATR</span>
                        <span class="metric-val ${trRatio >= 1.3 ? 'text-green' : ''}">${trRatio.toFixed(1)}x</span>
                    </div>
                    <div class="card-metric">
                        <span class="metric-label">Vol Surge</span>
                        <span class="metric-val ${volS >= 1.5 ? 'text-green' : ''}">${volS.toFixed(1)}x</span>
                    </div>
                </div>

                <div class="card-ticket-box">
                    <div class="ticket-headline">
                        <span>Order Ticket (Whole Shares)</span>
                        <span>Stop: ${row.Stop_Loss ? Number(row.Stop_Loss).toFixed(2) : '-'} PLN</span>
                    </div>
                    <div class="ticket-text">${ticket}</div>
                </div>

                <div class="card-actions-row">
                    <button class="btn-card-copy mobile-copy-btn" data-ticket="${encodeURIComponent(ticket)}">
                        <i data-lucide="copy" style="width: 14px; height: 14px;"></i> Copy Ticket
                    </button>
                    <button class="btn-card-exec mobile-exec-btn" data-ticker="${ticker}" data-price="${closeP}" data-shares="${shares}" data-ticket="${encodeURIComponent(ticket)}" data-atr="${atrVal}">
                        <i data-lucide="zap" style="width: 14px; height: 14px;"></i> Execute
                    </button>
                    <a href="${tvUrl}" target="_blank" class="btn-card-chart" title="TradingView Chart">
                        <i data-lucide="line-chart" style="width: 16px; height: 16px;"></i>
                    </a>
                </div>
            `;
            mobileSignalsFeed.appendChild(card);
        });

        // Wire copy ticket handlers
        mobileSignalsFeed.querySelectorAll('.mobile-copy-btn').forEach(btn => {
            btn.addEventListener('click', (e) => {
                e.stopPropagation();
                triggerHaptic(30);
                const raw = decodeURIComponent(btn.getAttribute('data-ticket') || '');
                navigator.clipboard.writeText(raw).then(() => {
                    showMobileToast('Ticket Copied! 📋', 'Pasted to clipboard. Ready for broker.', 'info', 2500);
                }).catch(() => {
                    prompt('Copy ticket manually:', raw);
                });
            });
        });

        // Wire execution bottom sheet triggers
        mobileSignalsFeed.querySelectorAll('.mobile-exec-btn').forEach(btn => {
            btn.addEventListener('click', (e) => {
                e.stopPropagation();
                triggerHaptic(20);
                const ticker = btn.getAttribute('data-ticker');
                const price = parseFloat(btn.getAttribute('data-price'));
                const shares = parseInt(btn.getAttribute('data-shares'), 10);
                const ticket = decodeURIComponent(btn.getAttribute('data-ticket') || '');
                const atr = parseFloat(btn.getAttribute('data-atr'));

                openMobileExecSheet({ ticker, price, shares, ticket, atr });
            });
        });

        if (window.lucide) {
            window.lucide.createIcons();
        }
    }

    async function fetchMobileSignals() {
        try {
            const res = await fetch('/api/results/scan?strategy=squeeze_ignition');
            const json = await res.json();
            if (json.market_regime) renderRegime(json.market_regime);
            if (json.status === 'success') {
                renderSignalCards(json.data);
            }
        } catch (e) {
            console.error('Failed to fetch signals:', e);
        }
    }

    if (mobileRunScanBtn) {
        mobileRunScanBtn.addEventListener('click', async () => {
            triggerHaptic(30);
            mobileRunScanBtn.disabled = true;
            if (mobileSignalsLoading) mobileSignalsLoading.classList.remove('hidden');
            if (mobileSignalsEmpty) mobileSignalsEmpty.classList.add('hidden');

            try {
                const res = await fetch('/api/scan', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ strategy: 'squeeze_ignition' })
                });
                const json = await res.json();
                if (json.status === 'success') {
                    if (json.market_regime) renderRegime(json.market_regime);
                    renderSignalCards(json.data);
                    showMobileToast('Scan Complete ⚡', `Evaluated WIG140 (${json.data ? json.data.length : 0} signals)`, 'success');
                    playMobileChime();
                } else {
                    showMobileToast('Scan Error', json.message || 'Error running scanner', 'error');
                }
            } catch (err) {
                showMobileToast('Scan Error', 'Connection failed: ' + err, 'error');
            }

            if (mobileSignalsLoading) mobileSignalsLoading.classList.add('hidden');
            mobileRunScanBtn.disabled = false;
        });
    }

    // ==========================================
    // 3. PORTFOLIO COMMAND (3 SLOTS)
    // ==========================================
    const mobileSlotsFeed = document.getElementById('mobileSlotsFeed');
    const topBarEquityVal = document.getElementById('topBarEquityVal');
    const portLiveEquity = document.getElementById('portLiveEquity');
    const portTotalPnlPill = document.getElementById('portTotalPnlPill');
    const portCashVal = document.getElementById('portCashVal');
    const portSlotAllocVal = document.getElementById('portSlotAllocVal');
    const portActiveCount = document.getElementById('portActiveCount');
    const mobileRefreshPortBtn = document.getElementById('mobileRefreshPortBtn');

    async function fetchMobilePortfolio() {
        try {
            const res = await fetch('/api/portfolio');
            const json = await res.json();
            if (json.status !== 'success' || !json.data) return;

            const summary = json.data;
            const positions = summary.positions || [];
            const maxSlots = summary.max_positions || 3;
            const vacantCount = summary.vacant_slots !== undefined ? summary.vacant_slots : (maxSlots - positions.length);
            const cashPerSlot = summary.cash_per_vacant_slot || (summary.cash / (vacantCount || 1));

            // Update top bar equity
            if (topBarEquityVal) {
                topBarEquityVal.textContent = `${Number(summary.total_equity || 20000).toLocaleString('pl-PL')} PLN`;
            }
            if (portLiveEquity) {
                portLiveEquity.textContent = `${Number(summary.total_equity || 20000).toLocaleString('pl-PL', { minimumFractionDigits: 2 })} PLN`;
            }

            const totalPnl = Number(summary.total_pnl_pln || 0);
            const totalRet = Number(summary.total_return_pct || 0);
            if (portTotalPnlPill) {
                portTotalPnlPill.textContent = `${totalRet >= 0 ? '+' : ''}${totalRet.toFixed(2)}% (${totalPnl >= 0 ? '+' : ''}${totalPnl.toFixed(0)} PLN)`;
                portTotalPnlPill.className = `port-pnl-pill ${totalPnl >= 0 ? 'positive' : 'negative'}`;
            }

            if (portCashVal) {
                portCashVal.textContent = `${Number(summary.cash || 0).toLocaleString('pl-PL', { maximumFractionDigits: 0 })} PLN`;
            }
            if (portSlotAllocVal) {
                portSlotAllocVal.textContent = `~${Number(cashPerSlot).toLocaleString('pl-PL', { maximumFractionDigits: 0 })} PLN`;
            }
            if (portActiveCount) {
                portActiveCount.textContent = String(positions.length);
            }

            if (!mobileSlotsFeed) return;
            mobileSlotsFeed.innerHTML = '';

            for (let i = 0; i < maxSlots; i++) {
                const pos = positions[i];
                const slotNum = `SLOT ${i + 1}`;

                if (pos) {
                    const isPositive = (pos.pnl_pln >= 0);
                    const pnlClass = isPositive ? 'text-green' : 'text-red';
                    const pnlSign = isPositive ? '+' : '';
                    const held = pos.sessions_held || 1;

                    let cardClass = 'mobile-slot-card occupied';
                    let badgeClass = 'slot-status-badge badge-signal-buy';
                    let badgeText = `DAY ${held} OF 3`;

                    if (pos.exit_signal === 'STOP_TRIGGERED') {
                        cardClass = 'mobile-slot-card breached';
                        badgeClass = 'slot-status-badge text-red';
                        badgeText = 'STOP BREACHED';
                    } else if (pos.exit_signal === '3D_EXIT_TODAY') {
                        cardClass = 'mobile-slot-card warning';
                        badgeClass = 'slot-status-badge text-amber';
                        badgeText = '3D EXIT TODAY';
                    } else if (pos.exit_signal === 'RUNNER_HOLD') {
                        cardClass = 'mobile-slot-card occupied';
                        badgeClass = 'slot-status-badge text-green font-bold';
                        badgeText = 'RUNNER EXCEPTION';
                    }

                    const card = document.createElement('div');
                    card.className = cardClass;
                    card.innerHTML = `
                        <div class="slot-top-row">
                            <span class="slot-tag">${slotNum}</span>
                            <span class="${badgeClass}">${badgeText}</span>
                        </div>

                        <div class="slot-ticker-pnl-row">
                            <span class="slot-pos-ticker">${pos.ticker}</span>
                            <span class="slot-pos-pnl ${pnlClass}">${pnlSign}${Number(pos.pnl_pct || 0).toFixed(2)}% (${pnlSign}${Number(pos.pnl_pln || 0).toFixed(0)} PLN)</span>
                        </div>

                        <!-- 3-Day Countdown Step Bar -->
                        <div class="hold-progress-bar">
                            <div class="hold-step active"></div>
                            <div class="hold-step ${held >= 2 ? 'active' : ''}"></div>
                            <div class="hold-step ${held >= 3 ? (pos.exit_signal === 'RUNNER_HOLD' ? 'active' : 'exit-day') : ''}"></div>
                        </div>

                        <div class="slot-details-grid">
                            <div class="slot-detail-item">
                                <span class="slot-detail-label">Shares</span>
                                <span class="slot-detail-val">${pos.shares} szt.</span>
                            </div>
                            <div class="slot-detail-item">
                                <span class="slot-detail-label">Entry</span>
                                <span class="slot-detail-val">${Number(pos.entry_price || 0).toFixed(2)} PLN</span>
                            </div>
                            <div class="slot-detail-item">
                                <span class="slot-detail-label">Current</span>
                                <span class="slot-detail-val">${Number(pos.current_price || pos.entry_price || 0).toFixed(2)} PLN</span>
                            </div>
                            <div class="slot-detail-item">
                                <span class="slot-detail-label">2.2x Stop</span>
                                <span class="slot-detail-val ${pos.current_price <= pos.stop_loss_price ? 'text-red font-bold' : ''}">${Number(pos.stop_loss_price || 0).toFixed(2)} PLN</span>
                            </div>
                        </div>

                        <button class="btn-close-pos mobile-close-pos-btn" data-ticker="${pos.ticker}" data-price="${pos.current_price || pos.entry_price}">
                            <i data-lucide="x-circle" style="width: 14px; height: 14px;"></i> Close Position (Liquidate)
                        </button>
                    `;
                    mobileSlotsFeed.appendChild(card);
                } else {
                    const card = document.createElement('div');
                    card.className = 'mobile-slot-card vacant';
                    card.innerHTML = `
                        <div class="slot-top-row">
                            <span class="slot-tag">${slotNum}</span>
                            <span class="slot-status-badge" style="color: var(--text-muted); background: var(--bg-card-subtle);">VACANT</span>
                        </div>
                        <div class="slot-vacant-content">
                            <div class="slot-vacant-title">Slot Available for Breakout</div>
                            <div class="slot-vacant-sub">Allocated: ~${Number(cashPerSlot).toLocaleString('pl-PL', { maximumFractionDigits: 0 })} PLN</div>
                        </div>
                    `;
                    mobileSlotsFeed.appendChild(card);
                }
            }

            // Wire position close buttons
            mobileSlotsFeed.querySelectorAll('.mobile-close-pos-btn').forEach(btn => {
                btn.addEventListener('click', async (e) => {
                    e.stopPropagation();
                    triggerHaptic(40);
                    const ticker = btn.getAttribute('data-ticker');
                    const price = parseFloat(btn.getAttribute('data-price'));
                    
                    if (confirm(`Liquidate position in ${ticker} at quote ~${price.toFixed(2)} PLN?`)) {
                        try {
                            const res = await fetch('/api/portfolio/sell', {
                                method: 'POST',
                                headers: { 'Content-Type': 'application/json' },
                                body: JSON.stringify({ ticker, exit_price: price, reason: 'Mobile_Close' })
                            });
                            const json = await res.json();
                            if (json.status === 'success') {
                                showMobileToast('Position Liquidated', json.message, 'warning');
                                playMobileChime();
                                fetchMobilePortfolio();
                            } else {
                                showMobileToast('Error', json.message || 'Cannot close position', 'error');
                            }
                        } catch (err) {
                            showMobileToast('Error', 'Close request failed: ' + err, 'error');
                        }
                    }
                });
            });

            if (window.lucide) {
                window.lucide.createIcons();
            }
        } catch (e) {
            console.error('Failed to fetch portfolio:', e);
        }
    }

    if (mobileRefreshPortBtn) {
        mobileRefreshPortBtn.addEventListener('click', () => {
            triggerHaptic(20);
            fetchMobilePortfolio();
            showMobileToast('Quotes Refreshed', 'Live quotes and stops updated.', 'info', 2000);
        });
    }

    // ==========================================
    // 4. ORDER EXECUTION BOTTOM SHEET
    // ==========================================
    const mobileExecSheet = document.getElementById('mobileExecSheet');
    const closeExecSheetBtn = document.getElementById('closeExecSheetBtn');
    const sheetConfirmBtn = document.getElementById('sheetConfirmBtn');
    const sheetTicker = document.getElementById('sheetTicker');
    const sheetTicketText = document.getElementById('sheetTicketText');
    const sheetPriceInput = document.getElementById('sheetPriceInput');
    const sheetSharesInput = document.getElementById('sheetSharesInput');

    let pendingMobileOrder = null;

    function openMobileExecSheet(data) {
        pendingMobileOrder = data;
        if (!mobileExecSheet) return;
        if (sheetTicker) sheetTicker.textContent = data.ticker;
        if (sheetTicketText) sheetTicketText.textContent = data.ticket;
        if (sheetPriceInput) sheetPriceInput.value = data.price;
        if (sheetSharesInput) sheetSharesInput.value = data.shares;

        mobileExecSheet.classList.add('active');
    }

    function closeMobileExecSheet() {
        if (mobileExecSheet) mobileExecSheet.classList.remove('active');
        pendingMobileOrder = null;
    }

    if (closeExecSheetBtn) closeExecSheetBtn.addEventListener('click', closeMobileExecSheet);
    if (mobileExecSheet) {
        mobileExecSheet.addEventListener('click', (e) => {
            if (e.target === mobileExecSheet) closeMobileExecSheet();
        });
    }

    if (sheetConfirmBtn) {
        sheetConfirmBtn.addEventListener('click', async () => {
            if (!pendingMobileOrder) return;
            const price = parseFloat(sheetPriceInput?.value || pendingMobileOrder.price);
            const shares = parseInt(sheetSharesInput?.value || pendingMobileOrder.shares, 10);

            if (!price || price <= 0 || !shares || shares <= 0) {
                alert('Please enter valid price and shares.');
                return;
            }

            sheetConfirmBtn.disabled = true;
            triggerHaptic(30);

            try {
                const res = await fetch('/api/portfolio/buy', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({
                        ticker: pendingMobileOrder.ticker,
                        price: price,
                        shares: shares,
                        atr: pendingMobileOrder.atr || (price * 0.03)
                    })
                });
                const json = await res.json();
                if (json.status === 'success') {
                    showMobileToast('Position Executed ⚡', json.message, 'success');
                    playMobileChime();
                    closeMobileExecSheet();
                    switchMobileTab('portfolioView');
                } else {
                    showMobileToast('Execution Rejected', json.message || 'Cannot execute trade', 'error');
                }
            } catch (err) {
                showMobileToast('Execution Error', 'Server error: ' + err, 'error');
            }
            sheetConfirmBtn.disabled = false;
        });
    }

    // ==========================================
    // 5. ALERTS & DISCORD SETTINGS
    // ==========================================
    const mobileDiscordWebhook = document.getElementById('mobileDiscordWebhook');
    const mobileSoundToggle = document.getElementById('mobileSoundToggle');
    const mobileAuto1635Toggle = document.getElementById('mobileAuto1635Toggle');
    const mobileAuto1650Toggle = document.getElementById('mobileAuto1650Toggle');
    const mobileSaveWebhookBtn = document.getElementById('mobileSaveWebhookBtn');

    const mobileTestWebhookBtn = document.getElementById('mobileTestWebhookBtn');
    const mobileTest1635Btn = document.getElementById('mobileTest1635Btn');
    const mobileTest1650Btn = document.getElementById('mobileTest1650Btn');

    async function loadMobileSettings() {
        try {
            const res = await fetch('/api/settings');
            const json = await res.json();
            if (json.status === 'success' && json.settings) {
                const s = json.settings;
                if (mobileDiscordWebhook && s.discord_webhook_url !== undefined) mobileDiscordWebhook.value = s.discord_webhook_url;
                if (mobileSoundToggle && s.sound_alerts !== undefined) mobileSoundToggle.checked = Boolean(s.sound_alerts);
                if (mobileAuto1635Toggle && s.auto_dispatch_1635 !== undefined) mobileAuto1635Toggle.checked = Boolean(s.auto_dispatch_1635);
                if (mobileAuto1650Toggle && s.auto_dispatch_1650 !== undefined) mobileAuto1650Toggle.checked = Boolean(s.auto_dispatch_1650);
            }
        } catch (e) {
            console.error('Failed to load settings:', e);
        }
    }

    if (mobileSaveWebhookBtn) {
        mobileSaveWebhookBtn.addEventListener('click', async () => {
            triggerHaptic(25);
            mobileSaveWebhookBtn.disabled = true;
            const payload = {
                discord_webhook_url: mobileDiscordWebhook?.value?.trim() || '',
                sound_alerts: mobileSoundToggle?.checked ?? true,
                auto_dispatch_1635: mobileAuto1635Toggle?.checked ?? true,
                auto_dispatch_1650: mobileAuto1650Toggle?.checked ?? true
            };
            try {
                const res = await fetch('/api/settings', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify(payload)
                });
                const json = await res.json();
                if (json.status === 'success') {
                    showMobileToast('Settings Saved', 'Webhook & automation preferences updated.', 'success');
                } else {
                    showMobileToast('Save Error', json.message || 'Could not save settings.', 'error');
                }
            } catch (err) {
                showMobileToast('Save Error', 'Connection failed: ' + err, 'error');
            }
            mobileSaveWebhookBtn.disabled = false;
        });
    }

    if (mobileTestWebhookBtn) {
        mobileTestWebhookBtn.addEventListener('click', async () => {
            triggerHaptic(20);
            mobileTestWebhookBtn.disabled = true;
            try {
                const webhookUrl = mobileDiscordWebhook?.value?.trim() || '';
                const res = await fetch('/api/notifications/test', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ webhook_url: webhookUrl })
                });
                const json = await res.json();
                if (json.status === 'success') {
                    showMobileToast('Discord Test Sent 🚀', json.message, 'success');
                    playMobileChime();
                } else {
                    showMobileToast('Discord Test Failed', json.message, 'error');
                }
            } catch (err) {
                showMobileToast('Error', 'Test failed: ' + err, 'error');
            }
            mobileTestWebhookBtn.disabled = false;
        });
    }

    if (mobileTest1635Btn) {
        mobileTest1635Btn.addEventListener('click', async () => {
            triggerHaptic(20);
            mobileTest1635Btn.disabled = true;
            try {
                const res = await fetch('/api/notifications/dispatch', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ window: '1635' })
                });
                const json = await res.json();
                showMobileToast('16:35 Pre-Close Alert Sent', json.message, json.status === 'success' ? 'success' : 'warning');
                playMobileChime();
            } catch (err) {
                showMobileToast('Dispatch Error', '' + err, 'error');
            }
            mobileTest1635Btn.disabled = false;
        });
    }

    if (mobileTest1650Btn) {
        mobileTest1650Btn.addEventListener('click', async () => {
            triggerHaptic(20);
            mobileTest1650Btn.disabled = true;
            try {
                const res = await fetch('/api/notifications/dispatch', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ window: '1650' })
                });
                const json = await res.json();
                showMobileToast('16:50 Action Sheet Sent', json.message, json.status === 'success' ? 'success' : 'warning');
                playMobileChime();
            } catch (err) {
                showMobileToast('Dispatch Error', '' + err, 'error');
            }
            mobileTest1650Btn.disabled = false;
        });
    }

    // ==========================================
    // 6. IN-APP NOTIFICATION POLLER
    // ==========================================
    let lastSeenNotifId = 0;
    async function pollMobileNotifications() {
        try {
            const res = await fetch('/api/notifications/active');
            const json = await res.json();
            if (json.status === 'success' && Array.isArray(json.data)) {
                if (lastSeenNotifId === 0 && json.data.length > 0) {
                    lastSeenNotifId = Math.max(...json.data.map(n => n.id || 0));
                    return;
                }
                const newNotes = json.data.filter(n => (n.id || 0) > lastSeenNotifId);
                if (newNotes.length > 0) {
                    newNotes.forEach(n => {
                        showMobileToast(n.title || 'Market Alert', n.message || '', n.level || 'info');
                        if ((n.id || 0) > lastSeenNotifId) lastSeenNotifId = n.id;
                    });
                    playMobileChime();
                    triggerHaptic(40);
                }
            }
        } catch (e) {}
    }

    // ==========================================
    // 7. INITIAL BOOTSTRAP
    // ==========================================
    fetchMobileSignals();
    fetchMobilePortfolio();
    loadMobileSettings();
    pollMobileNotifications();

    setInterval(pollMobileNotifications, 12000);
    setInterval(fetchMobilePortfolio, 25000);
});
