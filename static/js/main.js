document.addEventListener('DOMContentLoaded', () => {
    if (window.lucide) {
        window.lucide.createIcons();
    }

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
    }

    links.forEach(link => {
        link.addEventListener('click', (e) => {
            e.preventDefault();
            const targetId = link.getAttribute('data-target');
            switchTab(targetId);
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
        return strategySelect ? strategySelect.value : 'squeeze_ignition';
    }

    if (strategySelect) {
        strategySelect.addEventListener('change', () => {
            fetchScanResults();
            fetchBacktestResults();
            fetchOptResults();
        });
    }

    // ==========================================
    // 1. SCANNER + MARKET REGIME + BT SUMMARY BAR
    // ==========================================
    const runScanBtn = document.getElementById('runScanBtn');
    const scanLoading = document.getElementById('scanLoading');
    const scanTableBody = document.querySelector('#scanTable tbody');
    const scanEmpty = document.getElementById('scanEmpty');
    const scanTableHeader = document.getElementById('scanTableHeader');
    const scanCountBadge = document.getElementById('scanCountBadge');

    if (runScanBtn) {
        runScanBtn.addEventListener('click', async () => {
            runScanBtn.disabled = true;
            if (scanLoading) scanLoading.classList.remove('hidden');
            if (scanEmpty) scanEmpty.classList.add('hidden');
            if (scanTableBody) scanTableBody.innerHTML = '';

            try {
                const res = await fetch('/api/scan', { 
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ strategy: getActiveStrategy() })
                });
                const json = await res.json();
                
                if (json.status === 'success') {
                    if (json.market_regime) renderMarketRegime(json.market_regime);
                    if (json.backtest_summary) renderScannerBacktestSummary(json.backtest_summary);
                    populateScanTable(json.data, json.type, getActiveStrategy());
                } else {
                    alert('Error running scanner: ' + json.message);
                }
            } catch (e) {
                alert('Scanner request failed: ' + e);
            }

            if (scanLoading) scanLoading.classList.add('hidden');
            runScanBtn.disabled = false;
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
            if (scanEmpty) {
                scanEmpty.classList.remove('hidden');
                scanEmpty.textContent = "No strict Ignition Buy signals today. Displaying top 10 closest candidates ranked by Runner Score.";
            }
            if (scanCountBadge) scanCountBadge.textContent = `${data.length} watchlist`;
        } else {
            if (scanEmpty) scanEmpty.classList.add('hidden');
            if (scanCountBadge) scanCountBadge.textContent = `${data.length} qualified buys`;
        }

        if (strategy === 'squeeze_ignition') {
            if (scanTableHeader) {
                scanTableHeader.innerHTML = `
                    <tr>
                        <th>Ticker</th>
                        <th>Close (PLN)</th>
                        <th>Runner Score</th>
                        <th>Day Δ%</th>
                        <th>Pre-ATR %</th>
                        <th>TR / ATR</th>
                        <th>Close Pos</th>
                        <th>Vol Surge</th>
                        <th>Stop / Hold</th>
                        <th>5-Yr Backtest History</th>
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
            const tickerClean = ticker.replace('.WA', '').replace('.W', '');
            const tvUrl = `https://pl.tradingview.com/symbols/GPW-${tickerClean}/`;
            const isBuy = (row.Strategy_Signal === 'Buy');
            const isUptrend = (row.Trend_SMA50 === 'Uptrend');
            const btStats = row.BT_Stats || 'No past triggers';

            if (strategy === 'squeeze_ignition') {
                const dayGain = Number(row.Day_Gain_Pct || 0);
                const trRatio = Number(row.TR_Ratio || 0);
                const cPos = Number(row.Close_Pos || 0);
                const volS = Number(row.Volume_Surge || 0);
                const rScore = Number(row.Runner_Score || 0);
                tr.innerHTML = `
                    <td><strong>${ticker}</strong></td>
                    <td class="font-mono">${Number(row.Close || 0).toFixed(2)}</td>
                    <td class="font-mono font-bold text-green">${rScore.toFixed(2)}</td>
                    <td class="font-mono ${dayGain >= 2.5 ? 'text-green font-bold' : (dayGain < 0 ? 'text-red' : '')}">${dayGain >= 0 ? '+' : ''}${dayGain.toFixed(2)}%</td>
                    <td class="font-mono">${Number(row.ATR_Pct || 0).toFixed(2)}%</td>
                    <td class="font-mono ${trRatio >= 1.3 ? 'text-green font-bold' : ''}">${trRatio.toFixed(2)}x</td>
                    <td class="font-mono ${cPos >= 0.70 ? 'text-green font-bold' : ''}">${(cPos * 100).toFixed(0)}%</td>
                    <td class="font-mono ${volS >= 1.5 ? 'text-green font-bold' : ''}">${volS.toFixed(2)}x</td>
                    <td class="font-mono text-red">${row.Stop_Loss ? Number(row.Stop_Loss).toFixed(2) : '-'} <span class="text-muted">/ 3D</span></td>
                    <td class="font-mono text-xs">${btStats}</td>
                    <td>
                        <span class="badge ${isBuy ? 'badge-buy' : 'badge-hold'}">${row.Strategy_Signal || 'Hold'}</span>
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
                        <span class="badge ${isBuy ? 'badge-buy' : 'badge-hold'}">${row.Strategy_Signal || 'Hold'}</span>
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
                        <span class="badge ${isBuy ? 'badge-buy' : 'badge-hold'}">${row.Strategy_Signal || 'Hold'}</span>
                    </td>
                    <td>
                        <a href="${tvUrl}" target="_blank" class="tv-link">TV &nearr;</a>
                    </td>
                `;
            }
            scanTableBody.appendChild(tr);
        });
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
                } else if (pollJson.status === 'error' || attempts > 60) {
                    clearInterval(pollTimer);
                    if (backtestLoading) backtestLoading.classList.add('hidden');
                    if (runBacktestBtn) runBacktestBtn.disabled = false;
                    if (pollJson.message) alert('Backtest error: ' + pollJson.message);
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
                } else if (json.status === 'running') {
                    pollBacktestUntilDone(activeStrat);
                } else {
                    alert('Error running backtest: ' + (json.message || 'Unknown error'));
                    if (backtestLoading) backtestLoading.classList.add('hidden');
                    runBacktestBtn.disabled = false;
                }
            } catch (e) {
                // If network connection dropped during Render cold boot, poll for result
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

    function populateSeasonSummaryTable(seasons) {
        if (!seasonSummaryBody) return;
        seasonSummaryBody.innerHTML = '';

        if (seasons.length === 0) {
            seasonSummaryBody.innerHTML = '<tr><td colspan="12" class="text-center py-4 text-muted">No season results available.</td></tr>';
            return;
        }

        seasons.forEach(s => {
            const tr = document.createElement('tr');
            const isPositive = (s.return_pct >= 0);
            
            const winTxt = s.biggest_winner ? 
                `<span class="badge badge-buy font-bold">${s.biggest_winner.ticker} (+${s.biggest_winner.pnl_pct}%)</span>` : 
                '<span class="text-muted text-xs">-</span>';
                
            const lossTxt = s.biggest_loser ? 
                `<span class="badge badge-loss font-bold">${s.biggest_loser.ticker} (${s.biggest_loser.pnl_pct}%)</span>` : 
                '<span class="text-muted text-xs">-</span>';

            tr.innerHTML = `
                <td><strong>${s.season}</strong></td>
                <td class="font-mono text-muted text-xs">${s.start_date} &rarr; ${s.end_date}</td>
                <td class="font-mono">${Number(s.initial_capital).toLocaleString('pl-PL')} PLN</td>
                <td class="font-mono font-bold ${isPositive ? 'text-green' : 'text-red'}">${Number(s.final_capital).toLocaleString('pl-PL')} PLN</td>
                <td class="font-mono ${isPositive ? 'text-green' : 'text-red'}">${isPositive ? '+' : ''}${Number(s.net_profit).toLocaleString('pl-PL')} PLN</td>
                <td class="font-mono font-bold ${isPositive ? 'text-green' : 'text-red'}">${isPositive ? '+' : ''}${s.return_pct}%</td>
                <td class="font-mono">${s.win_rate}%</td>
                <td class="font-mono">${s.profit_factor}</td>
                <td class="font-mono text-red">-${s.max_drawdown}%</td>
                <td>${winTxt}</td>
                <td>${lossTxt}</td>
                <td class="font-mono">${s.trades_count}</td>
            `;
            seasonSummaryBody.appendChild(tr);
        });
    }

    function populateTradesLogTable(trades) {
        if (!tradesLogBody) return;
        tradesLogBody.innerHTML = '';

        const countBadge = document.getElementById('tradesLogCountBadge');
        if (countBadge) countBadge.textContent = `${trades.length} executed trades`;

        if (trades.length === 0) {
            tradesLogBody.innerHTML = '<tr><td colspan="12" class="text-center py-4 text-muted">No completed trades recorded for these parameters.</td></tr>';
            return;
        }

        const reversed = [...trades].reverse();
        reversed.forEach(t => {
            const tr = document.createElement('tr');
            const isWin = (t.PnL > 0);
            tr.innerHTML = `
                <td><span class="badge badge-season">${t.Season || '-'}</span></td>
                <td><strong>${t.Ticker}</strong></td>
                <td class="font-mono text-xs">${t.Entry_Date}</td>
                <td class="font-mono text-xs">${t.Exit_Date}</td>
                <td class="font-mono">${t.Shares || '-'}</td>
                <td class="font-mono">${Number(t.Entry_Price).toFixed(2)}</td>
                <td class="font-mono">${Number(t.Exit_Price).toFixed(2)}</td>
                <td class="font-mono text-muted">${t.Fees_PLN !== undefined ? Number(t.Fees_PLN).toFixed(2) : '-'}</td>
                <td class="font-mono font-bold ${isWin ? 'text-green' : 'text-red'}">${isWin ? '+' : ''}${Number(t.PnL).toFixed(2)} PLN</td>
                <td class="font-mono font-bold ${isWin ? 'text-green' : 'text-red'}">${isWin ? '+' : ''}${Number(t.PnL_Pct).toFixed(2)}%</td>
                <td class="font-mono">${t.Days_Held}d</td>
                <td class="font-mono text-xs text-muted">${t.Exit_Reason || 'Strategy_Exit'}</td>
            `;
            tradesLogBody.appendChild(tr);
        });
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
                } else {
                    alert('Error running optimizer: ' + json.message);
                }
            } catch (e) {
                alert('Optimizer request failed: ' + e);
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
    // INITIAL LOAD
    // ==========================================
    fetchScanResults();
    fetchBacktestResults();
    fetchOptResults();
    loadStrategyMarkdown();
});
