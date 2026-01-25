// pages/api/analyze.js
const yahooFinance = require("yahoo-finance");

const MONTHS = [
  "janvier",
  "février",
  "mars",
  "avril",
  "mai",
  "juin",
  "juillet",
  "août",
  "septembre",
  "octobre",
  "novembre",
  "décembre",
];

const CACHE_TTL_MS = Number(process.env.DCA_CACHE_TTL_SECONDS || 3600) * 1000;
const HISTORY_YEARS = Number(process.env.DCA_HISTORY_YEARS || 10);
const MAX_TICKERS = Number(process.env.DCA_MAX_TICKERS || 12);

const cache = new Map();

function getCache(key) {
  const entry = cache.get(key);
  if (!entry) return null;
  if (Date.now() > entry.expiresAt) {
    cache.delete(key);
    return null;
  }
  return entry.value;
}

function setCache(key, value) {
  cache.set(key, { value, expiresAt: Date.now() + CACHE_TTL_MS });
}

function parseTickers(raw) {
  return raw
    .split(",")
    .map((t) => t.trim().toUpperCase())
    .filter(Boolean)
    .slice(0, MAX_TICKERS);
}

function formatDate(date) {
  return date.toISOString().slice(0, 10);
}

function toDayNumber(date) {
  return String(date.getDate()).padStart(2, "0");
}

function bestDaysFromCounts(counts) {
  let maxCount = 0;
  Object.values(counts).forEach((count) => {
    if (count > maxCount) maxCount = count;
  });
  if (maxCount === 0) return [];
  return Object.keys(counts).filter((day) => counts[day] === maxCount);
}

function sortFreqDays(counts, bestDays) {
  return Object.entries(counts)
    .map(([day, count]) => ({
      day,
      count,
      isBest: bestDays.includes(day),
    }))
    .sort((a, b) => {
      if (b.count !== a.count) return b.count - a.count;
      return a.day.localeCompare(b.day);
    });
}

function computePerYear(records, monthIndex) {
  const byYear = new Map();
  records.forEach((r) => {
    if (!r.date) return;
    const date = new Date(r.date);
    if (Number.isNaN(date.valueOf())) return;
    if (date.getMonth() !== monthIndex) return;
    const year = date.getFullYear();
    const price = typeof r.low === "number" ? r.low : r.close;
    if (typeof price !== "number") return;
    if (!byYear.has(year)) byYear.set(year, []);
    byYear.get(year).push({ date, price });
  });

  const years = Array.from(byYear.keys()).sort((a, b) => b - a);
  const perYear = years.map((year) => {
    const lows = byYear
      .get(year)
      .sort((a, b) => a.price - b.price)
      .slice(0, 3)
      .map((item) => ({
        date: formatDate(item.date),
        price: item.price,
      }));
    return { year, lows };
  });

  return perYear;
}

async function fetchHistorical(ticker) {
  const to = new Date();
  const from = new Date();
  from.setFullYear(from.getFullYear() - HISTORY_YEARS);
  return yahooFinance.historical({
    symbol: ticker,
    from: formatDate(from),
    to: formatDate(to),
    period: "d",
  });
}

async function withConcurrency(items, limit, worker) {
  const results = [];
  let index = 0;
  let active = 0;

  return new Promise((resolve, reject) => {
    const next = () => {
      while (active < limit && index < items.length) {
        const currentIndex = index++;
        active++;
        Promise.resolve(worker(items[currentIndex]))
          .then((value) => {
            results[currentIndex] = value;
            active--;
            if (results.length === items.length && active === 0) {
              resolve(results);
            } else {
              next();
            }
          })
          .catch(reject);
      }
    };
    next();
  });
}

export default async function handler(req, res) {
  if (req.method !== "POST") {
    return res.status(405).json({ error: "Méthode non autorisée" });
  }

  const { tickers, month } = req.body || {};
  if (!tickers || !month) {
    return res.status(400).json({ error: "tickers et month sont requis" });
  }

  const monthIndex = MONTHS.indexOf(String(month).toLowerCase());
  if (monthIndex === -1) {
    return res.status(400).json({ error: "month invalide" });
  }

  const list = parseTickers(String(tickers));
  if (!list.length) {
    return res.status(400).json({ error: "tickers invalides" });
  }

  const cacheKey = `${list.join(",")}:${monthIndex}`;
  const cached = getCache(cacheKey);
  if (cached) {
    return res.status(200).json(cached);
  }

  try {
    const results = await withConcurrency(list, 4, async (ticker) => {
      const records = await fetchHistorical(ticker);
      const perYear = computePerYear(records, monthIndex);

      const dayCounts = {};
      perYear.forEach((yearItem) => {
        if (!yearItem.lows || !yearItem.lows.length) return;
        const day = toDayNumber(new Date(yearItem.lows[0].date));
        dayCounts[day] = (dayCounts[day] || 0) + 1;
      });

      const bestDays = bestDaysFromCounts(dayCounts);
      const freqDays = {
        sorted: sortFreqDays(dayCounts, bestDays),
      };

      return {
        ticker,
        bestDays,
        freqDays,
        perYear,
      };
    });

    const payload = { month: MONTHS[monthIndex], results };
    setCache(cacheKey, payload);
    return res.status(200).json(payload);
  } catch (err) {
    return res.status(500).json({
      error: "impossible de calculer l'analyse",
      detail: String(err),
    });
  }
}
