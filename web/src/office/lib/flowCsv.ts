// 真实的流量 CSV 解析器：把网络流（netflow/CIDDS 等）CSV 标准化为 PacketRecord。
// 自动识别列名，兼容 NetNomos 的 CIDDS 导出（Date first seen, Proto, Src IP Addr, ...）
// 以及通用的 source/destination/protocol/length 列。

import type { PacketRecord } from "../types/domain";

export interface ParsedCsv {
  packets: PacketRecord[];
  truncated: boolean;
  columns: string[];
}

const COLUMN_ALIASES: Record<string, string[]> = {
  time: ["date first seen", "time", "frame.time_epoch", "timestamp", "ts", "start time"],
  duration: ["duration"],
  proto: ["proto", "protocol", "_ws.col.protocol"],
  srcIp: ["src ip addr", "source", "src", "ip.src", "srcaddr", "source ip"],
  srcPort: ["src pt", "src port", "srcport", "sport", "tcp.srcport"],
  dstIp: ["dst ip addr", "destination", "dst", "ip.dst", "dstaddr", "destination ip"],
  dstPort: ["dst pt", "dst port", "dstport", "dport", "tcp.dstport"],
  packets: ["packets", "pkts", "frame.number"],
  bytes: ["bytes", "length", "frame.len", "octets"],
  flags: ["flags", "tcp.flags"],
  info: ["info", "label", "class"],
};

export function parseFlowCsv(text: string, maxRows = 20000): ParsedCsv {
  const lines = splitLines(text);
  if (lines.length < 2) return { packets: [], truncated: false, columns: [] };

  const delimiter = detectDelimiter(lines[0]);
  const headers = splitLine(lines[0], delimiter).map((h) => h.trim());
  const lower = headers.map((h) => h.toLowerCase());
  const colIndex = (logical: string) => {
    for (const alias of COLUMN_ALIASES[logical]) {
      const idx = lower.indexOf(alias);
      if (idx !== -1) return idx;
    }
    return -1;
  };

  const idx = {
    time: colIndex("time"),
    duration: colIndex("duration"),
    proto: colIndex("proto"),
    srcIp: colIndex("srcIp"),
    srcPort: colIndex("srcPort"),
    dstIp: colIndex("dstIp"),
    dstPort: colIndex("dstPort"),
    packets: colIndex("packets"),
    bytes: colIndex("bytes"),
    flags: colIndex("flags"),
    info: colIndex("info"),
  };

  const packets: PacketRecord[] = [];
  let truncated = false;
  const limit = Math.min(lines.length - 1, maxRows);

  for (let i = 1; i <= limit; i += 1) {
    const values = splitLine(lines[i], delimiter);
    if (values.length === 1 && values[0] === "") continue;
    const get = (j: number) => (j >= 0 && j < values.length ? values[j].trim() : "");

    const proto = (get(idx.proto) || "FLOW").toUpperCase().replace(/\s+/g, "");
    const srcIp = get(idx.srcIp) || "—";
    const dstIp = get(idx.dstIp) || "—";
    const srcPort = get(idx.srcPort);
    const dstPort = get(idx.dstPort);
    const source = srcPort ? `${srcIp}:${srcPort}` : srcIp;
    const destination = dstPort ? `${dstIp}:${dstPort}` : dstIp;
    const bytes = toNumber(get(idx.bytes), 0);
    const pktCount = toNumber(get(idx.packets), 0);
    const flags = get(idx.flags);
    const duration = get(idx.duration);
    const rawLabel = get(idx.info);

    const infoParts: string[] = [];
    if (pktCount) infoParts.push(`${pktCount} pkts`);
    if (bytes) infoParts.push(`${bytes} bytes`);
    if (flags && flags !== "0") infoParts.push(`flags ${flags}`);
    if (duration) infoParts.push(`dur ${duration}s`);
    if (rawLabel) infoParts.push(rawLabel);

    const raw: Record<string, string | number> = {};
    headers.forEach((header, j) => {
      const v = get(j);
      if (v !== "") raw[header] = v;
    });

    const time = get(idx.time) || `${i}`;
    const epoch = parseEpoch(time, i);

    packets.push({
      id: i,
      time: idx.time >= 0 ? time : `${i}.000000`,
      source,
      destination,
      protocol: proto,
      length: bytes || pktCount || 0,
      info: infoParts.join(" · ") || `flow ${i}`,
      tree: [],
      hex: "",
      sourceFormat: "csv",
      raw,
      epoch,
      searchText: [source, destination, proto, infoParts.join(" "), rawLabel].join(" ").toLowerCase(),
    });
  }

  if (lines.length - 1 > maxRows) truncated = true;
  return { packets, truncated, columns: headers };
}

function detectDelimiter(headerLine: string): string {
  const candidates = [",", ";", "\t", "|"];
  let best = ",";
  let bestCount = -1;
  for (const d of candidates) {
    const count = headerLine.split(d).length;
    if (count > bestCount) {
      bestCount = count;
      best = d;
    }
  }
  return best;
}

function splitLines(text: string): string[] {
  return text.split(/\r?\n/).filter((line, index) => index === 0 || line.length > 0);
}

function splitLine(line: string, delimiter: string): string[] {
  const result: string[] = [];
  let current = "";
  let quoted = false;
  for (let i = 0; i < line.length; i += 1) {
    const char = line[i];
    if (char === '"') {
      if (quoted && line[i + 1] === '"') {
        current += '"';
        i += 1;
      } else {
        quoted = !quoted;
      }
      continue;
    }
    if (char === delimiter && !quoted) {
      result.push(current);
      current = "";
      continue;
    }
    current += char;
  }
  result.push(current);
  return result;
}

function toNumber(value: string, fallback: number): number {
  const n = Number(value.replace(/[^0-9.eE+-]/g, ""));
  return Number.isFinite(n) ? n : fallback;
}

function parseEpoch(value: string, fallbackIndex: number): number {
  // "2017-03-23 16:38:23.258" → epoch 秒
  const isoLike = value.replace(" ", "T");
  const ms = Date.parse(isoLike);
  if (Number.isFinite(ms)) return ms / 1000;
  const asNumber = Number(value);
  if (Number.isFinite(asNumber)) return asNumber;
  return fallbackIndex;
}
