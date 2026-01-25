// pages/index.js
import { useState } from "react";
import DCAResult from "../components/DCAResult";

const MONTHS = [
  { value: "janvier", label: "Janvier" },
  { value: "février", label: "Février" },
  { value: "mars", label: "Mars" },
  { value: "avril", label: "Avril" },
  { value: "mai", label: "Mai" },
  { value: "juin", label: "Juin" },
  { value: "juillet", label: "Juillet" },
  { value: "août", label: "Août" },
  { value: "septembre", label: "Septembre" },
  { value: "octobre", label: "Octobre" },
  { value: "novembre", label: "Novembre" },
  { value: "décembre", label: "Décembre" },
];

export default function Home() {
  const [tickers, setTickers] = useState("UST.PA, AAPL");
  const [month, setMonth] = useState("novembre");
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  const handleAnalyze = async (e) => {
    e.preventDefault();
    setLoading(true);
    setError("");
    setData(null);
    try {
      const resp = await fetch("/api/analyze", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ tickers, month }),
      });
      const json = await resp.json();
      if (!resp.ok) {
        setError(json?.error || "Erreur API");
      } else {
        setData(json);
      }
    } catch (err) {
      setError("Impossible d'appeler l'API.");
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="page-shell">
      <div className="hero">
        <h1>Analyse DCA mensuelle</h1>
        <p>10 ans · plusieurs tickers · meilleurs jours du mois</p>
      </div>

      <div className="panel">
        <form onSubmit={handleAnalyze} className="form-grid">
          <div className="field">
            <label htmlFor="tickers">Tickers</label>
            <input
              id="tickers"
              type="text"
              value={tickers}
              onChange={(e) => setTickers(e.target.value)}
              placeholder="UST.PA, AAPL, QQQ..."
              autoComplete="off"
            />
            <span className="field-hint">Séparer par des virgules</span>
          </div>

          <div className="field">
            <label htmlFor="month">Mois</label>
            <select
              id="month"
              value={month}
              onChange={(e) => setMonth(e.target.value)}
            >
              {MONTHS.map((m) => (
                <option key={m.value} value={m.value}>
                  {m.label}
                </option>
              ))}
            </select>
          </div>

          <div className="actions">
            <button type="submit" disabled={loading}>
              {loading ? "Analyse..." : "Analyser"}
            </button>
          </div>
        </form>

        {error ? <p className="error">{error}</p> : null}

        {loading ? <div className="loading">⏳ Récupération des données…</div> : null}

        {data ? <DCAResult data={data} /> : null}

        {!data && !loading && !error ? (
          <p className="helper">
            Saisis tes tickers, choisis un mois et lance une analyse.
            <br />
            🔎 Tu peux trouver des tickers ici :{" "}
            <a
              href="https://fr.finance.yahoo.com/research-hub/screener/etf"
              target="_blank"
              rel="noreferrer"
            >
              Yahoo Finance – Screener ETF
            </a>
          </p>
        ) : null}
      </div>
    </div>
  );
}

