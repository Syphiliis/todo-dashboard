// components/DCAResult.jsx

export default function DCAResult({ data }) {
  if (!data || !data.results) return null;

  return (
    <div className="results-container">
      {data.results.map((item) => {
        const lastYears = (item.perYear || []).slice(0, 3);
        const hiddenCount = Math.max(
          0,
          (item.perYear || []).length - lastYears.length
        );

        return (
          <div key={item.ticker} className="result-card">
            <div className="result-header">
              <h2>
                Analyse DCA – {data.month} · <span>{item.ticker}</span>
              </h2>
              {item.bestDays && item.bestDays.length ? (
                <p className="best-days">
                  ✅ Meilleur moment :{" "}
                  {item.bestDays.map((d, i) => (
                    <strong key={d}>
                      {i > 0 ? ", " : ""}
                      {d}
                    </strong>
                  ))}{" "}
                  du mois
                </p>
              ) : (
                <p className="best-days muted">⚠️ Pas assez de données</p>
              )}
            </div>

            {item.freqDays?.sorted?.length ? (
              <p className="freq-line">
                📉 Jours souvent bas :{" "}
                {item.freqDays.sorted.slice(0, 4).map((f) => (
                  <span
                    key={f.day}
                    className={f.isBest ? "freq-day best" : "freq-day"}
                  >
                    {f.day} ({f.count}×)
                  </span>
                ))}
              </p>
            ) : null}

            <div className="years-block">
              {lastYears.map((y) => (
                <div key={y.year} className="year-line">
                  <span className="year-label">{y.year}</span>
                  <span className="year-lows">
                    {y.lows.map((l, idx) => (
                      <span key={idx} className="low-pill">
                        {l.date} → {l.price.toFixed(2)}
                      </span>
                    ))}
                  </span>
                </div>
              ))}
              {hiddenCount > 0 && (
                <p className="hidden-years">+ {hiddenCount} années cachées</p>
              )}
            </div>

            <div className="actions">
              <button
                type="button"
                onClick={() => downloadCSVForTicker(item, data.month)}
                className="export-btn"
              >
                💾 Export CSV
              </button>
            </div>
          </div>
        );
      })}

      <p className="helper">
        💡 Tu peux trouver des tickers (ETF, actions…) ici :{" "}
        <a
          href="https://fr.finance.yahoo.com/research-hub/screener/etf"
          target="_blank"
          rel="noreferrer"
          className="linklike"
        >
          Yahoo Finance – Screener ETF
        </a>
      </p>
    </div>
  );
}

// petit helper côté front
function downloadCSVForTicker(item, monthLabel) {
  const rows = [];
  rows.push(["ticker", "month", "year", "date", "price"].join(","));

  (item.perYear || []).forEach((y) => {
    (y.lows || []).forEach((l) => {
      rows.push(
        [
          item.ticker,
          monthLabel,
          y.year,
          l.date,
          typeof l.price === "number" ? l.price.toFixed(4) : l.price,
        ].join(",")
      );
    });
  });

  const blob = new Blob([rows.join("\n")], { type: "text/csv" });
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = `dca-${item.ticker}-${monthLabel}.csv`;
  a.click();
  URL.revokeObjectURL(url);
}

