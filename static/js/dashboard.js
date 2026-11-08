let selectedDriver = null;
let loaded = false;

const $ = id => document.getElementById(id);

async function api(url, options) {
    const response = await fetch(url, options);
    const data = await response.json();
    if (!response.ok || data.success === false) throw new Error(data.error || "Request failed");
    return data;
}

function seconds(v) {
    return v == null ? "—" : Number(v).toFixed(3) + "s";
}

function renderMetric(status) {
    $("mPosition").textContent = status.position ?? "—";
    $("mTeam").textContent = status.team;
    $("mLap").textContent = status.lap;
    $("mDistance").textContent = `of ${status.total_laps} race laps`;
    $("mLapTime").textContent = seconds(status.lap_time);
    $("mBest").textContent = seconds(status.best_lap);
    $("mCompound").textContent = status.compound;
    $("mTyreAge").textContent = `Tyre age ${status.tyre_age}`;
    $("mPits").textContent = status.pit_stops;
}

function renderDrivers(rows) {
    $("driverTable").innerHTML = rows.map(r => `
        <tr onclick="selectDriver('${r.driver}')">
            <td>${r.position}</td>
            <td>${r.driver}</td>
            <td>${r.team}</td>
            <td>${r.lap}</td>
            <td>${seconds(r.lap_time)}</td>
            <td>${seconds(r.best_lap)}</td>
            <td>${r.stint ?? "—"}</td>
            <td>${r.compound}</td>
            <td>${r.tyre_age}</td>
            <td>${r.pit_stops}</td>
        </tr>
    `).join("");
}

function fillDrivers(drivers) {
    $("driverSelect").innerHTML = drivers.map(d => `<option value="${d}">${d}</option>`).join("");
    selectedDriver = drivers[0];
}

async function loadRace() {
    const [year, event] = $("raceSelect").value.split("|");
    $("systemStatus").textContent = "LOADING RACE DATA";
    $("loadMessage").textContent = "FastF1 session loading...";
    $("loadButton").disabled = true;
    try {
        const data = await api("/api/load-race", {
            method: "POST",
            headers: {"Content-Type": "application/json"},
            body: JSON.stringify({year, event})
        });
        fillDrivers(data.drivers);
        $("loadMessage").textContent = `${data.summary.laps_recorded} laps loaded`;
        $("systemStatus").textContent = "RACE DATA ONLINE";
        loaded = true;
        await refreshDashboard();
    } catch (e) {
        $("loadMessage").textContent = e.message;
        $("systemStatus").textContent = "DATA ERROR";
    } finally {
        $("loadButton").disabled = false;
    }
}

async function refreshDashboard() {
    if (!loaded) return;
    const overview = await api("/api/overview");
    $("eventTitle").textContent = `${overview.event.toUpperCase()} GRAND PRIX`;
    $("circuitName").textContent = overview.circuit.toUpperCase();
    $("raceProgress").textContent = `${overview.current_lap} / ${overview.total_laps} LAPS`;
    $("trackStatus").textContent = `TRACK STATUS ${overview.track_status}`;
    $("raceProgressBar").style.width = overview.progress + "%";

    const rows = await api("/api/drivers");
    renderDrivers(rows.drivers);

    selectedDriver = $("driverSelect").value;
    await refreshDriver();
}

async function refreshDriver() {
    if (!selectedDriver) return;
    const status = await api(`/api/race-status?driver=${encodeURIComponent(selectedDriver)}`);
    renderMetric(status);
    const history = await api(`/api/lap-history?driver=${encodeURIComponent(selectedDriver)}`);
    drawCharts(history);
    const strategy = await api(`/api/strategy?driver=${encodeURIComponent(selectedDriver)}`);
    renderStrategy(strategy);
}

function drawCharts(data) {
    const base = {
        paper_bgcolor: "transparent",
        plot_bgcolor: "transparent",
        font: {color:"#8f949d", size:10},
        margin: {l:45,r:15,t:15,b:35},
        xaxis: {gridcolor:"#22252d", zerolinecolor:"#22252d"},
        yaxis: {gridcolor:"#22252d", zerolinecolor:"#22252d"}
    };

    Plotly.newPlot("lapChart", [{
        x:data.laps, y:data.lap_times, mode:"lines", line:{width:2}, name:"Lap time"
    }], {...base, yaxis:{...base.yaxis,title:"Seconds"}, xaxis:{...base.xaxis,title:"Lap"}}, {displayModeBar:false,responsive:true});

    Plotly.newPlot("positionChart", [{
        x:data.laps, y:data.positions, mode:"lines+markers", line:{width:2}, marker:{size:4}
    }], {...base, yaxis:{...base.yaxis,title:"Position",autorange:"reversed"}, xaxis:{...base.xaxis,title:"Lap"}}, {displayModeBar:false,responsive:true});

    $("paceLabel").textContent = data.driver;
}

function renderStrategy(s) {
    $("recommendation").textContent = s.recommendation;
    $("confidence").textContent = s.confidence + "%";
    $("pitWindow").textContent = `${s.pit_window[0]}–${s.pit_window[1]}`;
    $("tyreRisk").textContent = s.tyre_risk;
    $("degradation").textContent = `${s.tyre_degradation_per_lap.toFixed(3)} s/lap`;
    $("remainingLaps").textContent = s.remaining_laps;
    $("tyreAgeBig").textContent = $("mTyreAge").textContent.replace("Tyre age ","");
    $("tyreCompoundBig").textContent = s.current_compound;
    $("stintAverage").textContent = seconds(s.current_stint_average);
    $("compoundBaseline").textContent = seconds(s.compound_baseline);

    $("simulationRows").innerHTML = s.alternatives.map((x,i) => `
        <div class="sim-row ${i === 0 ? "best" : ""}">
            <div><strong>${x.name}</strong><br><span>${x.compounds.join(" → ")}</span></div>
            <div><span>PIT LAPS</span><br><strong>${x.pit_laps.length ? x.pit_laps.join(", ") : "NONE"}</strong></div>
            <div><span>REMAINING TIME</span><br><strong class="sim-time">${x.predicted_remaining_time.toFixed(1)}s</strong></div>
            <div><span>RANK</span><br><strong>${i === 0 ? "RECOMMENDED" : "ALTERNATIVE"}</strong></div>
        </div>
    `).join("");

    Plotly.newPlot("strategyChart", [{
        x:s.alternatives.map(x => x.name),
        y:s.alternatives.map(x => x.predicted_remaining_time),
        type:"bar"
    }], {
        paper_bgcolor:"transparent",
        plot_bgcolor:"transparent",
        font:{color:"#8f949d",size:10},
        margin:{l:55,r:15,t:20,b:75},
        xaxis:{gridcolor:"#22252d",tickangle:-18},
        yaxis:{gridcolor:"#22252d",title:"Predicted remaining seconds"}
    }, {displayModeBar:false,responsive:true});
}

async function selectDriver(driver) {
    selectedDriver = driver;
    $("driverSelect").value = driver;
    await refreshDriver();
}

$("loadButton").addEventListener("click", loadRace);
$("driverSelect").addEventListener("change", async e => {
    selectedDriver = e.target.value;
    await refreshDriver();
});
window.addEventListener("load", loadRace);
