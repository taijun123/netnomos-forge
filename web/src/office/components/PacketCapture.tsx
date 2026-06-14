import { AnimatePresence, motion } from "framer-motion";
import {
  ArrowLeft,
  ChevronRight,
  Database,
  FileJson,
  Filter,
  FolderUp,
  Loader2,
  Pause,
  Play,
  Search,
  Upload,
} from "lucide-react";
import { useDeferredValue, useMemo, useRef, useState } from "react";
import { packetRows as seedPackets } from "../data/mockData";
import type { PacketLayer, PacketRecord } from "../types/domain";
import { buildLayers, hexDump, parseCapture } from "../lib/pcap";
import { parseFlowCsv } from "../lib/flowCsv";
import { PacketFlow3D } from "./PacketFlow3D";

interface PacketCaptureProps {
  open: boolean;
  onBack: () => void;
}

const MAX_TABLE_ROWS = 800; // 表格 DOM 渲染上限，超出用计数提示
const PARSE_LIMIT = 20000; // 单文件解析包数上限，避免浏览器卡死

interface SourceMeta {
  label: string;
  format: "pcap" | "pcapng" | "csv" | "demo";
  totalParsed: number;
  truncated: boolean;
}

export function PacketCapture({ open, onBack }: PacketCaptureProps) {
  const [packets, setPackets] = useState<PacketRecord[]>(seedPackets);
  const [selectedId, setSelectedId] = useState<number>(seedPackets[1].id);
  const [query, setQuery] = useState("");
  const [protocol, setProtocol] = useState<string>("ALL");
  const [playing, setPlaying] = useState(true);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [source, setSource] = useState<SourceMeta>({
    label: "demo-mixed-source（内置示例）",
    format: "demo",
    totalParsed: seedPackets.length,
    truncated: false,
  });
  const fileInputRef = useRef<HTMLInputElement | null>(null);

  const deferredQuery = useDeferredValue(query);
  const deferredProtocol = useDeferredValue(protocol);

  // 当前数据集里实际出现的协议（动态生成下拉项）
  const protocolOptions = useMemo(() => {
    const set = new Set<string>();
    packets.forEach((p) => set.add(p.protocol));
    return ["ALL", ...Array.from(set).sort()];
  }, [packets]);

  const filteredPackets = useMemo(() => {
    const tokens = deferredQuery
      .toLowerCase()
      .split(/\s+/)
      .map((t) => t.trim())
      .filter(Boolean);
    const out: PacketRecord[] = [];
    for (const packet of packets) {
      if (deferredProtocol !== "ALL" && packet.protocol !== deferredProtocol) continue;
      if (tokens.length) {
        const haystack =
          packet.searchText ??
          `${packet.source} ${packet.destination} ${packet.protocol} ${packet.info}`.toLowerCase();
        if (!tokens.every((token) => haystack.includes(token))) continue;
      }
      out.push(packet);
    }
    return out;
  }, [packets, deferredQuery, deferredProtocol]);

  const visibleRows = useMemo(() => filteredPackets.slice(0, MAX_TABLE_ROWS), [filteredPackets]);

  const selected = useMemo(
    () =>
      filteredPackets.find((row) => row.id === selectedId) ??
      packets.find((row) => row.id === selectedId) ??
      filteredPackets[0] ??
      packets[0],
    [filteredPackets, packets, selectedId]
  );

  const stats = useMemo(() => {
    let bytes = 0;
    const endpoints = new Set<string>();
    for (const packet of filteredPackets) {
      bytes += packet.length;
      endpoints.add(hostOf(packet.source));
      endpoints.add(hostOf(packet.destination));
    }
    const span =
      filteredPackets.length > 1 && filteredPackets[0].epoch != null
        ? (filteredPackets[filteredPackets.length - 1].epoch! - filteredPackets[0].epoch!)
        : 0;
    return { bytes, endpoints: endpoints.size, count: filteredPackets.length, span };
  }, [filteredPackets]);

  async function handleFiles(fileList: FileList | null) {
    const file = fileList?.[0];
    if (!file) return;
    setError(null);
    setLoading(true);
    setProtocol("ALL");
    setQuery("");
    try {
      const name = file.name.toLowerCase();
      if (name.endsWith(".csv")) {
        const text = await file.text();
        const parsed = parseFlowCsv(text, PARSE_LIMIT);
        if (!parsed.packets.length) throw new Error("CSV 中没有可解析的数据行");
        setPackets(parsed.packets);
        setSelectedId(parsed.packets[0].id);
        setSource({ label: file.name, format: "csv", totalParsed: parsed.packets.length, truncated: parsed.truncated });
      } else {
        // pcap / pcapng：读为二进制后真实解析
        const buffer = await file.arrayBuffer();
        const result = parseCapture(buffer, { maxPackets: PARSE_LIMIT });
        if (!result.packets.length) throw new Error("未从该抓包文件解析出数据包");
        setPackets(result.packets);
        setSelectedId(result.packets[0].id);
        setSource({
          label: file.name,
          format: result.format,
          totalParsed: result.packets.length,
          truncated: result.truncated,
        });
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : "解析失败");
    } finally {
      setLoading(false);
      if (fileInputRef.current) fileInputRef.current.value = "";
    }
  }

  return (
    <AnimatePresence>
      {open ? (
        <motion.main
          className="packet-workbench"
          initial={{ opacity: 0, y: 18 }}
          animate={{ opacity: 1, y: 0 }}
          exit={{ opacity: 0, y: 18 }}
        >
          <header className="packet-workbench-title">
            <button className="icon-button" onClick={onBack} aria-label="返回办公室">
              <ArrowLeft size={17} />
            </button>
            <div>
              <strong>快递B · pcap/csv 抓包工作台</strong>
              <span>{source.label}</span>
            </div>
            <label className="capture-upload">
              {loading ? <Loader2 size={15} className="spin" /> : <Upload size={15} />}
              {loading ? "解析中…" : "导入 pcap / pcapng / csv"}
              <input
                ref={fileInputRef}
                type="file"
                accept=".csv,.pcap,.pcapng,.cap"
                onChange={(event) => handleFiles(event.currentTarget.files)}
              />
            </label>
          </header>

          <section className="packet-workbench-grid">
            <aside className="capture-sidebar">
              <div className="capture-card">
                <div className="capture-card-title">
                  <Database size={16} />
                  <strong>数据源</strong>
                </div>
                <p>{source.label}</p>
                <div className="capture-source-meta">
                  <span className={`source-badge source-badge--${source.format}`}>{source.format.toUpperCase()}</span>
                  <span>已解析 {source.totalParsed.toLocaleString()} 包</span>
                </div>
                {source.truncated && (
                  <p className="capture-warn">⚠ 文件较大，仅解析前 {PARSE_LIMIT.toLocaleString()} 个包用于演示</p>
                )}
                <div className="capture-stat-grid">
                  <span>
                    <b>{stats.count.toLocaleString()}</b>
                    显示包数
                  </span>
                  <span>
                    <b>{stats.endpoints}</b>
                    端点
                  </span>
                  <span>
                    <b>{formatBytes(stats.bytes)}</b>
                    总流量
                  </span>
                </div>
                {stats.span > 0 && <p className="capture-span">时间跨度 {stats.span.toFixed(3)} s</p>}
              </div>

              <div className="capture-card">
                <div className="capture-card-title">
                  <Filter size={16} />
                  <strong>筛选</strong>
                </div>
                <div className="capture-field">
                  <label>协议</label>
                  <select value={protocol} onChange={(event) => setProtocol(event.target.value)}>
                    {protocolOptions.map((item) => (
                      <option key={item} value={item}>
                        {item}
                      </option>
                    ))}
                  </select>
                </div>
                <div className="capture-field">
                  <label>显示过滤器</label>
                  <p className="capture-hint-small">支持多关键字（空格分隔），匹配地址 / 协议 / Info。</p>
                </div>
              </div>

              <div className="capture-card capture-card--hint">
                <FolderUp size={18} />
                <p>
                  pcap / pcapng 在浏览器端真实解析帧字节（以太网 / IPv4·v6 / TCP·UDP·ICMP·ARP / DNS·TLS·HTTP）；CSV
                  按 netflow 字段标准化。可直接导入 NetNomos 的 <code>netflix.pcap</code> 或{" "}
                  <code>cidds_*.csv</code>。
                </p>
              </div>
            </aside>

            <section className="capture-main">
              <div className="capture-toolbar">
                <button
                  className={playing ? "button button-primary" : "button button-secondary"}
                  onClick={() => setPlaying((value) => !value)}
                >
                  {playing ? <Pause size={14} /> : <Play size={14} />}
                  {playing ? "暂停粒子" : "播放粒子"}
                </button>
                <label className="capture-search">
                  <Search size={15} />
                  <input
                    value={query}
                    placeholder="显示过滤器，如：192.168 TCP rule"
                    onChange={(event) => setQuery(event.target.value)}
                  />
                </label>
              </div>

              {error && <div className="capture-error">解析失败：{error}</div>}

              <PacketFlow3D
                packets={filteredPackets}
                selectedId={selected?.id ?? -1}
                playing={playing}
                onSelectPacket={setSelectedId}
              />

              <div className="packet-table-card">
                <table className="packet-table">
                  <thead>
                    <tr>
                      <th>No.</th>
                      <th>Time</th>
                      <th>Source</th>
                      <th>Destination</th>
                      <th>Protocol</th>
                      <th>Length</th>
                      <th>Info</th>
                    </tr>
                  </thead>
                  <tbody>
                    {visibleRows.map((row) => (
                      <tr
                        key={row.id}
                        className={selected?.id === row.id ? "is-selected" : ""}
                        onClick={() => setSelectedId(row.id)}
                      >
                        <td>{row.id}</td>
                        <td>{row.time}</td>
                        <td className="cell-mono">{row.source}</td>
                        <td className="cell-mono">{row.destination}</td>
                        <td>
                          <span className={`protocol protocol--${protocolClass(row.protocol)}`}>{row.protocol}</span>
                        </td>
                        <td>{row.length}</td>
                        <td className="cell-info">{row.info}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
                {filteredPackets.length > MAX_TABLE_ROWS && (
                  <div className="packet-table-more">
                    仅显示前 {MAX_TABLE_ROWS} 行，共 {filteredPackets.length.toLocaleString()} 个匹配包 · 用过滤器缩小范围
                  </div>
                )}
                {filteredPackets.length === 0 && <div className="packet-table-more">没有匹配的包，调整过滤器试试</div>}
              </div>
            </section>

            <aside className="packet-inspector">
              {selected ? (
                <>
                  <PacketTree row={selected} />
                  <RawFields row={selected} />
                  <div className="hex-view">
                    <header>
                      <strong>Packet Bytes</strong>
                      <span>frame {selected.id}</span>
                    </header>
                    <pre>{selected.bytes ? hexDump(selected.bytes) : formatLegacyHex(selected.hex)}</pre>
                  </div>
                </>
              ) : (
                <div className="capture-card">选择一个数据包查看详情</div>
              )}
            </aside>
          </section>
        </motion.main>
      ) : null}
    </AnimatePresence>
  );
}

function PacketTree({ row }: { row: PacketRecord }) {
  const layers: PacketLayer[] = useMemo(() => buildLayers(row), [row]);
  const [collapsed, setCollapsed] = useState<Record<number, boolean>>({});
  return (
    <div className="packet-tree">
      <header>
        <strong>协议详情</strong>
        <span>{row.protocol}</span>
      </header>
      {layers.map((layer, index) => {
        const isCollapsed = collapsed[index];
        return (
          <div className="tree-layer" key={layer.title}>
            <button
              className="tree-layer-head"
              onClick={() => setCollapsed((prev) => ({ ...prev, [index]: !prev[index] }))}
            >
              <ChevronRight size={13} className={isCollapsed ? "" : "is-open"} />
              <span>{layer.title}</span>
            </button>
            {!isCollapsed &&
              layer.fields.map((field, fieldIndex) => (
                <div className="tree-field" key={`${field.name}-${fieldIndex}`}>
                  {field.name && <span className="tree-field-name">{field.name}</span>}
                  <span className="tree-field-value">{field.value}</span>
                </div>
              ))}
          </div>
        );
      })}
    </div>
  );
}

function RawFields({ row }: { row: PacketRecord }) {
  const entries = Object.entries(row.raw).slice(0, 24);
  return (
    <div className="raw-fields">
      <header>
        <FileJson size={15} />
        <strong>{row.sourceFormat === "csv" ? "CSV 原始列" : "标准化字段"}</strong>
      </header>
      {entries.map(([key, value]) => (
        <div key={key}>
          <span>{key}</span>
          <b>{String(value)}</b>
        </div>
      ))}
    </div>
  );
}

function formatLegacyHex(hex: string) {
  if (!hex) return "（无字节数据）";
  const values = hex.split(" ");
  const lines: string[] = [];
  for (let i = 0; i < values.length; i += 16) {
    const chunk = values.slice(i, i + 16);
    lines.push(`${i.toString(16).padStart(4, "0")}  ${chunk.join(" ")}`);
  }
  return lines.join("\n");
}

function hostOf(value: string): string {
  const idx = value.lastIndexOf(":");
  return idx > 0 ? value.slice(0, idx) : value;
}

function formatBytes(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(2)} MB`;
}

function protocolClass(protocol: string): string {
  const known = ["dns", "tcp", "http", "tls", "plugin", "csv", "udp", "icmp", "arp"];
  const lower = protocol.toLowerCase();
  const match = known.find((k) => lower.includes(k));
  return match ?? "other";
}
