import axios from "axios";

const BASE = process.env.REACT_APP_BACKEND_URL;
export const API = `${BASE}/api`;

const c = axios.create({ baseURL: API, timeout: 20000 });

export const api = {
  state: () => c.get("/bot/state").then((r) => r.data),
  config: () => c.get("/bot/config").then((r) => r.data),
  analysis: () => c.get("/analysis").then((r) => r.data),
  events: () => c.get("/events?limit=30").then((r) => r.data),
  feed: () => c.get("/feed?limit=60").then((r) => r.data),
  decisions: () => c.get("/decisions?limit=30").then((r) => r.data),
  positions: () => c.get("/positions").then((r) => r.data),
  orders: () => c.get("/orders").then((r) => r.data),
  connection: () => c.get("/connection").then((r) => r.data),
  account: () => c.get("/account").then((r) => r.data),
  news: () => c.get("/news?limit=25").then((r) => r.data),
  scanner: () => c.get("/scanner").then((r) => r.data),
  setMode: (mode) => c.post("/bot/mode", { mode }).then((r) => r.data),
  setLive: (enabled, confirm) => c.post("/bot/live", { enabled, confirm }).then((r) => r.data),
  resume: () => c.post("/bot/resume").then((r) => r.data),
  stop: () => c.post("/bot/stop").then((r) => r.data),
  updateConfig: (body) => c.put("/bot/config", body).then((r) => r.data),
  cancelOrders: () => c.post("/emergency/cancel-orders").then((r) => r.data),
  closePositions: (confirm) => c.post("/emergency/close-positions", { confirm }).then((r) => r.data),
  protect: (symbol, stop_pct, take_pct) => c.post("/positions/protect", { symbol, stop_pct, take_pct }).then((r) => r.data),
  performance: () => c.get("/performance").then((r) => r.data),
  backtest: (body) => c.post("/backtest", body).then((r) => r.data),
};
