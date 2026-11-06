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
        const regObj = (typeof regime === 'object' && regime !== null) ? regime : { regime: String(regime) };
        const reg = (regObj.regime || 'GREEN').toUpperCase();
        mobileRegimeStrip.className = 'regime-strip';
        if (reg === 'RED') mobileRegimeStrip.classList.add('regime-red');
        else if (reg === 'YELLOW') mobileRegimeStrip.classList.add('regime-yellow');
        else mobileRegimeStrip.classList.add('regime-green');

        if (mobileRegimeTag) mobileRegimeTag.textContent = `${reg} REGIME`;
        if (mobileRegimeText) {
            const brd = Number(regObj.breadth_above_sma20_pct || (reg === 'RED' ? 32 : 55)).toFixed(0);
            const chg = Number(regObj.index_change_pct || 0);
            mobileRegimeText.textContent = `Breadth: ${brd}% | Δ: ${chg >= 0 ? '+' : ''}${chg.toFixed(1)}% | Max 3 Slots`;
        }
    }

    const mobileStrategySelect = document.getElementById('mobileStrategySelect');
    const mobileFeedTitle = document.getElementById('mobileFeedTitle');

    function getMobileStrategy() {
        return mobileStrategySelect ? mobileStrategySelect.value : 'breakout_trend';
    }

    if (mobileStrategySelect) {
        mobileStrategySelect.addEventListener('change', () => {
            const strat = getMobileStrategy();
            if (mobileFeedTitle) {
                const text = mobileStrategySelect.options[mobileStrategySelect.selectedIndex]?.text || '';
                mobileFeedTitle.textContent = text.split('(')[0].trim() + ' Signals';
            }
            fetchMobileSignals();
        });
    }

    let _mobileAllScanned = [];
    let _mobileFilter = 'all';
    let _mobileSearch = '';
    let _mobileActiveScanSource = null;

    const mobilePodiumGrid = document.getElementById('mobilePodiumGrid');
    const mobilePodiumBadge = document.getElementById('mobilePodiumBadge');
    const mobileRunBtnText = document.getElementById('mobileRunBtnText');
    const mobileScanProgressCard = document.getElementById('mobileScanProgressCard');
    const mobileProgressText = document.getElementById('mobileProgressText');
    const mobileProgressCount = document.getElementById('mobileProgressCount');
    const mobileProgressBar = document.getElementById('mobileProgressBar');
    const mobileSearchInput = document.getElementById('mobileSearchInput');
    const mobileFilterAllBtn = document.getElementById('mobileFilterAllBtn');
    const mobileFilterBuysBtn = document.getElementById('mobileFilterBuysBtn');

    if (mobileFilterAllBtn) {
        mobileFilterAllBtn.addEventListener('click', () => {
            _mobileFilter = 'all';
            mobileFilterAllBtn.style.background = 'var(--accent)';
            mobileFilterAllBtn.style.color = '#fff';
            if (mobileFilterBuysBtn) {
                mobileFilterBuysBtn.style.background = 'var(--bg-card)';
                mobileFilterBuysBtn.style.color = 'var(--text-secondary)';
            }
            renderSignalCards();
        });
    }

    if (mobileFilterBuysBtn) {
        mobileFilterBuysBtn.addEventListener('click', () => {
            _mobileFilter = 'buys';
            mobileFilterBuysBtn.style.background = 'var(--accent)';
            mobileFilterBuysBtn.style.color = '#fff';
            if (mobileFilterAllBtn) {
                mobileFilterAllBtn.style.background = 'var(--bg-card)';
                mobileFilterAllBtn.style.color = 'var(--text-secondary)';
            }
            renderSignalCards();
        });
    }

    if (mobileSearchInput) {
        mobileSearchInput.addEventListener('input', (e) => {
            _mobileSearch = (e.target.value || '').trim().toLowerCase();
            renderSignalCards();
        });
    }

    function renderMobilePodium(podiumData, regimeData) {
        if (!mobilePodiumGrid) return;
        const regStr = typeof regimeData === 'string' ? regimeData : (regimeData?.regime || podiumData?.regime || '');
        const isRed = (podiumData && podiumData.is_locked) || (String(regStr).toUpperCase() === 'RED');

        if (isRed) {
            if (mobilePodiumBadge) {
                mobilePodiumBadge.textContent = '🔴 LOCKED';
                mobilePodiumBadge.style.background = 'rgba(239, 68, 68, 0.2)';
                mobilePodiumBadge.style.color = '#f87171';
            }
            mobilePodiumGrid.innerHTML = `
                <div class="mobile-podium-locked" style="padding: 1rem; background: rgba(239,68,68,0.1); border: 1px solid rgba(239,68,68,0.3); border-radius: 10px;">
                    <div style="display: flex; align-items: center; gap: 0.5rem; color: #ef4444; font-weight: 700; font-size: 0.85rem; margin-bottom: 0.35rem;">
                        <i data-lucide="lock" style="width: 18px; height: 18px;"></i>
                        <span>KILL SWITCH ACTIVE (RED REGIME)</span>
                    </div>
                    <p style="font-size: 0.75rem; color: #fca5a5; line-height: 1.35; margin: 0 0 0.5rem 0;">
                        WIG breadth is weak. Zero stock purchases permitted today. 100% Cash preserved (0 downside risk).
                    </p>
                    <div style="display: flex; flex-direction: column; gap: 0.3rem;">
                        <span style="font-size: 0.72rem; color: #cbd5e1; background: rgba(0,0,0,0.3); padding: 4px 8px; border-radius: 6px;">🛡️ Slot 1: 100% Cash Preserved</span>
                        <span style="font-size: 0.72rem; color: #cbd5e1; background: rgba(0,0,0,0.3); padding: 4px 8px; border-radius: 6px;">🛡️ Slot 2: 100% Cash Preserved</span>
                        <span style="font-size: 0.72rem; color: #cbd5e1; background: rgba(0,0,0,0.3); padding: 4px 8px; border-radius: 6px;">🛡️ Slot 3: 100% Cash Preserved</span>
                    </div>
                </div>
            `;
        } else {
            const slots = (podiumData && podiumData.slots) ? podiumData.slots : [];
            const picks = (podiumData && podiumData.picks) ? podiumData.picks : [];
            const allocatedCount = picks.length;

            if (mobilePodiumBadge) {
                mobilePodiumBadge.textContent = `🟢 UNLOCKED (${allocatedCount} / 3)`;
                mobilePodiumBadge.style.background = 'rgba(16, 185, 129, 0.2)';
                mobilePodiumBadge.style.color = '#34d399';
            }

            let html = '<div style="display: flex; flex-direction: column; gap: 0.6rem;">';
            for (let i = 0; i < 3; i++) {
                const slotNum = i + 1;
                const slotItem = slots[i] || (picks[i] ? { ...picks[i], is_allocated: true, slot: slotNum } : { slot: slotNum, is_allocated: false });
                const isAllocated = Boolean(slotItem && slotItem.is_allocated && slotItem.ticker);

                if (isAllocated) {
                    const dayGain = Number(slotItem.day_gain_pct || 0);
                    const closeP = Number(slotItem.close || 0);
                    const shares = slotItem.order_shares || Math.floor(6600 / (closeP || 1));
                    const cleanSym = (slotItem.ticker || '').replace('.WA', '').replace('.W', '');
                    const ticket = slotItem.order_ticket || `KUPNO | ${cleanSym} | ${shares} szt. | LIMIT ${(closeP * 1.005).toFixed(2)} PLN`;
                    const atrVal = ((closeP || 0) * 0.03).toFixed(2);
                    const tvUrl = `https://pl.tradingview.com/symbols/GPW-${cleanSym}/`;

                    html += `
                        <div class="mobile-podium-card" style="border: 1px solid rgba(16,185,129,0.35); background: rgba(16,185,129,0.04); border-radius: 10px; padding: 0.75rem;">
                            <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 0.35rem;">
                                <span style="font-size: 0.72rem; font-weight: 800; color: #34d399; text-transform: uppercase;">Slot ${slotNum} • Allocated</span>
                                <span class="badge-signal-buy" style="font-size: 0.68rem; padding: 2px 6px;">${slotItem.tier || 'BUY'}</span>
                            </div>
                            <div style="display: flex; justify-content: space-between; align-items: baseline;">
                                <div>
                                    <strong style="font-size: 0.95rem; color: #fff;">${slotItem.ticker}</strong>
                                    <span style="font-size: 0.72rem; color: var(--text-muted); margin-left: 4px;">${slotItem.name || ''}</span>
                                </div>
                                <div style="font-family: var(--font-mono); font-size: 0.9rem; font-weight: 700; color: #fff;">
                                    ${closeP.toFixed(2)} PLN
                                    <span style="font-size: 0.75rem; margin-left: 4px;" class="${dayGain >= 0 ? 'text-green' : 'text-red'}">${dayGain >= 0 ? '+' : ''}${dayGain.toFixed(1)}%</span>
                                </div>
                            </div>
                            <div style="display: flex; gap: 0.5rem; margin: 0.4rem 0; font-size: 0.72rem; color: var(--text-muted); font-family: var(--font-mono);">
                                <span>Score: <b style="color: #34d399;">★ ${(slotItem.runner_score || 0).toFixed(2)}</b></span>
                                <span>Vol: ${(slotItem.volume_surge || 1).toFixed(1)}x</span>
                                <span>Stop: <span style="color: #f87171;">${Number(slotItem.stop_loss || 0).toFixed(2)}</span></span>
                            </div>
                            <div style="display: flex; gap: 0.4rem; margin-top: 0.4rem;">
                                <button class="btn-card-copy mobile-copy-btn" style="flex: 1; padding: 5px;" data-ticket="${encodeURIComponent(ticket)}">
                                    <i data-lucide="copy" style="width: 12px; height: 12px;"></i> Copy
                                </button>
                                <button class="btn-card-exec mobile-exec-btn" style="flex: 1; padding: 5px;" data-ticker="${slotItem.ticker}" data-price="${closeP}" data-shares="${shares}" data-ticket="${encodeURIComponent(ticket)}" data-atr="${atrVal}">
                                    <i data-lucide="zap" style="width: 12px; height: 12px;"></i> Execute
                                </button>
                                <a href="${tvUrl}" target="_blank" class="btn-card-chart" style="padding: 5px 8px;">TV &nearr;</a>
                            </div>
                        </div>
                    `;
                } else {
                    html += `
                        <div class="mobile-podium-card vacant" style="border: 1px dashed rgba(255,255,255,0.15); background: rgba(255,255,255,0.02); border-radius: 10px; padding: 0.75rem;">
                            <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 0.35rem;">
                                <span style="font-size: 0.72rem; font-weight: 700; color: var(--text-muted); text-transform: uppercase;">Slot ${slotNum} • 33.3% Capital</span>
                                <span style="font-size: 0.68rem; padding: 2px 6px; background: rgba(255,255,255,0.05); color: var(--text-muted); border-radius: 4px;">100% CASH</span>
                            </div>
                            <div style="display: flex; align-items: center; gap: 0.5rem; margin-top: 0.25rem;">
                                <i data-lucide="shield-check" style="width: 18px; height: 18px; color: #10b981; flex-shrink: 0;"></i>
                                <div>
                                    <div style="font-size: 0.8rem; font-weight: 700; color: #fff;">Preserved in Cash</div>
                                    <div style="font-size: 0.72rem; color: var(--text-muted);">
                                        ${allocatedCount > 0 ? `Only ${allocatedCount} stock(s) met buy criteria.` : 'No stock met strict buy criteria today.'}
                                    </div>
                                </div>
                            </div>
                        </div>
                    `;
                }
            }
            html += '</div>';
            mobilePodiumGrid.innerHTML = html;
        }

        mobilePodiumGrid.querySelectorAll('.mobile-copy-btn').forEach(btn => {
            btn.onclick = (e) => {
                e.stopPropagation();
                triggerHaptic(30);
                const raw = decodeURIComponent(btn.getAttribute('data-ticket') || '');
                navigator.clipboard.writeText(raw).then(() => {
                    showMobileToast('Ticket Copied! 📋', 'Pasted to clipboard.', 'info', 2500);
                }).catch(() => {
                    prompt('Copy ticket manually:', raw);
                });
            };
        });

        mobilePodiumGrid.querySelectorAll('.mobile-exec-btn').forEach(btn => {
            btn.onclick = (e) => {
                e.stopPropagation();
                triggerHaptic(20);
                const ticker = btn.getAttribute('data-ticker');
                const price = parseFloat(btn.getAttribute('data-price'));
                const shares = parseInt(btn.getAttribute('data-shares'), 10);
                const ticket = decodeURIComponent(btn.getAttribute('data-ticket') || '');
                const atr = parseFloat(btn.getAttribute('data-atr'));

                openMobileExecSheet({ ticker, price, shares, ticket, atr });
            };
        });

        if (window.lucide) window.lucide.createIcons();
    }

    function renderSignalCards(data) {
        if (data && Array.isArray(data)) {
            _mobileAllScanned = data;
        }
        if (!mobileSignalsFeed) return;
        mobileSignalsFeed.innerHTML = '';

        const total = _mobileAllScanned.length;
        const buysCount = _mobileAllScanned.filter(s => s.Strategy_Signal === 'Buy').length;
        if (mobileSignalCount) {
            mobileSignalCount.textContent = `${buysCount} buys / ${total} scanned`;
        }

        const filtered = _mobileAllScanned.filter(row => {
            if (_mobileFilter === 'buys' && row.Strategy_Signal !== 'Buy') return false;
            if (_mobileSearch) {
                const t = (row.Ticker || '').toLowerCase();
                const n = (row.Name || '').toLowerCase();
                if (!t.includes(_mobileSearch) && !n.includes(_mobileSearch)) return false;
            }
            return true;
        });

        if (filtered.length === 0) {
            if (mobileSignalsEmpty) {
                mobileSignalsEmpty.classList.remove('hidden');
                const titleEl = mobileSignalsEmpty.querySelector('div');
                if (titleEl) {
                    titleEl.textContent = total === 0 ? 'No Signals Loaded' : 'No Stocks Match Filter';
                }
            }
            return;
        }

        if (mobileSignalsEmpty) mobileSignalsEmpty.classList.add('hidden');

        filtered.forEach(row => {
            const ticker = row.Ticker || '';
            const tvSymbol = (row.Yahoo_Ticker || row.Ticker || '').replace('.WA', '').replace('.W', '');
            const tvUrl = `https://pl.tradingview.com/symbols/GPW-${tvSymbol}/`;
            const isBuy = (row.Strategy_Signal === 'Buy');
            const dayGain = Number(row.Day_Gain_Pct || 0);
            const rScore = Number(row.Runner_Score || 0);
            const closeP = Number(row.Close || 0);
            const shares = row.Order_Shares || Math.floor(6600 / (closeP || 1));
            const cleanSym = ticker.replace('.WA', '').replace('.W', '');
            const ticket = row.Order_Ticket || `KUPNO | ${cleanSym} | ${shares} szt. | LIMIT ${(closeP * 1.005).toFixed(2)} PLN`;
            const trRatio = Number(row.TR_Ratio || 0);
            const volS = Number(row.Volume_Surge || 0);
            const atrVal = (row.ATR_Pct ? (closeP * (row.ATR_Pct / 100)) : (closeP * 0.03)).toFixed(2);
            const stopP = row.Stop_Loss ? Number(row.Stop_Loss).toFixed(2) : '-';
            const targetP = row.Target ? Number(row.Target).toFixed(2) : '-';
            const rrRatio = row.RR_Ratio ? `${Number(row.RR_Ratio).toFixed(1)}:1` : '';
            const tierLabel = row.Tier || (isBuy ? 'BUY CANDIDATE' : 'WATCH');

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

                <div style="font-size: 0.72rem; color: var(--text-muted); margin-bottom: 0.4rem; font-weight: 600;">
                    ${tierLabel}
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
                        <span class="metric-label">Vol Surge</span>
                        <span class="metric-val ${volS >= 1.5 ? 'text-green' : ''}">${volS.toFixed(1)}x</span>
                    </div>
                    <div class="card-metric">
                        <span class="metric-label">Target (R:R)</span>
                        <span class="metric-val text-green">${targetP} ${rrRatio ? `<small>(${rrRatio})</small>` : ''}</span>
                    </div>
                </div>

                <div class="card-ticket-box">
                    <div class="ticket-headline">
                        <span>Order Ticket (Whole Shares)</span>
                        <span>Stop: ${stopP} PLN</span>
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
            btn.onclick = (e) => {
                e.stopPropagation();
                triggerHaptic(30);
                const raw = decodeURIComponent(btn.getAttribute('data-ticket') || '');
                navigator.clipboard.writeText(raw).then(() => {
                    showMobileToast('Ticket Copied! 📋', 'Pasted to clipboard. Ready for broker.', 'info', 2500);
                }).catch(() => {
                    prompt('Copy ticket manually:', raw);
                });
            };
        });

        // Wire execution bottom sheet triggers
        mobileSignalsFeed.querySelectorAll('.mobile-exec-btn').forEach(btn => {
            btn.onclick = (e) => {
                e.stopPropagation();
                triggerHaptic(20);
                const ticker = btn.getAttribute('data-ticker');
                const price = parseFloat(btn.getAttribute('data-price'));
                const shares = parseInt(btn.getAttribute('data-shares'), 10);
                const ticket = decodeURIComponent(btn.getAttribute('data-ticket') || '');
                const atr = parseFloat(btn.getAttribute('data-atr'));

                openMobileExecSheet({ ticker, price, shares, ticket, atr });
            };
        });

        if (window.lucide) {
            window.lucide.createIcons();
        }
    }

    async function fetchMobileSignals() {
        try {
            const strat = getMobileStrategy();
            const res = await fetch('/api/results/scan?strategy=' + encodeURIComponent(strat));
            const json = await res.json();
            if (json.market_regime) renderRegime(json.market_regime);
            renderMobilePodium(json.top_3, json.market_regime);
            if (json.all_stocks && Array.isArray(json.all_stocks)) {
                _mobileAllScanned = json.all_stocks;
            } else if (json.data && Array.isArray(json.data)) {
                _mobileAllScanned = json.data;
            } else {
                _mobileAllScanned = [];
            }
            renderSignalCards();
        } catch (e) {
            console.error('Failed to fetch signals:', e);
        }
    }

    if (mobileRunScanBtn) {
        mobileRunScanBtn.addEventListener('click', () => {
            runMobileLiveScanner();
        });
    }

    function runMobileLiveScanner() {
        if (_mobileActiveScanSource) {
            _mobileActiveScanSource.close();
            _mobileActiveScanSource = null;
        }

        triggerHaptic(30);
        const strat = getMobileStrategy();
        if (mobileRunScanBtn) mobileRunScanBtn.disabled = true;
        if (mobileRunBtnText) mobileRunBtnText.textContent = "Scanning WIG140...";
        if (mobileScanProgressCard) mobileScanProgressCard.classList.remove('hidden');
        if (mobileProgressBar) mobileProgressBar.style.width = '0%';
        if (mobileProgressText) mobileProgressText.textContent = "Connecting to market stream...";
        if (mobileProgressCount) mobileProgressCount.textContent = "0 / 140 (0%)";
        if (mobileSignalsEmpty) mobileSignalsEmpty.classList.add('hidden');

        _mobileAllScanned = [];
        if (mobileSignalsFeed) mobileSignalsFeed.innerHTML = '';

        let count = 0;
        const streamUrl = `/api/scan/stream?strategy=${encodeURIComponent(strat)}`;

        try {
            const es = new EventSource(streamUrl);
            _mobileActiveScanSource = es;

            es.addEventListener('connected', () => {
                if (mobileProgressText) mobileProgressText.textContent = "Connected. Scanning WIG140 universe...";
            });

            es.addEventListener('regime', (e) => {
                try {
                    const payload = JSON.parse(e.data);
                    const reg = payload.data || payload;
                    renderRegime(reg);
                    if ((reg.regime || payload.regime) === 'RED') {
                        renderMobilePodium({ is_locked: true, picks: [] }, reg);
                    }
                } catch (err) {
                    console.error("Error parsing regime event", err);
                }
            });

            es.addEventListener('stock', (e) => {
                try {
                    const payload = JSON.parse(e.data);
                    const stock = payload.stock;
                    const total = payload.total || 140;
                    count++;

                    _mobileAllScanned.push(stock);
                    const pct = Math.min(100, Math.round((count / total) * 100));
                    if (mobileProgressBar) mobileProgressBar.style.width = `${pct}%`;
                    if (mobileProgressCount) mobileProgressCount.textContent = `${count} / ${total} (${pct}%)`;
                    if (mobileProgressText) mobileProgressText.textContent = `${stock.Ticker} (${stock.Strategy_Signal === 'Buy' ? '🔥 BUY' : 'Hold'})`;

                    if (stock.Strategy_Signal === 'Buy' || _mobileAllScanned.length % 5 === 0) {
                        renderSignalCards();
                    }
                } catch (err) {
                    console.error("Error parsing stock event", err);
                }
            });

            es.addEventListener('error', (e) => {
                try {
                    const payload = JSON.parse(e.data);
                    showMobileToast('Scan Error', payload.message || 'Stream error', 'error');
                } catch (_) {}
            });

            es.addEventListener('complete', (e) => {
                try {
                    const payload = JSON.parse(e.data);
                    es.close();
                    _mobileActiveScanSource = null;

                    if (payload.all_stocks && Array.isArray(payload.all_stocks)) {
                        _mobileAllScanned = payload.all_stocks;
                    }

                    if (payload.market_regime) renderRegime(payload.market_regime);
                    renderMobilePodium(payload.top_3, payload.market_regime);
                    renderSignalCards();

                    if (mobileProgressBar) mobileProgressBar.style.width = '100%';
                    if (mobileProgressCount) mobileProgressCount.textContent = `${_mobileAllScanned.length} / ${_mobileAllScanned.length} (100%)`;
                    if (mobileProgressText) mobileProgressText.textContent = "Scan complete!";

                    showMobileToast('Scan Complete ⚡', `Evaluated ${_mobileAllScanned.length} stocks. Podium updated.`, 'success');
                    playMobileChime();
                    triggerHaptic(40);

                    setTimeout(() => {
                        if (mobileScanProgressCard) mobileScanProgressCard.classList.add('hidden');
                    }, 2500);
                } catch (err) {
                    console.error("Error on mobile complete", err);
                } finally {
                    if (mobileRunScanBtn) mobileRunScanBtn.disabled = false;
                    if (mobileRunBtnText) mobileRunBtnText.textContent = "Run Live Scanner";
                }
            });

            es.onerror = (err) => {
                console.warn("Mobile EventSource error, fallback to POST", err);
                es.close();
                _mobileActiveScanSource = null;
                if (count === 0) {
                    fallbackMobilePostScan(strat);
                } else {
                    if (mobileRunScanBtn) mobileRunScanBtn.disabled = false;
                    if (mobileRunBtnText) mobileRunBtnText.textContent = "Run Live Scanner";
                    renderSignalCards();
                }
            };
        } catch (err) {
            console.error("Failed to connect EventSource on mobile, using POST fallback", err);
            fallbackMobilePostScan(strat);
        }
    }

    async function fallbackMobilePostScan(strat) {
        if (mobileProgressText) mobileProgressText.textContent = "Streaming unavailable, running batch scan...";
        try {
            const res = await fetch('/api/scan', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ strategy: strat })
            });
            const json = await res.json();
            if (json.status === 'success') {
                if (json.all_stocks && Array.isArray(json.all_stocks)) {
                    _mobileAllScanned = json.all_stocks;
                } else if (json.data && Array.isArray(json.data)) {
                    _mobileAllScanned = json.data;
                }
                if (json.market_regime) renderRegime(json.market_regime);
                renderMobilePodium(json.top_3, json.market_regime);
                renderSignalCards();
                showMobileToast('Scan Complete ⚡', `Evaluated WIG140 (${_mobileAllScanned.length} stocks)`, 'success');
                playMobileChime();
            } else {
                showMobileToast('Scan Error', json.message || 'Error running scanner', 'error');
            }
        } catch (err) {
            showMobileToast('Scan Error', 'Connection failed: ' + err, 'error');
        } finally {
            if (mobileScanProgressCard) mobileScanProgressCard.classList.add('hidden');
            if (mobileRunScanBtn) mobileRunScanBtn.disabled = false;
            if (mobileRunBtnText) mobileRunBtnText.textContent = "Run Live Scanner";
        }
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

            // Update Mobile Contest Status
            const mobileDot = document.getElementById('mobileContestDot');
            const mobileStatusText = document.getElementById('mobileContestStatusText');
            const mobileRankPill = document.getElementById('mobileContestRankPill');
            const cs = summary.contest_sync || {};

            if (mobileDot && mobileStatusText) {
                if (cs.status === 'synced') {
                    mobileDot.style.background = '#34d399';
                    mobileDot.style.boxShadow = '0 0 6px rgba(52, 211, 153, 0.8)';
                    const timePart = cs.last_synced ? cs.last_synced.split(' ')[1] : '';
                    mobileStatusText.textContent = `Contest: Synced ${timePart}`;
                    mobileStatusText.style.color = '#34d399';
                } else if (cs.status === 'expired') {
                    mobileDot.style.background = '#fb7185';
                    mobileDot.style.boxShadow = 'none';
                    mobileStatusText.textContent = 'Contest: Expired';
                    mobileStatusText.style.color = '#fb7185';
                } else if (cs.status === 'error') {
                    mobileDot.style.background = '#fbbf24';
                    mobileDot.style.boxShadow = 'none';
                    mobileStatusText.textContent = 'Contest: Error';
                    mobileStatusText.style.color = '#fbbf24';
                } else {
                    mobileDot.style.background = '#94a3b8';
                    mobileDot.style.boxShadow = 'none';
                    mobileStatusText.textContent = 'Contest: Offline';
                    mobileStatusText.style.color = '#94a3b8';
                }
            }

            if (mobileRankPill) {
                if (cs.rank) {
                    mobileRankPill.classList.remove('hidden');
                    mobileRankPill.textContent = `#${cs.rank}${cs.total_teams ? ' / ' + cs.total_teams : ''}`;
                } else {
                    mobileRankPill.classList.add('hidden');
                }
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

    const mobileSyncContestBtn = document.getElementById('mobileSyncContestBtn');
    if (mobileSyncContestBtn) {
        mobileSyncContestBtn.addEventListener('click', async () => {
            triggerHaptic(25);
            const syncTxt = document.getElementById('mobileSyncContestText');
            mobileSyncContestBtn.disabled = true;
            if (syncTxt) syncTxt.textContent = '...';
            try {
                const res = await fetch('/api/contest/sync', { method: 'POST' });
                const json = await res.json();
                if (json.status === 'success') {
                    showMobileToast('Contest Synced', json.message || 'Holding positions and equity synchronized.', 'success');
                    playMobileChime();
                    fetchMobilePortfolio();
                } else {
                    showMobileToast('Sync Failed', json.message || 'Could not connect to contest. Verify cURL in Desktop settings.', 'error');
                    fetchMobilePortfolio();
                }
            } catch (err) {
                showMobileToast('Sync Error', 'Network error connecting to local hub API: ' + err, 'error');
            } finally {
                mobileSyncContestBtn.disabled = false;
                if (syncTxt) syncTxt.textContent = 'Sync';
            }
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
