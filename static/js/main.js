document.addEventListener('DOMContentLoaded', () => {
    if (window.lucide) {
        window.lucide.createIcons();
    }

    // ==========================================
    // 0. TOAST NOTIFICATIONS & AUDIO CHIME
    // ==========================================
    const toastContainer = document.getElementById('toastContainer');
    let audioCtx = null;

    function playChime() {
        try {
            const soundEnabled = document.getElementById('soundAlertsToggle')?.checked ?? true;
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
            osc1.frequency.exponentialRampToValueAtTime(880, now + 0.12); // A5

            osc2.type = 'triangle';
            osc2.frequency.setValueAtTime(880, now + 0.12); // A5
            osc2.frequency.exponentialRampToValueAtTime(1174.66, now + 0.28); // D6

            gain.gain.setValueAtTime(0.12, now);
            gain.gain.exponentialRampToValueAtTime(0.001, now + 0.45);

            osc1.connect(gain);
            osc2.connect(gain);
            gain.connect(audioCtx.destination);

            osc1.start(now);
            osc2.start(now + 0.12);
            osc1.stop(now + 0.12);
            osc2.stop(now + 0.45);
        } catch (e) {
            // AudioContext may be blocked before first user gesture
        }
    }

    function showToast(title, message, type = 'info', duration = 5000) {
        if (!toastContainer) return;
        const toast = document.createElement('div');
        toast.className = `toast ${type}`;
        toast.innerHTML = `
            <div class="toast-title">${title}</div>
            <div class="toast-msg">${message}</div>
        `;
        toastContainer.appendChild(toast);

        setTimeout(() => {
            toast.style.opacity = '0';
            toast.style.transform = 'translateX(100%)';
            toast.style.transition = 'all 0.3s ease';
            setTimeout(() => toast.remove(), 300);
        }, duration);
    }

    // ==========================================
    // 0.1 NAVIGATION & TABS
    // ==========================================
    const links = document.querySelectorAll('nav a');
    const panels = document.querySelectorAll('.panel');
    const strategySelect = document.getElementById('strategySelect');

    function switchTab(targetId) {
        links.forEach(l => {
            if (l.getAttribute('data-target') === targetId) {
                l.classList.add('active');
            } else {
                l.classList.remove('active');
            }
        });
        panels.forEach(p => {
            if (p.id === targetId) {
                p.classList.add('active');
            } else {
                p.classList.remove('active');
            }
        });

        if (targetId === 'backtest') {
            if (equityChartInstance) equityChartInstance.resize();
            if (seasonBarChartInstance) seasonBarChartInstance.resize();
            if (winLossChartInstance) winLossChartInstance.resize();
        } else if (targetId === 'blueprint') {
            loadStrategyMarkdown();
        }

        if (window.lucide) {
            window.lucide.createIcons();
        }
    }

    links.forEach(link => {
        link.addEventListener('click', (e) => {
            const targetId = link.getAttribute('data-target');
            if (targetId) {
                e.preventDefault();
                switchTab(targetId);
            }
        });
    });

    const openBlueprintBtn = document.getElementById('openBlueprintBtn');
    if (openBlueprintBtn) {
        openBlueprintBtn.addEventListener('click', () => switchTab('blueprint'));
    }

    const goToBacktestBtn = document.getElementById('goToBacktestBtn');
    if (goToBacktestBtn) {
        goToBacktestBtn.addEventListener('click', () => switchTab('backtest'));
    }

    function getActiveStrategy() {
        return strategySelect ? strategySelect.value : 'breakout_trend';
    }

    if (strategySelect) {
        strategySelect.addEventListener('change', () => {
            fetchScanResults();
            fetchBacktestResults();
            fetchOptResults();
        });
    }

    // ==========================================
    // 0.2 PORTFOLIO COMMAND CENTER (3 SLOTS)
    // ==========================================
    const refreshPortfolioBtn = document.getElementById('refreshPortfolioBtn');
    if (refreshPortfolioBtn) {
        refreshPortfolioBtn.addEventListener('click', () => {
            fetchPortfolio();
            showToast('Refreshing Quotes', 'Updated live portfolio quotes and dynamic trailing stops.', 'info', 2500);
        });
    }

    async function fetchPortfolio() {
        const grid = document.getElementById('portfolioSlotsGrid');
        const cashBadge = document.getElementById('portfolioCashBadge');
        const sidebarEquity = document.getElementById('sidebarEquity');
        const sidebarSlots = document.getElementById('sidebarSlots');

        try {
            const res = await fetch('/api/portfolio');
            const json = await res.json();
            if (json.status !== 'success' || !json.data) return;

            const summary = json.data;
            const positions = summary.positions || [];
            const maxSlots = summary.max_positions || 3;
            const vacantCount = summary.vacant_slots !== undefined ? summary.vacant_slots : (maxSlots - positions.length);
            const cashPerSlot = summary.cash_per_vacant_slot || (summary.cash / (vacantCount || 1));

            // Update sidebar & header badges
            if (sidebarEquity) {
                sidebarEquity.textContent = `${Number(summary.total_equity || 20000).toLocaleString('pl-PL')} PLN`;
            }
            if (sidebarSlots) {
                sidebarSlots.textContent = `${positions.length} / ${maxSlots} Active`;
            }
            if (cashBadge) {
                cashBadge.textContent = `Available Cash: ${Number(summary.cash || 0).toLocaleString('pl-PL', { minimumFractionDigits: 2 })} PLN`;
            }

            // Update Contest Sync Status & Rank
            const contestBadge = document.getElementById('contestStatusBadge');
            const contestStatusText = document.getElementById('contestStatusText');
            const contestRankBadge = document.getElementById('contestRankBadge');
            const sidebarContestRank = document.getElementById('sidebarContestRank');
            const cs = summary.contest_sync || {};

            if (contestBadge && contestStatusText) {
                if (cs.status === 'synced') {
                    contestBadge.className = 'contest-badge synced';
                    const timePart = cs.last_synced ? cs.last_synced.split(' ')[1] : '';
                    contestStatusText.textContent = `Contest: Synced ${timePart}`;
                    contestBadge.title = `Verified with sigg.gpw.pl: ${Number(cs.contest_equity || summary.total_equity).toLocaleString('pl-PL')} PLN at ${cs.last_synced}`;
                } else if (cs.status === 'expired') {
                    contestBadge.className = 'contest-badge expired';
                    contestStatusText.textContent = 'Contest: Session Expired';
                    contestBadge.title = cs.error_message || 'Session expired. Paste refreshed cURL in Settings.';
                } else if (cs.status === 'error') {
                    contestBadge.className = 'contest-badge error';
                    contestStatusText.textContent = 'Contest: Error';
                    contestBadge.title = cs.error_message || 'Sync error';
                } else {
                    contestBadge.className = 'contest-badge unconfigured';
                    contestStatusText.textContent = 'Contest: Offline';
                    contestBadge.title = 'Paste DevTools cURL in Settings to connect live contest';
                }
            }

            if (contestRankBadge) {
                if (cs.rank) {
                    contestRankBadge.classList.remove('hidden');
                    contestRankBadge.textContent = `Rank: #${cs.rank}${cs.total_teams ? ' / ' + cs.total_teams : ''}`;
                } else {
                    contestRankBadge.classList.add('hidden');
                }
            }

            if (sidebarContestRank) {
                sidebarContestRank.textContent = cs.rank ? `#${cs.rank}` : 'N/A';
            }

            if (!grid) return;
            grid.innerHTML = '';

            for (let i = 0; i < maxSlots; i++) {
                const pos = positions[i];
                const slotNum = `SLOT ${i + 1}`;

                if (pos) {
                    const isPositive = (pos.pnl_pln >= 0);
                    const pnlClass = isPositive ? 'text-green' : 'text-red';
                    const pnlSign = isPositive ? '+' : '';
                    
                    let cardClass = 'slot-card occupied';
                    let badgeClass = 'badge badge-buy';
                    let badgeText = `DAY ${pos.sessions_held || 1} OF 3`;

                    if (pos.exit_signal === 'STOP_TRIGGERED') {
                        cardClass += ' stop-breached';
                        badgeClass = 'badge badge-loss font-bold';
                        badgeText = 'STOP BREACHED';
                    } else if (pos.exit_signal === '3D_EXIT_TODAY') {
                        cardClass += ' exit-warning';
                        badgeClass = 'badge badge-loss font-bold';
                        badgeText = '3D EXIT TODAY';
                    } else if (pos.exit_signal === 'RUNNER_HOLD') {
                        cardClass += ' runner-hold';
                        badgeClass = 'badge badge-buy font-bold';
                        badgeText = 'RUNNER EXCEPTION';
                    }

                    const card = document.createElement('div');
                    card.className = cardClass;
                    card.innerHTML = `
                        <div class="slot-header">
                            <span class="slot-num">${slotNum}</span>
                            <span class="${badgeClass}">${badgeText}</span>
                        </div>
                        <div class="slot-ticker-row">
                            <span class="slot-ticker">${pos.ticker}</span>
                            <span class="slot-pnl ${pnlClass}">${pnlSign}${Number(pos.pnl_pct || 0).toFixed(2)}% (${pnlSign}${Number(pos.pnl_pln || 0).toFixed(2)} PLN)</span>
                        </div>
                        <div class="slot-stats-grid">
                            <div class="slot-stat-row"><span>Shares</span><span>${pos.shares} szt.</span></div>
                            <div class="slot-stat-row"><span>Entry Price</span><span>${Number(pos.entry_price || 0).toFixed(2)} PLN</span></div>
                            <div class="slot-stat-row"><span>Current Price</span><span>${Number(pos.current_price || pos.entry_price || 0).toFixed(2)} PLN</span></div>
                            <div class="slot-stat-row"><span>2.2x ATR Stop</span><span class="${pos.current_price <= pos.stop_loss_price ? 'text-red font-bold' : ''}">${Number(pos.stop_loss_price || 0).toFixed(2)} PLN</span></div>
                        </div>
                        <div class="slot-footer-action">
                            <span class="text-xs text-muted" title="${pos.exit_reason || ''}">${pos.exit_reason || 'Holding position'}</span>
                            <button class="btn btn-xs secondary close-pos-btn" data-ticker="${pos.ticker}" data-price="${pos.current_price || pos.entry_price}">
                                <i data-lucide="x" class="icon-inline" style="width:12px;height:12px;"></i> Close Position
                            </button>
                        </div>
                    `;
                    grid.appendChild(card);
                } else {
                    const card = document.createElement('div');
                    card.className = 'slot-card vacant';
                    card.innerHTML = `
                        <div class="slot-header">
                            <span class="slot-num">${slotNum}</span>
                            <span class="badge badge-hold">VACANT</span>
                        </div>
                        <div class="slot-body">
                            <div class="slot-empty-title">Waiting for Breakout</div>
                            <p class="slot-empty-desc">Allocated: ~${Number(cashPerSlot).toLocaleString('pl-PL', { maximumFractionDigits: 0 })} PLN</p>
                        </div>
                    `;
                    grid.appendChild(card);
                }
            }

            // Bind click handlers for closing positions
            grid.querySelectorAll('.close-pos-btn').forEach(btn => {
                btn.addEventListener('click', async (e) => {
                    e.stopPropagation();
                    const ticker = btn.getAttribute('data-ticker');
                    const price = parseFloat(btn.getAttribute('data-price'));
                    if (confirm(`Confirm liquidation of ${ticker} at quote ~${price.toFixed(2)} PLN?`)) {
                        try {
                            const sRes = await fetch('/api/portfolio/sell', {
                                method: 'POST',
                                headers: { 'Content-Type': 'application/json' },
                                body: JSON.stringify({ ticker, exit_price: price, reason: 'Manual_Close' })
                            });
                            const sJson = await sRes.json();
                            if (sJson.status === 'success') {
                                showToast('Position Closed', sJson.message, 'warning');
                                fetchPortfolio();
                            } else {
                                showToast('Error', sJson.message || 'Failed to close position', 'error');
                            }
                        } catch (err) {
                            showToast('Error', 'Close request failed: ' + err, 'error');
                        }
                    }
                });
            });

            if (window.lucide) {
                window.lucide.createIcons();
            }
        } catch (e) {
            console.error('Error fetching portfolio:', e);
        }
    }

    // ==========================================
    // 0.3 QUICK EXECUTE ORDER MODAL
    // ==========================================
    let pendingExecuteData = null;

    function setupExecuteModal() {
        const modal = document.getElementById('executeModal');
        const closeBtn = document.getElementById('closeExecuteModalBtn');
        const cancelBtn = document.getElementById('cancelExecBtn');
        const confirmBtn = document.getElementById('confirmExecBtn');
        const execTicker = document.getElementById('execTicker');
        const execTicket = document.getElementById('execTicket');
        const execPriceInput = document.getElementById('execPriceInput');
        const execSharesInput = document.getElementById('execSharesInput');
        const execSlotNotice = document.getElementById('execSlotNotice');

        function closeModal() {
            if (modal) modal.classList.add('hidden');
            pendingExecuteData = null;
        }

        if (closeBtn) closeBtn.addEventListener('click', closeModal);
        if (cancelBtn) cancelBtn.addEventListener('click', closeModal);

        if (confirmBtn) {
            confirmBtn.addEventListener('click', async () => {
                if (!pendingExecuteData) return;
                const price = parseFloat(execPriceInput?.value || pendingExecuteData.price);
                const shares = parseInt(execSharesInput?.value || pendingExecuteData.shares, 10);

                if (!price || price <= 0 || !shares || shares <= 0) {
                    alert('Please enter valid positive numbers for price and shares.');
                    return;
                }

                confirmBtn.disabled = true;
                try {
                    const res = await fetch('/api/portfolio/buy', {
                        method: 'POST',
                        headers: { 'Content-Type': 'application/json' },
                        body: JSON.stringify({
                            ticker: pendingExecuteData.ticker,
                            price: price,
                            shares: shares,
                            atr: pendingExecuteData.atr || (price * 0.03)
                        })
                    });
                    const json = await res.json();
                    if (json.status === 'success') {
                        showToast('Position Executed', json.message, 'success');
                        playChime();
                        closeModal();
                        fetchPortfolio();
                    } else {
                        showToast('Execution Rejected', json.message || 'Cannot execute trade', 'error');
                    }
                } catch (err) {
                    showToast('Execution Error', 'Server error: ' + err, 'error');
                }
                confirmBtn.disabled = false;
            });
        }

        window.openExecuteModal = function(data) {
            pendingExecuteData = data;
            if (!modal) return;
            if (execTicker) execTicker.textContent = data.ticker;
            if (execTicket) execTicket.textContent = data.ticket || `KUP ${data.shares} szt. @ LIMIT ${data.price.toFixed(2)} PLN`;
            if (execPriceInput) execPriceInput.value = data.price;
            if (execSharesInput) execSharesInput.value = data.shares;
            if (execSlotNotice) execSlotNotice.textContent = `Will occupy next vacant portfolio slot. 3-Day burst countdown starts today.`;
            modal.classList.remove('hidden');
        };
    }

    // ==========================================
    // 0.4 SETTINGS & DISCORD ALERTS MODAL
    // ==========================================
    function setupSettingsModal() {
        const modal = document.getElementById('settingsModal');
        const openBtn = document.getElementById('openSettingsBtn');
        const openLink = document.getElementById('openSettingsLink');
        const closeBtn = document.getElementById('closeSettingsBtn');
        const saveBtn = document.getElementById('saveSettingsBtn');

        const webhookInput = document.getElementById('discordWebhookInput');
        const soundToggle = document.getElementById('soundAlertsToggle');
        const dispatch1635Toggle = document.getElementById('autoDispatch1635Toggle');
        const dispatch1650Toggle = document.getElementById('autoDispatch1650Toggle');

        const testWebhookBtn = document.getElementById('testWebhookBtn');
        const trigger1635Btn = document.getElementById('trigger1635Btn');
        const trigger1650Btn = document.getElementById('trigger1650Btn');

        // Contest Sync Modal Elements
        const contestCurlInput = document.getElementById('contestCurlInput');
        const contestRankCurlInput = document.getElementById('contestRankCurlInput');
        const contestSyncEnabledToggle = document.getElementById('contestSyncEnabledToggle');
        const testContestCurlBtn = document.getElementById('testContestCurlBtn');
        const testMockSyncBtn = document.getElementById('testMockSyncBtn');
        const contestCurlPreview = document.getElementById('contestCurlPreview');

        async function loadSettings() {
            try {
                const res = await fetch('/api/settings');
                const json = await res.json();
                if (json.status === 'success' && json.settings) {
                    const s = json.settings;
                    if (webhookInput && s.discord_webhook_url !== undefined) webhookInput.value = s.discord_webhook_url;
                    if (soundToggle && s.sound_alerts !== undefined) soundToggle.checked = Boolean(s.sound_alerts);
                    if (dispatch1635Toggle && s.auto_dispatch_1635 !== undefined) dispatch1635Toggle.checked = Boolean(s.auto_dispatch_1635);
                    if (dispatch1650Toggle && s.auto_dispatch_1650 !== undefined) dispatch1650Toggle.checked = Boolean(s.auto_dispatch_1650);
                }

                // Load Contest Sync Config
                const cRes = await fetch('/api/contest/config');
                const cJson = await cRes.json();
                if (cJson.status === 'success' && cJson.config) {
                    const c = cJson.config;
                    if (contestCurlInput && c.portfolio_curl !== undefined) contestCurlInput.value = c.portfolio_curl;
                    if (contestRankCurlInput && c.ranking_curl !== undefined) contestRankCurlInput.value = c.ranking_curl;
                    if (contestSyncEnabledToggle && c.enabled !== undefined) contestSyncEnabledToggle.checked = Boolean(c.enabled);
                }
            } catch (e) {
                console.error('Error loading settings:', e);
            }
        }

        function openModal() {
            if (!modal) return;
            loadSettings();
            modal.classList.remove('hidden');
        }

        function closeModal() {
            if (modal) modal.classList.add('hidden');
        }

        if (openBtn) openBtn.addEventListener('click', openModal);
        if (openLink) {
            openLink.addEventListener('click', (e) => {
                e.preventDefault();
                openModal();
            });
        }
        if (closeBtn) closeBtn.addEventListener('click', closeModal);

        if (saveBtn) {
            saveBtn.addEventListener('click', async () => {
                saveBtn.disabled = true;
                const payload = {
                    discord_webhook_url: webhookInput?.value?.trim() || '',
                    sound_alerts: soundToggle?.checked ?? true,
                    auto_dispatch_1635: dispatch1635Toggle?.checked ?? true,
                    auto_dispatch_1650: dispatch1650Toggle?.checked ?? true
                };

                const contestPayload = {
                    portfolio_curl: contestCurlInput?.value?.trim() || '',
                    ranking_curl: contestRankCurlInput?.value?.trim() || '',
                    enabled: contestSyncEnabledToggle?.checked ?? true
                };

                try {
                    // Save general alert settings
                    const res = await fetch('/api/settings', {
                        method: 'POST',
                        headers: { 'Content-Type': 'application/json' },
                        body: JSON.stringify(payload)
                    });
                    const json = await res.json();

                    // Save contest cURL settings
                    await fetch('/api/contest/config', {
                        method: 'POST',
                        headers: { 'Content-Type': 'application/json' },
                        body: JSON.stringify(contestPayload)
                    });

                    if (json.status === 'success') {
                        showToast('Settings Saved', 'Alerts and Contest Live Sync configurations updated.', 'success');
                        closeModal();
                        fetchPortfolio();
                    } else {
                        showToast('Save Error', json.message || 'Could not save settings.', 'error');
                    }
                } catch (err) {
                    showToast('Save Error', 'Error saving settings: ' + err, 'error');
                }
                saveBtn.disabled = false;
            });
        }

        if (testContestCurlBtn) {
            testContestCurlBtn.addEventListener('click', async () => {
                const curlStr = contestCurlInput?.value?.trim() || '';
                if (!curlStr) {
                    showToast('cURL Required', 'Please paste a cURL command copied from browser DevTools.', 'warning');
                    return;
                }
                testContestCurlBtn.disabled = true;
                if (contestCurlPreview) {
                    contestCurlPreview.className = 'contest-preview-box show';
                    contestCurlPreview.innerHTML = '<span style="color: #94a3b8;"><i data-lucide="loader" class="icon-inline" style="animation: spin 1s linear infinite;"></i> Parsing and testing connection to contest...</span>';
                }
                try {
                    // Save first
                    await fetch('/api/contest/config', {
                        method: 'POST',
                        headers: { 'Content-Type': 'application/json' },
                        body: JSON.stringify({
                            portfolio_curl: curlStr,
                            ranking_curl: contestRankCurlInput?.value?.trim() || '',
                            enabled: true
                        })
                    });

                    // Trigger sync
                    const sRes = await fetch('/api/contest/sync', { method: 'POST' });
                    const sJson = await sRes.json();

                    if (sJson.status === 'success' && sJson.data) {
                        const d = sJson.data;
                        const rankDisplay = d.rank ? `#${d.rank}` + (d.total_teams ? ` / ${d.total_teams}` : '') : 'N/A';
                        const posSummary = d.positions && d.positions.length > 0 
                            ? d.positions.map(p => `${p.symbol} (${p.shares} szt. @ ${p.entry_price.toFixed(2)} PLN)`).join(', ')
                            : 'Zero open positions (100% Cash)';

                        if (contestCurlPreview) {
                            contestCurlPreview.innerHTML = `
                                <div style="color: #34d399; font-weight: 700; margin-bottom: 4px;">✅ Contest Connection Verified & Synced</div>
                                <div>• <b>Live Equity:</b> ${d.portfolio_value.toFixed(2)} PLN</div>
                                <div>• <b>Available Cash:</b> ${d.cash.toFixed(2)} PLN</div>
                                <div>• <b>Contest Rank:</b> <span class="text-gold font-bold">${rankDisplay}</span></div>
                                <div>• <b>Positions:</b> ${d.positions.length} holdings &mdash; ${posSummary}</div>
                            `;
                        }
                        showToast('Contest Synced', `Verified ${d.portfolio_value.toFixed(2)} PLN, Rank ${rankDisplay}`, 'success');
                        playChime();
                        fetchPortfolio();
                    } else {
                        if (contestCurlPreview) {
                            contestCurlPreview.innerHTML = `
                                <div style="color: #fb7185; font-weight: 700; margin-bottom: 4px;">❌ Connection Failed</div>
                                <div>${sJson.message || 'Could not retrieve data from contest.'}</div>
                                <div style="color: #94a3b8; margin-top: 4px; font-size: 0.72rem;">Tip: In Chrome DevTools, make sure you copy a request that happened while logged into sigg.gpw.pl.</div>
                            `;
                        }
                        showToast('Connection Failed', sJson.message || 'Check your session cookie.', 'error');
                    }
                } catch (e) {
                    if (contestCurlPreview) {
                        contestCurlPreview.innerHTML = `<div style="color: #fb7185;">Error: ${e}</div>`;
                    }
                    showToast('Error', 'Request failed: ' + e, 'error');
                } finally {
                    testContestCurlBtn.disabled = false;
                }
            });
        }

        if (testMockSyncBtn) {
            testMockSyncBtn.addEventListener('click', async () => {
                testMockSyncBtn.disabled = true;
                try {
                    const mockPayload = {
                        "wartosc_portfela": 21850.0,
                        "wolne_srodki": 7250.0,
                        "miejsce": 28,
                        "liczba_uczestnikow": 3150,
                        "pozycje": [
                            { "symbol": "DINOPL", "ilosc": 20, "kurs_zakupu": 380.0, "kurs_biezacy": 395.0 },
                            { "symbol": "KGHM", "ilosc": 35, "kurs_zakupu": 140.0, "kurs_biezacy": 146.5 }
                        ]
                    };
                    const res = await fetch('/api/contest/mock_sync', {
                        method: 'POST',
                        headers: { 'Content-Type': 'application/json' },
                        body: JSON.stringify(mockPayload)
                    });
                    const json = await res.json();
                    if (json.status === 'success') {
                        if (contestCurlPreview) {
                            contestCurlPreview.className = 'contest-preview-box show';
                            contestCurlPreview.innerHTML = `
                                <div style="color: #facc15; font-weight: 700; margin-bottom: 4px;">🧪 Mock Payload Injected (Offline Mode)</div>
                                <div>• <b>Simulated Equity:</b> 21,850.00 PLN</div>
                                <div>• <b>Simulated Cash:</b> 7,250.00 PLN</div>
                                <div>• <b>Simulated Rank:</b> #28 / 3,150</div>
                                <div>• <b>Simulated Holdings:</b> DINOPL (20), KGHM (35)</div>
                            `;
                        }
                        showToast('Mock Contest Applied', 'Simulated contest state injected into Portfolio.', 'info');
                        playChime();
                        fetchPortfolio();
                    }
                } catch (err) {
                    showToast('Mock Error', 'Error applying mock: ' + err, 'error');
                } finally {
                    testMockSyncBtn.disabled = false;
                }
            });
        }

        if (testWebhookBtn) {
            testWebhookBtn.addEventListener('click', async () => {
                testWebhookBtn.disabled = true;
                try {
                    const webhookUrl = webhookInput?.value?.trim() || '';
                    const res = await fetch('/api/notifications/test', {
                        method: 'POST',
                        headers: { 'Content-Type': 'application/json' },
                        body: JSON.stringify({ webhook_url: webhookUrl })
                    });
                    const json = await res.json();
                    if (json.status === 'success') {
                        showToast('Discord Test Sent', json.message, 'success');
                        playChime();
                    } else {
                        showToast('Discord Test Failed', json.message, 'error');
                    }
                } catch (err) {
                    showToast('Error', 'Test failed: ' + err, 'error');
                }
                testWebhookBtn.disabled = false;
            });
        }

        if (trigger1635Btn) {
            trigger1635Btn.addEventListener('click', async () => {
                trigger1635Btn.disabled = true;
                try {
                    const res = await fetch('/api/notifications/dispatch', {
                        method: 'POST',
                        headers: { 'Content-Type': 'application/json' },
                        body: JSON.stringify({ window: '1635' })
                    });
                    const json = await res.json();
                    showToast('16:35 Pre-Close Dispatched', json.message || 'Alert sent.', json.status === 'success' ? 'success' : 'warning');
                    playChime();
                    pollNotifications();
                } catch (err) {
                    showToast('Dispatch Error', '' + err, 'error');
                }
                trigger1635Btn.disabled = false;
            });
        }

        if (trigger1650Btn) {
            trigger1650Btn.addEventListener('click', async () => {
                trigger1650Btn.disabled = true;
                try {
                    const res = await fetch('/api/notifications/dispatch', {
                        method: 'POST',
                        headers: { 'Content-Type': 'application/json' },
                        body: JSON.stringify({ window: '1650' })
                    });
                    const json = await res.json();
                    showToast('16:50 Fixing Sheet Dispatched', json.message || 'Action sheet sent.', json.status === 'success' ? 'success' : 'warning');
                    playChime();
                    pollNotifications();
                } catch (err) {
                    showToast('Dispatch Error', '' + err, 'error');
                }
                trigger1650Btn.disabled = false;
            });
        }

        loadSettings();
    }

    // ==========================================
    // 0.5 IN-APP NOTIFICATION POLLER
    // ==========================================
    let lastSeenNotificationId = 0;
    async function pollNotifications() {
        try {
            const res = await fetch('/api/notifications/active');
            const json = await res.json();
            if (json.status === 'success' && Array.isArray(json.data)) {
                if (lastSeenNotificationId === 0 && json.data.length > 0) {
                    // Seed last seen id on first poll so page load doesn't trigger historical alerts
                    lastSeenNotificationId = Math.max(...json.data.map(n => n.id || 0));
                    return;
                }
                const newNotes = json.data.filter(n => (n.id || 0) > lastSeenNotificationId);
                if (newNotes.length > 0) {
                    newNotes.forEach(n => {
                        showToast(n.title || 'Market Alert', n.message || '', n.level || 'info');
                        if ((n.id || 0) > lastSeenNotificationId) lastSeenNotificationId = n.id;
                    });
                    playChime();
                }
            }
        } catch (e) {
            // Ignore temporary network glitches
        }
    }

    // ==========================================
    // 0.8 CONTEST SYNC BUTTON LISTENER
    // ==========================================
    const syncContestBtn = document.getElementById('syncContestBtn');
    if (syncContestBtn) {
        syncContestBtn.addEventListener('click', async () => {
            const btnText = document.getElementById('syncContestBtnText');
            syncContestBtn.disabled = true;
            if (btnText) btnText.textContent = 'Syncing...';
            try {
                const res = await fetch('/api/contest/sync', { method: 'POST' });
                const json = await res.json();
                if (json.status === 'success') {
                    showToast('Contest Synced', json.message || 'Holding positions and equity synchronized.', 'success');
                    playChime();
                    fetchPortfolio();
                } else {
                    showToast('Sync Failed', json.message || 'Could not connect to contest. Verify cURL.', 'error');
                    fetchPortfolio();
                }
            } catch (err) {
                showToast('Sync Error', 'Network error connecting to local hub API: ' + err, 'error');
            } finally {
                syncContestBtn.disabled = false;
                if (btnText) btnText.textContent = 'Sync Contest';
            }
        });
    }

    // ==========================================
    // 1. LIVE SCANNER & PODIUM ENGINE
    // ==========================================
    const runScanBtn = document.getElementById('runScanBtn');
    const runScanBtnText = document.getElementById('runScanBtnText');
    const scanTableBody = document.getElementById('scanTableBody') || document.querySelector('#scanTable tbody');
    const scanEmpty = document.getElementById('scanEmpty');
    const scanTableHeader = document.getElementById('scanTableHeader');
    const scanProgressCard = document.getElementById('scanProgressCard');
    const scanProgressBar = document.getElementById('scanProgressBar');
    const scanProgressStatus = document.getElementById('scanProgressStatus');
    const scanProgressCount = document.getElementById('scanProgressCount');
    const podiumCardsGrid = document.getElementById('podiumCardsGrid');
    const podiumStatusBadge = document.getElementById('podiumStatusBadge');
    const podiumSubtitle = document.getElementById('podiumSubtitle');
    const filterAllBtn = document.getElementById('filterAllBtn');
    const filterBuysBtn = document.getElementById('filterBuysBtn');
    const ledgerSearchInput = document.getElementById('ledgerSearchInput');
    const ledgerTotalCount = document.getElementById('ledgerTotalCount');
    const ledgerBuysCount = document.getElementById('ledgerBuysCount');

    let _allScannedStocks = [];
    let _activeLedgerFilter = 'all';
    let _ledgerSearchTerm = '';
    let _activeScanSource = null;

    if (runScanBtn) {
        runScanBtn.addEventListener('click', () => {
            runLiveScanner();
        });
    }

    if (filterAllBtn) {
        filterAllBtn.addEventListener('click', () => {
            _activeLedgerFilter = 'all';
            filterAllBtn.classList.add('active');
            if (filterBuysBtn) filterBuysBtn.classList.remove('active');
            renderLedgerTable();
        });
    }

    if (filterBuysBtn) {
        filterBuysBtn.addEventListener('click', () => {
            _activeLedgerFilter = 'buys';
            filterBuysBtn.classList.add('active');
            if (filterAllBtn) filterAllBtn.classList.remove('active');
            renderLedgerTable();
        });
    }

    if (ledgerSearchInput) {
        ledgerSearchInput.addEventListener('input', (e) => {
            _ledgerSearchTerm = e.target.value || '';
            renderLedgerTable();
        });
    }

    function renderMarketRegime(regimeData) {
        const banner = document.getElementById('marketRegimeBanner');
        const badge = document.getElementById('regimeBadge');
        const desc = document.getElementById('regimeActionText');
        const metrics = document.getElementById('regimeMetrics');
        if (!banner || !regimeData) return;

        const reg = regimeData.regime || 'GREEN';
        banner.className = 'regime-banner';
        if (reg === 'RED') banner.classList.add('regime-red');
        else if (reg === 'YELLOW') banner.classList.add('regime-yellow');
        else banner.classList.add('regime-green');

        if (badge) badge.textContent = `${reg} REGIME — ${regimeData.status_label || ''}`;
        if (desc) desc.textContent = regimeData.action_msg || '';
        if (metrics) {
            const chg = Number(regimeData.index_change_pct || 0);
            const brd = Number(regimeData.breadth_above_sma20_pct || 0);
            metrics.textContent = `WIG140 Breadth > SMA20: ${brd.toFixed(1)}% | Daily Δ: ${chg >= 0 ? '+' : ''}${chg.toFixed(2)}%`;
        }
    }

    function renderScannerBacktestSummary(summary) {
        if (!summary) return;
        const avgEl = document.getElementById('scanBtAvgReturn');
        const wrEl = document.getElementById('scanBtWinRate');
        const tpsEl = document.getElementById('scanBtTradesPerSeason');
        const totEl = document.getElementById('scanBtTotalTrades');
        const bestSEl = document.getElementById('scanBtBestSeason');
        const bestREl = document.getElementById('scanBtBestReturn');
        const worstSEl = document.getElementById('scanBtWorstSeason');
        const worstREl = document.getElementById('scanBtWorstReturn');
        const notesEl = document.getElementById('scannerBtNotes');

        const ret = Number(summary.avg_return_pct || 0);
        if (avgEl) {
            avgEl.textContent = `${ret >= 0 ? '+' : ''}${ret.toFixed(2)}%`;
            avgEl.className = `kpi-value ${ret >= 0 ? 'text-green' : 'text-red'}`;
        }
        if (wrEl) wrEl.textContent = `Win Rate: ${summary.overall_win_rate || 0}%`;
        if (tpsEl) {
            const tps = summary.avg_trades_per_season || ((summary.total_trades || 0) / 6).toFixed(1);
            tpsEl.textContent = `${tps} / season`;
        }
        if (totEl) totEl.textContent = `Total 6-Yr Trades: ${summary.total_trades || 0}`;

        if (summary.best_season && bestSEl && bestREl) {
            bestSEl.textContent = summary.best_season.season;
            bestREl.textContent = `Return: +${summary.best_season.return_pct}% (${Number(summary.best_season.final_capital).toLocaleString('pl-PL')} PLN)`;
        }
        if (summary.worst_season && worstSEl && worstREl) {
            worstSEl.textContent = summary.worst_season.season;
            const wRet = Number(summary.worst_season.return_pct || 0);
            worstREl.textContent = `Return: ${wRet >= 0 ? '+' : ''}${wRet}% (${Number(summary.worst_season.final_capital).toLocaleString('pl-PL')} PLN)`;
        }
        if (notesEl && summary.notes) {
            notesEl.textContent = summary.notes;
        }
    }

    function populateScanTable(data, type, strategy) {
        if (!scanTableBody) return;
        
        if (!data || data.length === 0) {
            if (scanEmpty) {
                scanEmpty.classList.remove('hidden');
                scanEmpty.textContent = "No scan data available. Click 'Run Scanner Now'.";
            }
            scanTableBody.innerHTML = '';
            if (scanCountBadge) scanCountBadge.textContent = "0 signals";
            return;
        }
        
        if (type === 'closest') {
            if (scanEmpty) scanEmpty.classList.add('hidden');
            if (scanCountBadge) scanCountBadge.textContent = `${data.length} watchlist (regime protected)`;
        } else {
            if (scanEmpty) scanEmpty.classList.add('hidden');
            if (scanCountBadge) scanCountBadge.textContent = `${data.length} qualified signals`;
        }

        if (strategy === 'breakout_trend') {
            if (scanTableHeader) {
                scanTableHeader.innerHTML = `
                    <tr>
                        <th>Ticker</th>
                        <th>Close (PLN)</th>
                        <th>Runner Score</th>
                        <th>Order Ticket (Whole Shares)</th>
                        <th>Day Δ%</th>
                        <th>10-Day High</th>
                        <th>Vol Surge</th>
                        <th>Turnover</th>
                        <th>Trailing Stop (2.0x ATR)</th>
                        <th>Target &amp; R:R</th>
                        <th>5-Yr BT</th>
                        <th>Action</th>
                        <th>Chart</th>
                    </tr>
                `;
            }
        } else if (strategy === 'squeeze_ignition') {
            if (scanTableHeader) {
                scanTableHeader.innerHTML = `
                    <tr>
                        <th>Ticker</th>
                        <th>Close (PLN)</th>
                        <th>Runner Score</th>
                        <th>Order Ticket (Whole Shares)</th>
                        <th>Day Δ%</th>
                        <th>ATR Coil</th>
                        <th>TR / ATR</th>
                        <th>Vol Surge</th>
                        <th>Stop / Hold</th>
                        <th>5-Yr BT</th>
                        <th>Action</th>
                        <th>Chart</th>
                    </tr>
                `;
            }
        } else if (strategy === 'breakout' || strategy === 'home_run') {
            if (scanTableHeader) {
                scanTableHeader.innerHTML = `
                    <tr>
                        <th>Ticker</th>
                        <th>Close (PLN)</th>
                        <th>Trend (SMA50)</th>
                        <th>Vol Surge</th>
                        <th>Stop Loss</th>
                        <th>Target</th>
                        <th>5-Yr Backtest History</th>
                        <th>Action</th>
                        <th>Chart</th>
                    </tr>
                `;
            }
        } else {
            if (scanTableHeader) {
                scanTableHeader.innerHTML = `
                    <tr>
                        <th>Ticker</th>
                        <th>Close (PLN)</th>
                        <th>Trend (SMA50)</th>
                        <th>RSI (14)</th>
                        <th>Vol Surge</th>
                        <th>Stop Loss</th>
                        <th>5-Yr Backtest History</th>
                        <th>Action</th>
                        <th>Chart</th>
                    </tr>
                `;
            }
        }
        
        scanTableBody.innerHTML = '';
        data.forEach(row => {
            const tr = document.createElement('tr');
            const ticker = row.Ticker || '';
            const tvSymbol = (row.Yahoo_Ticker || row.Ticker || '').replace('.WA', '').replace('.W', '');
            const tvUrl = `https://pl.tradingview.com/symbols/GPW-${tvSymbol}/`;
            const isBuy = (row.Strategy_Signal === 'Buy');
            const isUptrend = (row.Trend_SMA50 === 'Uptrend');
            const btStats = row.BT_Stats || 'No past triggers';
            const closeP = Number(row.Close || 0);
            const shares = row.Order_Shares || Math.floor(6600 / (closeP || 1));
            const cleanSym = ticker.replace('.WA', '').replace('.W', '');
            const safeTicket = row.Order_Ticket || `KUPNO | ${cleanSym} | ${shares} szt. | LIMIT ${(closeP * 1.005).toFixed(2)} PLN`;

            if (strategy === 'breakout_trend') {
                const dayGain = Number(row.Day_Gain_Pct || 0);
                const volS = Number(row.Volume_Surge || 0);
                const rScore = Number(row.Runner_Score || 0);
                const atrVal = (row.ATR_Pct ? (closeP * (row.ATR_Pct / 100)) : (closeP * 0.03)).toFixed(2);
                const targetP = row.Target ? Number(row.Target).toFixed(2) : '-';
                const rrVal = row.RR_Ratio ? `${Number(row.RR_Ratio).toFixed(1)}:1` : '-';
                const turnoverK = Math.round(Number(row.Turnover_PLN || 0) / 1000);

                tr.innerHTML = `
                    <td>
                        <strong>${ticker}</strong>
                        <div class="text-xs text-muted">${row.Name || ''}</div>
                    </td>
                    <td class="font-mono">${closeP.toFixed(2)}</td>
                    <td class="font-mono font-bold text-green">★ ${rScore.toFixed(2)}</td>
                    <td class="font-mono text-xs">
                        <div style="display:flex; align-items:center; gap:0.4rem;">
                            <span>${safeTicket}</span>
                            <button class="btn btn-xs secondary copy-ticket-btn" data-ticket="${encodeURIComponent(safeTicket)}" title="Copy ticket to clipboard for GPW broker">
                                Copy
                            </button>
                        </div>
                    </td>
                    <td class="font-mono ${dayGain >= 2.5 ? 'text-green font-bold' : (dayGain < 0 ? 'text-red' : '')}">${dayGain >= 0 ? '+' : ''}${dayGain.toFixed(2)}%</td>
                    <td class="font-mono">${Number(row.Breakout_Target || 0).toFixed(2)}</td>
                    <td class="font-mono ${volS >= 1.5 ? 'text-green font-bold' : ''}">${volS.toFixed(2)}x</td>
                    <td class="font-mono text-xs">${turnoverK}k PLN</td>
                    <td class="font-mono text-red">${row.Stop_Loss ? Number(row.Stop_Loss).toFixed(2) : '-'} <span class="text-muted">/ Trailing</span></td>
                    <td class="font-mono text-xs">${targetP} <span class="text-muted">(${rrVal})</span></td>
                    <td class="font-mono text-xs">${btStats}</td>
                    <td>
                        <div style="display:flex; align-items:center; gap:0.4rem;">
                            <span class="badge ${isBuy ? 'badge-buy' : 'badge-hold'}">${row.Strategy_Signal || 'Hold'}</span>
                            <button class="btn btn-xs primary exec-order-btn" data-ticker="${ticker}" data-price="${closeP}" data-shares="${shares}" data-ticket="${encodeURIComponent(safeTicket)}" data-atr="${atrVal}">
                                Execute
                            </button>
                        </div>
                    </td>
                    <td>
                        <a href="${tvUrl}" target="_blank" class="tv-link">TV &nearr;</a>
                    </td>
                `;
            } else if (strategy === 'squeeze_ignition') {
                const dayGain = Number(row.Day_Gain_Pct || 0);
                const trRatio = Number(row.TR_Ratio || 0);
                const cPos = Number(row.Close_Pos || 0);
                const volS = Number(row.Volume_Surge || 0);
                const rScore = Number(row.Runner_Score || 0);
                const atrVal = (row.ATR_Pct ? (closeP * (row.ATR_Pct / 100)) : (closeP * 0.03)).toFixed(2);

                tr.innerHTML = `
                    <td><strong>${ticker}</strong></td>
                    <td class="font-mono">${closeP.toFixed(2)}</td>
                    <td class="font-mono font-bold text-green">★ ${rScore.toFixed(2)}</td>
                    <td class="font-mono text-xs">
                        <div style="display:flex; align-items:center; gap:0.4rem;">
                            <span>${safeTicket}</span>
                            <button class="btn btn-xs secondary copy-ticket-btn" data-ticket="${encodeURIComponent(safeTicket)}" title="Copy ticket to clipboard for GPW broker">
                                Copy
                            </button>
                        </div>
                    </td>
                    <td class="font-mono ${dayGain >= 2.5 ? 'text-green font-bold' : (dayGain < 0 ? 'text-red' : '')}">${dayGain >= 0 ? '+' : ''}${dayGain.toFixed(2)}%</td>
                    <td class="font-mono">${Number(row.ATR_Pct || 0).toFixed(2)}%</td>
                    <td class="font-mono ${trRatio >= 1.3 ? 'text-green font-bold' : ''}">${trRatio.toFixed(2)}x</td>
                    <td class="font-mono ${volS >= 1.5 ? 'text-green font-bold' : ''}">${volS.toFixed(2)}x</td>
                    <td class="font-mono text-red">${row.Stop_Loss ? Number(row.Stop_Loss).toFixed(2) : '-'} <span class="text-muted">/ 3D</span></td>
                    <td class="font-mono text-xs">${btStats}</td>
                    <td>
                        <div style="display:flex; align-items:center; gap:0.4rem;">
                            <span class="badge ${isBuy ? 'badge-buy' : 'badge-hold'}">${row.Strategy_Signal || 'Hold'}</span>
                            <button class="btn btn-xs primary exec-order-btn" data-ticker="${ticker}" data-price="${closeP}" data-shares="${shares}" data-ticket="${encodeURIComponent(safeTicket)}" data-atr="${atrVal}">
                                Execute
                            </button>
                        </div>
                    </td>
                    <td>
                        <a href="${tvUrl}" target="_blank" class="tv-link">TV &nearr;</a>
                    </td>
                `;
            } else if (strategy === 'breakout' || strategy === 'home_run') {
                tr.innerHTML = `
                    <td><strong>${ticker}</strong></td>
                    <td class="font-mono">${Number(row.Close || 0).toFixed(2)}</td>
                    <td>
                        <span class="badge ${isUptrend ? 'badge-buy' : 'badge-loss'}">${row.Trend_SMA50 || 'Uptrend'}</span>
                    </td>
                    <td class="font-mono ${Number(row.Volume_Surge || 0) >= 1.25 ? 'text-green font-bold' : ''}">${Number(row.Volume_Surge || 0).toFixed(2)}x</td>
                    <td class="font-mono text-red">${row.Stop_Loss ? Number(row.Stop_Loss).toFixed(2) : '-'}</td>
                    <td class="font-mono text-green">${row.Target ? Number(row.Target).toFixed(2) : '-'}</td>
                    <td class="font-mono text-xs">${btStats}</td>
                    <td>
                        <div style="display:flex; align-items:center; gap:0.4rem;">
                            <span class="badge ${isBuy ? 'badge-buy' : 'badge-hold'}">${row.Strategy_Signal || 'Hold'}</span>
                            <button class="btn btn-xs primary exec-order-btn" data-ticker="${ticker}" data-price="${closeP}" data-shares="${shares}" data-ticket="${encodeURIComponent(safeTicket)}" data-atr="${(closeP * 0.03).toFixed(2)}">
                                Execute
                            </button>
                        </div>
                    </td>
                    <td>
                        <a href="${tvUrl}" target="_blank" class="tv-link">TV &nearr;</a>
                    </td>
                `;
            } else {
                tr.innerHTML = `
                    <td><strong>${ticker}</strong></td>
                    <td class="font-mono">${Number(row.Close || 0).toFixed(2)}</td>
                    <td>
                        <span class="badge ${isUptrend ? 'badge-buy' : 'badge-loss'}">${row.Trend_SMA50 || 'Uptrend'}</span>
                    </td>
                    <td class="font-mono">${Number(row.RSI || 0).toFixed(1)}</td>
                    <td class="font-mono">${Number(row.Volume_Surge || 0).toFixed(2)}x</td>
                    <td class="font-mono text-red">${row.Stop_Loss ? Number(row.Stop_Loss).toFixed(2) : '-'}</td>
                    <td class="font-mono text-xs">${btStats}</td>
                    <td>
                        <div style="display:flex; align-items:center; gap:0.4rem;">
                            <span class="badge ${isBuy ? 'badge-buy' : 'badge-hold'}">${row.Strategy_Signal || 'Hold'}</span>
                            <button class="btn btn-xs primary exec-order-btn" data-ticker="${ticker}" data-price="${closeP}" data-shares="${shares}" data-ticket="${encodeURIComponent(safeTicket)}" data-atr="${(closeP * 0.03).toFixed(2)}">
                                Execute
                            </button>
                        </div>
                    </td>
                    <td>
                        <a href="${tvUrl}" target="_blank" class="tv-link">TV &nearr;</a>
                    </td>
                `;
            }
            scanTableBody.appendChild(tr);
        });

        // Wire copy ticket buttons
        scanTableBody.querySelectorAll('.copy-ticket-btn').forEach(btn => {
            btn.addEventListener('click', (e) => {
                e.stopPropagation();
                const raw = decodeURIComponent(btn.getAttribute('data-ticket') || '');
                navigator.clipboard.writeText(raw).then(() => {
                    showToast('Ticket Copied', `"${raw}" copied to clipboard. Ready to paste in broker.`, 'info', 3000);
                }).catch(() => {
                    prompt('Copy order ticket manually:', raw);
                });
            });
        });

        // Wire execute order buttons
        scanTableBody.querySelectorAll('.exec-order-btn').forEach(btn => {
            btn.addEventListener('click', (e) => {
                e.stopPropagation();
                const ticker = btn.getAttribute('data-ticker');
                const price = parseFloat(btn.getAttribute('data-price'));
                const shares = parseInt(btn.getAttribute('data-shares'), 10);
                const ticket = decodeURIComponent(btn.getAttribute('data-ticket') || '');
                const atr = parseFloat(btn.getAttribute('data-atr'));

                if (window.openExecuteModal) {
                    window.openExecuteModal({ ticker, price, shares, ticket, atr });
                }
            });
        });

        if (window.lucide) {
            window.lucide.createIcons();
        }
    }

    function fetchScanResults() {
        const strategy = getActiveStrategy();
        fetch('/api/results/scan?strategy=' + strategy).then(r => r.json()).then(j => {
            if (j.market_regime) renderMarketRegime(j.market_regime);
            if (j.backtest_summary) renderScannerBacktestSummary(j.backtest_summary);
            if (j.status === 'success') {
                populateScanTable(j.data, j.type, strategy);
            } else {
                if (scanEmpty) scanEmpty.classList.remove('hidden');
                if (scanTableBody) scanTableBody.innerHTML = '';
            }
        }).catch(() => {});
    }

    // ==========================================
    // 2. SELF-SERVICE 5-YEAR BACKTEST & CHARTS
    // ==========================================
    let equityChartInstance = null;
    let seasonBarChartInstance = null;
    let winLossChartInstance = null;

    const runBacktestBtn = document.getElementById('runBacktestBtn');
    const presetChampionBtn = document.getElementById('presetChampionBtn');
    const presetBurstBtn = document.getElementById('presetBurstBtn');
    const presetStrictBtn = document.getElementById('presetStrictBtn');
    const backtestLoading = document.getElementById('backtestLoading');
    const seasonSummaryBody = document.getElementById('seasonSummaryBody');
    const tradesLogBody = document.getElementById('tradesLogBody');

    function setFormParams(p) {
        const setVal = (id, val) => {
            const el = document.getElementById(id);
            if (el && val !== undefined) el.value = String(val);
        };
        setVal('btHoldDays', p.max_hold_days);
        setVal('btHardStop', p.hard_time_stop);
        setVal('btMaxPos', p.max_positions);
        setVal('btBreakoutDays', p.breakout_period);
        setVal('btAtrMin', p.atr_min_pct);
        setVal('btAtrMax', p.atr_max_pct);
        setVal('btTrMin', p.min_tr_ratio);
        setVal('btGainMin', p.min_day_gain_pct);
        setVal('btGainMax', p.max_day_gain_pct);
        setVal('btClosePos', p.min_close_pos);
        setVal('btVolMin', p.volume_surge_multiplier);
        setVal('btTurnoverMin', p.min_turnover_pln);
        setVal('btStopAtr', p.trailing_stop_atr_mult);
        setVal('btExecTiming', p.exec_timing);
        setVal('btCommPct', p.commission_pct);
        setVal('btUseRegime', p.use_market_regime);
    }

    function readFormParams() {
        const num = (id, fallback) => {
            const el = document.getElementById(id);
            if (!el) return fallback;
            const v = parseFloat(el.value);
            return isNaN(v) ? fallback : v;
        };
        const bool = (id, fallback) => {
            const el = document.getElementById(id);
            return el ? (el.value === 'true') : fallback;
        };
        const str = (id, fallback) => {
            const el = document.getElementById(id);
            return el ? el.value : fallback;
        };
        return {
            max_hold_days_without_new_high: Math.round(num('btHoldDays', 3)),
            hard_time_stop: bool('btHardStop', true),
            max_positions: Math.round(num('btMaxPos', 3)),
            breakout_period: Math.round(num('btBreakoutDays', 10)),
            atr_min_pct: num('btAtrMin', 2.0) / 100.0,
            atr_max_pct: num('btAtrMax', 8.0) / 100.0,
            min_tr_ratio: num('btTrMin', 1.3),
            min_day_gain_pct: num('btGainMin', 2.5) / 100.0,
            max_day_gain_pct: num('btGainMax', 12.0) / 100.0,
            min_close_pos: num('btClosePos', 0.70),
            volume_surge_multiplier: num('btVolMin', 1.5),
            min_turnover_pln: num('btTurnoverMin', 150000),
            trailing_stop_atr_mult: num('btStopAtr', 2.0),
            exec_timing: str('btExecTiming', 'close_auction'),
            commission_pct: num('btCommPct', 0.29) / 100.0,
            use_market_regime: bool('btUseRegime', true)
        };
    }

    if (presetChampionBtn) {
        presetChampionBtn.addEventListener('click', () => {
            if (strategySelect) strategySelect.value = 'breakout_trend';
            setFormParams({
                max_hold_days: 7,
                hard_time_stop: false,
                max_positions: 2,
                breakout_period: 10,
                atr_min_pct: 2.0,
                atr_max_pct: 15.0,
                min_tr_ratio: 1.0,
                min_day_gain_pct: 1.0,
                max_day_gain_pct: 35.0,
                min_close_pos: 0.70,
                volume_surge_multiplier: 1.5,
                min_turnover_pln: 400000,
                trailing_stop_atr_mult: 2.0,
                exec_timing: 'close_auction',
                commission_pct: 0.29,
                use_market_regime: true
            });
            runBacktestBtn.click();
        });
    }

    if (presetBurstBtn) {
        presetBurstBtn.addEventListener('click', () => {
            if (strategySelect) strategySelect.value = 'squeeze_ignition';
            setFormParams({
                max_hold_days: 3,
                hard_time_stop: true,
                max_positions: 3,
                breakout_period: 10,
                atr_min_pct: 2.0,
                atr_max_pct: 8.0,
                min_tr_ratio: 1.3,
                min_day_gain_pct: 2.5,
                max_day_gain_pct: 12.0,
                min_close_pos: 0.70,
                volume_surge_multiplier: 1.5,
                min_turnover_pln: 150000,
                trailing_stop_atr_mult: 2.0,
                exec_timing: 'close_auction',
                commission_pct: 0.29,
                use_market_regime: true
            });
            runBacktestBtn.click();
        });
    }

    if (presetStrictBtn) {
        presetStrictBtn.addEventListener('click', () => {
            if (strategySelect) strategySelect.value = 'squeeze_ignition';
            setFormParams({
                max_hold_days: 4,
                hard_time_stop: false,
                max_positions: 3,
                breakout_period: 10,
                atr_min_pct: 1.5,
                atr_max_pct: 4.0,
                min_tr_ratio: 1.8,
                min_day_gain_pct: 3.0,
                max_day_gain_pct: 9.0,
                min_close_pos: 0.75,
                volume_surge_multiplier: 2.0,
                min_turnover_pln: 400000,
                trailing_stop_atr_mult: 2.2,
                exec_timing: 'close_auction',
                commission_pct: 0.29,
                use_market_regime: true
            });
            runBacktestBtn.click();
        });
    }

    async function safeJsonFetch(url, options) {
        const res = await fetch(url, options);
        const text = await res.text();
        if (!text || !text.trim()) {
            return { status: 'running', message: 'Server warming up...' };
        }
        try {
            return JSON.parse(text);
        } catch (err) {
            return { status: 'running', message: 'Waiting for background worker...' };
        }
    }

    function pollBacktestUntilDone(strategy) {
        let attempts = 0;
        const pollTimer = setInterval(async () => {
            attempts++;
            try {
                const pollJson = await safeJsonFetch('/api/results/backtest?strategy=' + strategy);
                if (pollJson.status === 'success') {
                    clearInterval(pollTimer);
                    renderBacktestData(pollJson);
                    if (pollJson.summary) renderScannerBacktestSummary(pollJson.summary);
                    if (backtestLoading) backtestLoading.classList.add('hidden');
                    if (runBacktestBtn) runBacktestBtn.disabled = false;
                    showToast('Backtest Complete', `Evaluated across 6 historical seasons.`, 'success');
                } else if (pollJson.status === 'error' || attempts > 60) {
                    clearInterval(pollTimer);
                    if (backtestLoading) backtestLoading.classList.add('hidden');
                    if (runBacktestBtn) runBacktestBtn.disabled = false;
                    if (pollJson.message) showToast('Backtest Error', pollJson.message, 'error');
                }
            } catch (e) {
                if (attempts > 60) {
                    clearInterval(pollTimer);
                    if (backtestLoading) backtestLoading.classList.add('hidden');
                    if (runBacktestBtn) runBacktestBtn.disabled = false;
                }
            }
        }, 1500);
    }

    if (runBacktestBtn) {
        runBacktestBtn.addEventListener('click', async () => {
            runBacktestBtn.disabled = true;
            if (backtestLoading) backtestLoading.classList.remove('hidden');
            const activeStrat = getActiveStrategy();

            try {
                const customParams = readFormParams();
                const json = await safeJsonFetch('/api/backtest', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({
                        strategy: activeStrat,
                        params: customParams
                    })
                });
                
                if (json.status === 'success') {
                    renderBacktestData(json);
                    if (json.summary) renderScannerBacktestSummary(json.summary);
                    if (backtestLoading) backtestLoading.classList.add('hidden');
                    runBacktestBtn.disabled = false;
                    showToast('Backtest Complete', 'Custom backtest executed successfully.', 'success');
                } else if (json.status === 'running') {
                    pollBacktestUntilDone(activeStrat);
                } else {
                    showToast('Backtest Error', json.message || 'Unknown error', 'error');
                    if (backtestLoading) backtestLoading.classList.add('hidden');
                    runBacktestBtn.disabled = false;
                }
            } catch (e) {
                pollBacktestUntilDone(activeStrat);
            }
        });
    }

    function fetchBacktestResults() {
        const strategy = getActiveStrategy();
        fetch('/api/results/backtest?strategy=' + strategy)
            .then(r => r.json())
            .then(json => {
                if (json.status === 'success') {
                    renderBacktestData(json);
                    if (json.summary) {
                        renderScannerBacktestSummary(json.summary);
                        if (json.summary.active_params) {
                            setFormParams(json.summary.active_params);
                        }
                    }
                }
            })
            .catch(() => {});
    }

    function renderBacktestData(data) {
        if (!data) return;

        const summary = data.summary || {};
        const kpiAvgReturn = document.getElementById('kpiAvgReturn');
        const kpiWinRate = document.getElementById('kpiWinRate');
        const kpiBestSeason = document.getElementById('kpiBestSeason');
        const kpiBestReturn = document.getElementById('kpiBestReturn');
        const kpiTradesPerSeason = document.getElementById('kpiTradesPerSeason');
        const kpiTotalTrades = document.getElementById('kpiTotalTrades');
        const kpiFeesPaid = document.getElementById('kpiFeesPaid');

        if (kpiAvgReturn) {
            const ret = Number(summary.avg_return_pct || 0);
            kpiAvgReturn.textContent = `${ret >= 0 ? '+' : ''}${ret.toFixed(2)}%`;
            kpiAvgReturn.className = `kpi-value ${ret >= 0 ? 'text-green' : 'text-red'}`;
        }
        if (kpiWinRate) {
            kpiWinRate.textContent = `Win Rate: ${summary.overall_win_rate || 0}%`;
        }
        if (kpiTradesPerSeason) {
            const tps = summary.avg_trades_per_season || ((summary.total_trades || 0) / 6).toFixed(1);
            kpiTradesPerSeason.textContent = `${tps} / season`;
        }
        if (kpiTotalTrades) {
            kpiTotalTrades.textContent = `Total 6-Yr Trades: ${summary.total_trades || 0}`;
        }
        if (kpiFeesPaid) {
            kpiFeesPaid.textContent = `6-Yr Fees Paid: ${Number(summary.total_fees_pln || 0).toLocaleString('pl-PL')} PLN`;
        }
        if (summary.best_season && kpiBestSeason && kpiBestReturn) {
            kpiBestSeason.textContent = summary.best_season.season;
            kpiBestReturn.textContent = `Return: +${summary.best_season.return_pct}% (${Number(summary.best_season.final_capital).toLocaleString('pl-PL')} PLN)`;
        }

        const warningEl = document.getElementById('backtestWarning');
        if (warningEl && summary.notes) {
            warningEl.innerHTML = `<strong>Engine Configuration:</strong> ${summary.notes}`;
        }

        renderEquityCurveChart(data.equity_curves || {});
        renderSeasonBarChart(data.seasons || []);
        renderWinLossChart(data.trades || []);
        populateSeasonSummaryTable(data.seasons || []);
        populateTradesLogTable(data.trades || []);
    }

    function renderEquityCurveChart(curves) {
        const ctx = document.getElementById('equityCurveChart');
        if (!ctx) return;

        let maxDays = 0;
        Object.values(curves).forEach(pts => {
            if (pts.length > maxDays) maxDays = pts.length;
        });

        if (maxDays === 0) maxDays = 40;
        const labels = Array.from({ length: maxDays }, (_, i) => `Day ${i + 1}`);

        const colors = {
            "2020/2021": "#10b981",
            "2021/2022": "#a855f7",
            "2022/2023": "#3b82f6",
            "2023/2024": "#06b6d4",
            "2024/2025": "#f59e0b",
            "2025/2026": "#22c55e"
        };

        const datasets = [];
        Object.entries(curves).forEach(([season, pts]) => {
            const color = colors[season] || '#64748b';
            datasets.push({
                label: season,
                data: pts.map(p => p.value),
                borderColor: color,
                backgroundColor: 'transparent',
                borderWidth: 2.2,
                pointRadius: 0,
                pointHoverRadius: 4,
                tension: 0.25
            });
        });

        datasets.push({
            label: '20,000 PLN Baseline',
            data: Array(maxDays).fill(20000),
            borderColor: 'rgba(255, 255, 255, 0.2)',
            borderWidth: 1.5,
            borderDash: [5, 5],
            pointRadius: 0,
            fill: false
        });

        if (equityChartInstance) {
            equityChartInstance.destroy();
        }

        equityChartInstance = new Chart(ctx.getContext('2d'), {
            type: 'line',
            data: { labels, datasets },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                interaction: { mode: 'index', intersect: false },
                plugins: {
                    legend: {
                        position: 'top',
                        labels: {
                            color: '#94a3b8',
                            font: { family: 'JetBrains Mono', size: 11 },
                            boxWidth: 14
                        }
                    },
                    tooltip: {
                        backgroundColor: '#1e293b',
                        titleColor: '#f8fafc',
                        bodyColor: '#e2e8f0',
                        borderColor: '#334155',
                        borderWidth: 1,
                        callbacks: {
                            label: function(context) {
                                let label = context.dataset.label || '';
                                if (label) label += ': ';
                                if (context.parsed.y !== null) {
                                    label += Number(context.parsed.y).toLocaleString('pl-PL', { minimumFractionDigits: 2 }) + ' PLN';
                                }
                                return label;
                            }
                        }
                    }
                },
                scales: {
                    x: {
                        grid: { color: 'rgba(51, 65, 85, 0.4)' },
                        ticks: { color: '#64748b', font: { family: 'JetBrains Mono', size: 10 } }
                    },
                    y: {
                        grid: { color: 'rgba(51, 65, 85, 0.4)' },
                        ticks: {
                            color: '#64748b',
                            font: { family: 'JetBrains Mono', size: 10 },
                            callback: (val) => val.toLocaleString('pl-PL') + ' PLN'
                        }
                    }
                }
            }
        });
    }

    function renderSeasonBarChart(seasons) {
        const ctx = document.getElementById('seasonBarChart');
        if (!ctx) return;

        const labels = seasons.map(s => s.season);
        const dataVals = seasons.map(s => s.return_pct);
        const bgColors = dataVals.map(v => v >= 0 ? '#10b981' : '#f43f5e');

        if (seasonBarChartInstance) {
            seasonBarChartInstance.destroy();
        }

        seasonBarChartInstance = new Chart(ctx.getContext('2d'), {
            type: 'bar',
            data: {
                labels,
                datasets: [{
                    label: 'Return (%)',
                    data: dataVals,
                    backgroundColor: bgColors,
                    borderRadius: 4
                }]
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                plugins: {
                    legend: { display: false },
                    tooltip: {
                        callbacks: {
                            label: (ctx) => `${ctx.parsed.y >= 0 ? '+' : ''}${ctx.parsed.y}% Return`
                        }
                    }
                },
                scales: {
                    x: {
                        grid: { display: false },
                        ticks: { color: '#64748b', font: { family: 'JetBrains Mono', size: 10 } }
                    },
                    y: {
                        grid: { color: 'rgba(51, 65, 85, 0.4)' },
                        ticks: {
                            color: '#64748b',
                            font: { family: 'JetBrains Mono', size: 10 },
                            callback: (val) => val + '%'
                        }
                    }
                }
            }
        });
    }

    function renderWinLossChart(trades) {
        const ctx = document.getElementById('winLossChart');
        if (!ctx) return;

        const wins = trades.filter(t => (t.PnL || 0) > 0).length;
        const losses = trades.filter(t => (t.PnL || 0) <= 0).length;
        const total = wins + losses || 1;

        if (winLossChartInstance) {
            winLossChartInstance.destroy();
        }

        winLossChartInstance = new Chart(ctx.getContext('2d'), {
            type: 'doughnut',
            data: {
                labels: ['Winning Trades', 'Losing Trades'],
                datasets: [{
                    data: [wins, losses],
                    backgroundColor: ['#10b981', '#f43f5e'],
                    borderColor: '#0f172a',
                    borderWidth: 2
                }]
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                plugins: {
                    legend: {
                        position: 'bottom',
                        labels: { color: '#94a3b8', font: { family: 'JetBrains Mono', size: 11 } }
                    },
                    tooltip: {
                        callbacks: {
                            label: (ctx) => ` ${ctx.label}: ${ctx.parsed} (${((ctx.parsed / total) * 100).toFixed(1)}%)`
                        }
                    }
                },
                cutout: '68%'
            }
        });
    }

    let currentBacktestTrades = [];

    function populateSeasonSummaryTable(seasons) {
        if (!seasonSummaryBody) return;
        seasonSummaryBody.innerHTML = '';

        if (!seasons || seasons.length === 0) {
            seasonSummaryBody.innerHTML = '<tr><td colspan="14" class="text-center py-4 text-muted">No season results available.</td></tr>';
            return;
        }

        // Dynamically synchronize the Season / Year filter dropdown
        const seasonSelect = document.getElementById('tradeFilterSeason');
        if (seasonSelect && seasons && seasons.length > 0) {
            const currentSelected = seasonSelect.value;
            seasonSelect.innerHTML = '<option value="ALL">All Seasons (2020–2026)</option>';
            seasons.forEach(s => {
                const opt = document.createElement('option');
                opt.value = s.season;
                opt.textContent = `${s.season} (${s.edition || ('SIGG ' + s.year)})`;
                seasonSelect.appendChild(opt);
            });
            if (currentSelected && Array.from(seasonSelect.options).some(o => o.value === currentSelected)) {
                seasonSelect.value = currentSelected;
            }
        }

        seasons.forEach(s => {
            const tr = document.createElement('tr');
            const isPositive = (s.return_pct >= 0);
            
            const seasonLabel = s.edition ? 
                `<strong>${s.season}</strong><span class="cell-sub font-mono">${s.edition}</span>` : 
                `<strong>${s.season}</strong>`;

            const winTxt = s.biggest_winner ? 
                `<span class="badge badge-buy font-bold" title="${s.biggest_winner.company_name || s.biggest_winner.ticker}">${s.biggest_winner.ticker} (+${s.biggest_winner.pnl_pct}%)</span>` : 
                '<span class="text-muted text-xs">-</span>';
                
            const lossTxt = s.biggest_loser ? 
                `<span class="badge badge-loss font-bold" title="${s.biggest_loser.company_name || s.biggest_loser.ticker}">${s.biggest_loser.ticker} (${s.biggest_loser.pnl_pct}%)</span>` : 
                '<span class="text-muted text-xs">-</span>';

            const sharpeVal = s.sharpe_ratio !== undefined ? Number(s.sharpe_ratio).toFixed(2) : '0.00';
            const sharpeClass = Number(sharpeVal) >= 1.0 ? 'text-green font-bold' : (Number(sharpeVal) < 0 ? 'text-red' : '');
            const feesVal = Number(s.total_fees_pln || 0).toLocaleString('pl-PL', { minimumFractionDigits: 2, maximumFractionDigits: 2 });

            tr.innerHTML = `
                <td>${seasonLabel}</td>
                <td class="font-mono text-muted text-xs">${s.start_date} &rarr; ${s.end_date}</td>
                <td class="font-mono">${Number(s.initial_capital).toLocaleString('pl-PL')} PLN</td>
                <td class="font-mono font-bold ${isPositive ? 'text-green' : 'text-red'}">${Number(s.final_capital).toLocaleString('pl-PL')} PLN</td>
                <td class="font-mono ${isPositive ? 'text-green' : 'text-red'}">${isPositive ? '+' : ''}${Number(s.net_profit).toLocaleString('pl-PL')} PLN</td>
                <td class="font-mono font-bold ${isPositive ? 'text-green' : 'text-red'}">${isPositive ? '+' : ''}${s.return_pct}%</td>
                <td class="font-mono">${s.win_rate}%</td>
                <td class="font-mono">${s.profit_factor}</td>
                <td class="font-mono text-red">-${s.max_drawdown}%</td>
                <td class="font-mono ${sharpeClass}">${sharpeVal}</td>
                <td class="font-mono text-muted text-xs">${feesVal} PLN</td>
                <td>${winTxt}</td>
                <td>${lossTxt}</td>
                <td class="font-mono">${s.trades_count}</td>
            `;
            seasonSummaryBody.appendChild(tr);
        });
    }

    const normalizeQueryStr = (str) => {
        return String(str || '')
            .normalize('NFD')
            .replace(/[\u0300-\u036f]/g, '')
            .toLowerCase();
    };

    function applyTradesFiltersAndRender() {
        if (!tradesLogBody) return;
        tradesLogBody.innerHTML = '';

        const seasonFilter = document.getElementById('tradeFilterSeason')?.value || 'ALL';
        const rawSearchInput = (document.getElementById('tradeSearchInput')?.value || '').trim();
        const searchInput = normalizeQueryStr(rawSearchInput);
        const outcomeFilter = document.getElementById('tradeFilterOutcome')?.value || 'ALL';

        const filtered = currentBacktestTrades.filter(t => {
            // Season filter
            if (seasonFilter !== 'ALL') {
                const seasonStr = String(t.Season || '');
                const yearStr = String(t.Year || '');
                const editionStr = String(t.Edition || '');
                if (seasonStr !== seasonFilter && yearStr !== seasonFilter && editionStr !== seasonFilter && !seasonStr.includes(seasonFilter)) {
                    return false;
                }
            }

            // Search input (ticker, company name, sigg symbol, exit reason) with Polish diacritic insensitivity
            if (searchInput) {
                const tickerMatch = normalizeQueryStr(t.Ticker).includes(searchInput);
                const nameMatch = normalizeQueryStr(t.Company_Name).includes(searchInput);
                const symMatch = normalizeQueryStr(t.SIGG_Symbol).includes(searchInput);
                const reasonMatch = normalizeQueryStr(t.Exit_Reason).includes(searchInput);
                if (!tickerMatch && !nameMatch && !symMatch && !reasonMatch) {
                    return false;
                }
            }

            // Outcome filter
            if (outcomeFilter === 'WIN') {
                const pnl = Number(t.Net_PnL !== undefined ? t.Net_PnL : t.PnL || 0);
                if (pnl <= 0) return false;
            } else if (outcomeFilter === 'LOSS') {
                const pnl = Number(t.Net_PnL !== undefined ? t.Net_PnL : t.PnL || 0);
                if (pnl > 0) return false;
            }

            return true;
        });

        const countBadge = document.getElementById('tradesLogCountBadge');
        if (countBadge) {
            countBadge.textContent = `${filtered.length} of ${currentBacktestTrades.length} operations`;
        }

        if (filtered.length === 0) {
            tradesLogBody.innerHTML = '<tr><td colspan="15" class="text-center py-4 text-muted">No operations matching the selected filter criteria.</td></tr>';
            return;
        }

        const reversed = [...filtered].reverse();
        reversed.forEach(t => {
            const tr = document.createElement('tr');
            const netPnl = Number(t.Net_PnL !== undefined ? t.Net_PnL : t.PnL || 0);
            const isWin = (netPnl > 0);
            const pnlSign = isWin ? '+' : '';
            const pnlClass = isWin ? 'text-green font-bold' : 'text-red font-bold';

            const seasonBadge = t.Edition ? 
                `<span class="badge badge-season">${t.Season || '-'}</span><span class="cell-sub">${t.Edition}</span>` : 
                `<span class="badge badge-season">${t.Season || '-'}</span>`;

            const companyName = t.Company_Name || t.SIGG_Symbol || '';
            const tickerCell = `<strong>${t.Ticker}</strong>` + (companyName ? `<span class="cell-sub">${companyName}</span>` : '');

            const entryTime = t.Entry_Timestamp || (t.Entry_Date + (t.Entry_Time ? ' ' + t.Entry_Time : ''));
            const exitTime = t.Exit_Timestamp || (t.Exit_Date + (t.Exit_Time ? ' ' + t.Exit_Time : ''));

            const posVal = Number(t.Position_Value_PLN !== undefined ? t.Position_Value_PLN : ((t.Shares || 0) * (t.Entry_Price || 0))).toLocaleString('pl-PL', { minimumFractionDigits: 2, maximumFractionDigits: 2 });
            const feesVal = Number(t.Total_Fees_PLN !== undefined ? t.Total_Fees_PLN : (t.Fees_PLN || 0)).toFixed(2);
            const entryCommVal = t.Entry_Commission_PLN !== undefined ? ` (entry: ${Number(t.Entry_Commission_PLN).toFixed(2)})` : '';

            const sessionsHeld = t.Sessions_Held !== undefined ? t.Sessions_Held : (t.Days_Held || 1);
            const calDays = t.Calendar_Days !== undefined ? t.Calendar_Days : '-';

            const peakPrice = t.Peak_Price !== undefined ? Number(t.Peak_Price).toFixed(2) : null;
            const maxGainPct = t.Max_Potential_Gain_Pct !== undefined ? Number(t.Max_Potential_Gain_Pct).toFixed(2) : null;
            const peakCell = peakPrice ? 
                `<span class="font-mono">${peakPrice} PLN</span><span class="cell-sub text-green">+${maxGainPct}% peak</span>` : 
                `<span class="text-muted">-</span>`;

            const execType = t.Exec_Type || 'Close Auction';
            const execBadgeClass = execType.toLowerCase().includes('open') ? 'badge-hold' : 'badge-buy';

            tr.innerHTML = `
                <td>${seasonBadge}</td>
                <td>${tickerCell}</td>
                <td class="font-mono text-xs">${entryTime}</td>
                <td><span class="badge ${execBadgeClass} text-xs">${execType}</span></td>
                <td class="font-mono font-bold">${t.Shares || '-'}</td>
                <td class="font-mono">${Number(t.Entry_Price || 0).toFixed(2)}</td>
                <td class="font-mono text-xs">${posVal} PLN</td>
                <td class="font-mono text-xs">${exitTime}</td>
                <td class="font-mono">${Number(t.Exit_Price || 0).toFixed(2)}</td>
                <td class="font-mono text-muted text-xs" title="Total commissions${entryCommVal}">${feesVal} PLN</td>
                <td class="font-mono ${pnlClass}">${pnlSign}${netPnl.toFixed(2)} PLN</td>
                <td class="font-mono ${pnlClass}">${pnlSign}${Number(t.PnL_Pct || 0).toFixed(2)}%</td>
                <td class="font-mono text-xs">${sessionsHeld} sessions <span class="cell-sub">${calDays} cal days</span></td>
                <td>${peakCell}</td>
                <td class="font-mono text-xs text-muted"><span class="badge ${isWin ? 'badge-buy' : 'badge-loss'}">${t.Exit_Reason || 'Strategy_Exit'}</span></td>
            `;
            tradesLogBody.appendChild(tr);
        });
    }

    function populateTradesLogTable(trades) {
        currentBacktestTrades = trades || [];
        applyTradesFiltersAndRender();
    }

    // ==========================================
    // 3. STRATEGY BLUEPRINT (.MD) VIEWER
    // ==========================================
    const markdownContent = document.getElementById('markdownContent');
    const refreshMdBtn = document.getElementById('refreshMdBtn');

    function loadStrategyMarkdown() {
        if (!markdownContent) return;
        fetch('/api/strategy_md')
            .then(r => r.json())
            .then(j => {
                if (j.status === 'success') {
                    if (window.marked) {
                        markdownContent.innerHTML = window.marked.parse(j.content);
                    } else {
                        markdownContent.innerHTML = `<pre class="font-mono">${j.content}</pre>`;
                    }
                } else {
                    markdownContent.textContent = 'Error loading Strategy.md: ' + j.message;
                }
            })
            .catch(e => {
                markdownContent.textContent = 'Failed to fetch Strategy.md: ' + e;
            });
    }

    if (refreshMdBtn) {
        refreshMdBtn.addEventListener('click', loadStrategyMarkdown);
    }

    // ==========================================
    // 4. OPTIMIZER LOGIC
    // ==========================================
    const runOptBtn = document.getElementById('runOptBtn');
    const optLoading = document.getElementById('optLoading');
    const optTableBody = document.querySelector('#optTable tbody');
    const optEmpty = document.getElementById('optEmpty');
    const optTableHeader = document.getElementById('optTableHeader');

    if (runOptBtn) {
        runOptBtn.addEventListener('click', async () => {
            runOptBtn.disabled = true;
            if (optLoading) optLoading.classList.remove('hidden');
            if (optEmpty) optEmpty.classList.add('hidden');
            if (optTableBody) optTableBody.innerHTML = '';

            try {
                const res = await fetch('/api/optimize', { 
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ strategy: getActiveStrategy() })
                });
                const json = await res.json();
                
                if (json.status === 'success') {
                    populateOptTable(json.data, getActiveStrategy());
                    showToast('Optimizer Complete', 'Top parameter configurations evaluated across 5 years.', 'success');
                } else {
                    showToast('Optimizer Error', json.message || 'Error running optimizer', 'error');
                }
            } catch (e) {
                showToast('Optimizer Error', 'Optimizer request failed: ' + e, 'error');
            }

            if (optLoading) optLoading.classList.add('hidden');
            runOptBtn.disabled = false;
        });
    }

    function populateOptTable(data, strategy) {
        if (!optTableBody) return;
        
        if (!data || data.length === 0) {
            if (optEmpty) {
                optEmpty.classList.remove('hidden');
                optEmpty.textContent = "No optimization results. Click Run 5-Year Optimization.";
            }
            optTableBody.innerHTML = '';
            return;
        }
        
        if (optEmpty) optEmpty.classList.add('hidden');
        
        if (strategy !== 'macd_rsi') {
            if (optTableHeader) {
                optTableHeader.innerHTML = `
                    <tr>
                        <th>Rank</th>
                        <th>Breakout Days</th>
                        <th>ATR Min</th>
                        <th>Vol Surge</th>
                        <th>Stop Loss</th>
                        <th>Avg Return</th>
                        <th>Avg WinRate</th>
                    </tr>
                `;
            }
        } else {
            if (optTableHeader) {
                optTableHeader.innerHTML = `
                    <tr>
                        <th>Rank</th>
                        <th>MACD Fast/Slow</th>
                        <th>RSI Thresh</th>
                        <th>Stop Loss</th>
                        <th>Avg Return</th>
                        <th>Avg WinRate</th>
                    </tr>
                `;
            }
        }

        optTableBody.innerHTML = '';
        data.slice(0, 10).forEach((row, i) => {
            const tr = document.createElement('tr');
            if (strategy !== 'macd_rsi') {
                tr.innerHTML = `
                    <td><strong>#${i + 1}</strong></td>
                    <td class="font-mono">${row.Breakout}</td>
                    <td class="font-mono">${(row.ATR_Min * 100).toFixed(1)}%</td>
                    <td class="font-mono">${row.Vol_Surge}x</td>
                    <td class="font-mono">${row.Trailing_Stop}x ATR</td>
                    <td class="font-mono font-bold text-green">+${row.Avg_Return}%</td>
                    <td class="font-mono">${row.Avg_Winrate}%</td>
                `;
            } else {
                tr.innerHTML = `
                    <td><strong>#${i + 1}</strong></td>
                    <td class="font-mono">${row.MACD_Fast} / ${row.MACD_Slow}</td>
                    <td class="font-mono">${row.RSI_Threshold}</td>
                    <td class="font-mono">${row.Trailing_Stop}x ATR</td>
                    <td class="font-mono font-bold text-green">+${row.Avg_Return}%</td>
                    <td class="font-mono">${row.Avg_Winrate}%</td>
                `;
            }
            optTableBody.appendChild(tr);
        });
    }

    function fetchOptResults() {
        const strategy = getActiveStrategy();
        fetch('/api/results/optimizer?strategy=' + strategy).then(r => r.json()).then(j => {
            if (j.status === 'success') {
                populateOptTable(j.data, strategy);
            } else {
                if (optEmpty) optEmpty.classList.remove('hidden');
                if (optTableBody) optTableBody.innerHTML = '';
            }
        }).catch(() => {});
    }

    // ==========================================
    // INITIAL BOOTSTRAP
    // ==========================================
    // Trade Audit Log Filter & Export Listeners
    const tradeFilterSeason = document.getElementById('tradeFilterSeason');
    if (tradeFilterSeason) tradeFilterSeason.addEventListener('change', applyTradesFiltersAndRender);

    const tradeSearchInput = document.getElementById('tradeSearchInput');
    if (tradeSearchInput) tradeSearchInput.addEventListener('input', applyTradesFiltersAndRender);

    const tradeFilterOutcome = document.getElementById('tradeFilterOutcome');
    if (tradeFilterOutcome) tradeFilterOutcome.addEventListener('change', applyTradesFiltersAndRender);

    const exportTradesCsvBtn = document.getElementById('exportTradesCsvBtn');
    if (exportTradesCsvBtn) {
        exportTradesCsvBtn.addEventListener('click', () => {
            const strat = getActiveStrategy();
            const seasonVal = document.getElementById('tradeFilterSeason')?.value || 'ALL';
            window.location.href = `/api/backtest/trades/export?strategy=${strat}&season=${encodeURIComponent(seasonVal)}`;
        });
    }

    const exportSeasonsCsvBtn = document.getElementById('exportSeasonsCsvBtn');
    if (exportSeasonsCsvBtn) {
        exportSeasonsCsvBtn.addEventListener('click', () => {
            const strat = getActiveStrategy();
            window.location.href = `/api/backtest/seasons/export?strategy=${strat}`;
        });
    }

    setupExecuteModal();
    setupSettingsModal();
    fetchScanResults();
    fetchPortfolio();
    fetchBacktestResults();
    fetchOptResults();
    loadStrategyMarkdown();
    pollNotifications();

    // Standby Polling Loops:
    // Notifications every 12 seconds
    setInterval(pollNotifications, 12000);
    // Quotes / portfolio refresh every 30 seconds
    setInterval(fetchPortfolio, 30000);
});
