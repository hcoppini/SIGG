document.addEventListener('DOMContentLoaded', () => {
    // Initialize Lucide Icons if available
    if (window.lucide) {
        window.lucide.createIcons();
    }

    // Navigation
    const links = document.querySelectorAll('nav a');
    const panels = document.querySelectorAll('.panel');
    const strategySelect = document.getElementById('strategySelect');

    links.forEach(link => {
        link.addEventListener('click', (e) => {
            e.preventDefault();
            links.forEach(l => l.classList.remove('active'));
            panels.forEach(p => p.classList.remove('active'));
            
            link.classList.add('active');
            const targetId = link.getAttribute('data-target');
            const targetPanel = document.getElementById(targetId);
            if (targetPanel) {
                targetPanel.classList.add('active');
            }

            // Re-render / resize charts when tab opens
            if (targetId === 'backtest') {
                if (equityChartInstance) equityChartInstance.resize();
                if (seasonBarChartInstance) seasonBarChartInstance.resize();
                if (winLossChartInstance) winLossChartInstance.resize();
            }
        });
    });

    function getActiveStrategy() {
        return strategySelect ? strategySelect.value : 'breakout';
    }

    if (strategySelect) {
        strategySelect.addEventListener('change', () => {
            fetchScanResults();
            fetchBacktestResults();
            fetchOptResults();
        });
    }

    // ==========================================
    // 1. SCANNER LOGIC
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

    function populateScanTable(data, type, strategy) {
        if (!scanTableBody) return;
        
        if (!data || data.length === 0) {
            if (scanEmpty) {
                scanEmpty.classList.remove('hidden');
                scanEmpty.textContent = "No scan data available.";
            }
            scanTableBody.innerHTML = '';
            if (scanCountBadge) scanCountBadge.textContent = "0 signals";
            return;
        }
        
        if (type === 'closest') {
            if (scanEmpty) {
                scanEmpty.classList.remove('hidden');
                scanEmpty.textContent = "No pure buy signals today. Displaying top 5 closest candidates.";
            }
            if (scanCountBadge) scanCountBadge.textContent = `${data.length} closest`;
        } else {
            if (scanEmpty) scanEmpty.classList.add('hidden');
            if (scanCountBadge) scanCountBadge.textContent = `${data.length} qualified`;
        }

        if (strategy === 'breakout') {
            if (scanTableHeader) {
                scanTableHeader.innerHTML = `
                    <tr>
                        <th>Ticker</th>
                        <th>Close (PLN)</th>
                        <th>Trend (SMA50)</th>
                        <th>Vol Surge</th>
                        <th>Stop Loss</th>
                        <th>Target</th>
                        <th>R:R</th>
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
                        <th>Target</th>
                        <th>R:R</th>
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

            if (strategy === 'breakout') {
                tr.innerHTML = `
                    <td><strong>${ticker}</strong></td>
                    <td class="font-mono">${Number(row.Close || 0).toFixed(2)}</td>
                    <td>
                        <span class="badge ${isUptrend ? 'badge-buy' : 'badge-loss'}">${row.Trend_SMA50 || 'Uptrend'}</span>
                    </td>
                    <td class="font-mono ${Number(row.Volume_Surge || 0) >= 1.25 ? 'text-green font-bold' : ''}">${Number(row.Volume_Surge || 0).toFixed(2)}x</td>
                    <td class="font-mono text-red">${row.Stop_Loss ? Number(row.Stop_Loss).toFixed(2) : '-'}</td>
                    <td class="font-mono text-green">${row.Target ? Number(row.Target).toFixed(2) : '-'}</td>
                    <td class="font-mono font-bold ${Number(row.RR_Ratio || 0) >= 2.0 ? 'text-green' : ''}">${row.RR_Ratio ? Number(row.RR_Ratio).toFixed(1) + ':1' : '-'}</td>
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
                    <td class="font-mono ${Number(row.RSI || 0) >= 45 && Number(row.RSI || 0) <= 75 ? 'text-green font-bold' : ''}">${Number(row.RSI || 0).toFixed(1)}</td>
                    <td class="font-mono ${Number(row.Volume_Surge || 0) >= 1.15 ? 'text-green font-bold' : ''}">${Number(row.Volume_Surge || 0).toFixed(2)}x</td>
                    <td class="font-mono text-red">${row.Stop_Loss ? Number(row.Stop_Loss).toFixed(2) : '-'}</td>
                    <td class="font-mono text-green">${row.Target ? Number(row.Target).toFixed(2) : '-'}</td>
                    <td class="font-mono font-bold ${Number(row.RR_Ratio || 0) >= 1.8 ? 'text-green' : ''}">${row.RR_Ratio ? Number(row.RR_Ratio).toFixed(1) + ':1' : '-'}</td>
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
        fetch('/api/results/scan').then(r => r.json()).then(j => {
            if(j.status === 'success') {
                populateScanTable(j.data, j.type, strategy);
            } else {
                if (scanEmpty) scanEmpty.classList.remove('hidden');
                if (scanTableBody) scanTableBody.innerHTML = '';
            }
        }).catch(() => {});
    }

    // ==========================================
    // 2. 5-YEAR BACKTEST & CHART.JS VISUAL GRAPHS
    // ==========================================
    let equityChartInstance = null;
    let seasonBarChartInstance = null;
    let winLossChartInstance = null;

    const runBacktestBtn = document.getElementById('runBacktestBtn');
    const backtestLoading = document.getElementById('backtestLoading');
    const seasonSummaryBody = document.getElementById('seasonSummaryBody');
    const tradesLogBody = document.getElementById('tradesLogBody');

    if (runBacktestBtn) {
        runBacktestBtn.addEventListener('click', async () => {
            runBacktestBtn.disabled = true;
            if (backtestLoading) backtestLoading.classList.remove('hidden');

            try {
                const res = await fetch('/api/backtest', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ strategy: getActiveStrategy() })
                });
                const json = await res.json();
                if (json.status === 'success') {
                    renderBacktestData(json);
                } else {
                    alert('Error running backtest: ' + json.message);
                }
            } catch (e) {
                alert('Backtest request failed: ' + e);
            }

            if (backtestLoading) backtestLoading.classList.add('hidden');
            runBacktestBtn.disabled = false;
        });
    }

    function fetchBacktestResults() {
        const strategy = getActiveStrategy();
        fetch('/api/results/backtest?strategy=' + strategy)
            .then(r => r.json())
            .then(json => {
                if (json.status === 'success') {
                    renderBacktestData(json);
                }
            })
            .catch(() => {});
    }

    function renderBacktestData(data) {
        if (!data) return;

        // 1. Update KPI Cards
        const summary = data.summary || {};
        const kpiAvgReturn = document.getElementById('kpiAvgReturn');
        const kpiWinRate = document.getElementById('kpiWinRate');
        const kpiBestSeason = document.getElementById('kpiBestSeason');
        const kpiBestReturn = document.getElementById('kpiBestReturn');

        if (kpiAvgReturn) {
            const ret = summary.avg_return_pct || 0;
            kpiAvgReturn.textContent = `${ret > 0 ? '+' : ''}${ret.toFixed(2)}%`;
            kpiAvgReturn.className = `kpi-value ${ret >= 0 ? 'text-green' : 'text-red'}`;
        }
        if (kpiWinRate) {
            kpiWinRate.textContent = `Win Rate: ${summary.overall_win_rate || 0}% (${summary.total_trades || 0} trades)`;
        }
        if (summary.best_season && kpiBestSeason && kpiBestReturn) {
            kpiBestSeason.textContent = summary.best_season.season;
            kpiBestReturn.textContent = `Return: +${summary.best_season.return_pct}% (${summary.best_season.final_capital.toLocaleString('pl-PL')} PLN)`;
        }

        // 2. Render Equity Curve Chart
        renderEquityCurveChart(data.equity_curves || {});

        // 3. Render Season Bar Chart & Win/Loss Doughnut
        renderSeasonBarChart(data.seasons || []);
        renderWinLossChart(data.trades || [], summary.overall_win_rate || 50);

        // 4. Populate Season Breakdown Table
        populateSeasonSummaryTable(data.seasons || []);

        // 5. Populate Completed Trades Log Table
        populateTradesLogTable(data.trades || []);
    }

    function renderEquityCurveChart(curves) {
        const ctx = document.getElementById('equityCurveChart');
        if (!ctx) return;

        // Find the maximum length of points across seasons
        let maxDays = 0;
        Object.values(curves).forEach(pts => {
            if (pts.length > maxDays) maxDays = pts.length;
        });

        if (maxDays === 0) maxDays = 40;
        const labels = Array.from({ length: maxDays }, (_, i) => `Day ${i + 1}`);

        // Define distinct professional palette for each season
        const colors = {
            "2020/2021": "#10b981", // Emerald Green
            "2021/2022": "#a855f7", // Purple
            "2022/2023": "#3b82f6", // Blue
            "2023/2024": "#06b6d4", // Cyan
            "2024/2025": "#f59e0b", // Amber
            "2025/2026": "#22c55e"  // Vibrant Green (Latest Contest Edition)
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

        // Add 20,000 PLN baseline reference
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
                            label: (ctx) => `${ctx.parsed.y > 0 ? '+' : ''}${ctx.parsed.y}% Return`
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

    function renderWinLossChart(trades, winRate) {
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

        if (trades.length === 0) {
            tradesLogBody.innerHTML = '<tr><td colspan="10" class="text-center py-4 text-muted">No completed trades recorded.</td></tr>';
            return;
        }

        // Show newest first
        const reversed = [...trades].reverse();
        reversed.slice(0, 20).forEach(t => {
            const tr = document.createElement('tr');
            const isWin = (t.PnL > 0);
            tr.innerHTML = `
                <td><span class="badge badge-season">${t.Season || '-'}</span></td>
                <td><strong>${t.Ticker}</strong></td>
                <td class="font-mono text-xs">${t.Entry_Date}</td>
                <td class="font-mono text-xs">${t.Exit_Date}</td>
                <td class="font-mono">${Number(t.Entry_Price).toFixed(2)}</td>
                <td class="font-mono">${Number(t.Exit_Price).toFixed(2)}</td>
                <td class="font-mono font-bold ${isWin ? 'text-green' : 'text-red'}">${isWin ? '+' : ''}${Number(t.PnL).toFixed(2)} PLN</td>
                <td class="font-mono font-bold ${isWin ? 'text-green' : 'text-red'}">${isWin ? '+' : ''}${Number(t.PnL_Pct).toFixed(2)}%</td>
                <td class="font-mono">${t.Days_Held}d</td>
                <td class="font-mono text-xs text-muted">${t.Exit_Reason || 'Strategy_Exit'}</td>
            `;
            tradesLogBody.appendChild(tr);
        });
    }

    // ==========================================
    // 3. OPTIMIZER LOGIC
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
        
        if (strategy === 'breakout') {
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
            if (strategy === 'breakout') {
                tr.innerHTML = `
                    <td><strong>#${i + 1}</strong></td>
                    <td class="font-mono">${row.Breakout}</td>
                    <td class="font-mono">${(row.ATR_Min*100).toFixed(1)}%</td>
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
            if(j.status === 'success') {
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
});
