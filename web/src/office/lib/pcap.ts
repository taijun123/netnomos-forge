// 真实的 pcap / pcapng 解析器 + 链路层/网络层/传输层/部分应用层解码器。
// 纯前端、零依赖，在浏览器里直接读用户导入的 .pcap/.pcapng 文件。
// 设计目标：能打开 NetNomos 的 netflix.pcap / mawi_*.pcap 这类真实抓包文件。

import type { PacketLayer, PacketRecord } from "../types/domain";

export interface ParsedCapture {
  packets: PacketRecord[];
  linkType: number;
  truncated: boolean; // 是否因为达到上限而停止
  format: "pcap" | "pcapng";
}

const PCAP_MAGIC_LE = 0xa1b2c3d4;
const PCAP_MAGIC_BE = 0xd4c3b2a1;
const PCAP_MAGIC_NS_LE = 0xa1b23c4d; // 纳秒精度
const PCAP_MAGIC_NS_BE = 0x4d3cb2a1;
const PCAPNG_MAGIC = 0x0a0d0d0a;

// 链路层类型
const LINKTYPE_ETHERNET = 1;
const LINKTYPE_RAW = 101;
const LINKTYPE_LINUX_SLL = 113;
const LINKTYPE_RAW_IP4 = 228;
const LINKTYPE_RAW_IP6 = 229;

export interface ParseOptions {
  maxPackets?: number; // 防止超大文件卡死浏览器
}

export function parseCapture(buffer: ArrayBuffer, options: ParseOptions = {}): ParsedCapture {
  const view = new DataView(buffer);
  if (buffer.byteLength < 4) throw new Error("文件过小，不是有效的抓包文件");
  const magicBE = view.getUint32(0, false);
  if (magicBE === PCAPNG_MAGIC) {
    return parsePcapng(buffer, options);
  }
  const magicLE = view.getUint32(0, true);
  if (
    magicLE === PCAP_MAGIC_LE ||
    magicLE === PCAP_MAGIC_BE ||
    magicLE === PCAP_MAGIC_NS_LE ||
    magicLE === PCAP_MAGIC_NS_BE
  ) {
    return parseClassicPcap(buffer, options);
  }
  throw new Error("无法识别的文件头：既不是 pcap 也不是 pcapng");
}

/* ----------------------------- 经典 pcap ----------------------------- */

function parseClassicPcap(buffer: ArrayBuffer, options: ParseOptions): ParsedCapture {
  const view = new DataView(buffer);
  const bytes = new Uint8Array(buffer);
  const magic = view.getUint32(0, true);
  const little = magic === PCAP_MAGIC_LE || magic === PCAP_MAGIC_NS_LE;
  const nano = magic === PCAP_MAGIC_NS_LE || magic === PCAP_MAGIC_NS_BE;
  const linkType = view.getUint32(20, little);

  const max = options.maxPackets ?? 20000;
  const packets: PacketRecord[] = [];
  let offset = 24; // 全局头 24 字节
  let truncated = false;
  let baseEpoch = 0;
  let id = 1;

  while (offset + 16 <= buffer.byteLength) {
    const tsSec = view.getUint32(offset, little);
    const tsFrac = view.getUint32(offset + 4, little);
    const capLen = view.getUint32(offset + 8, little);
    const origLen = view.getUint32(offset + 12, little);
    offset += 16;
    if (capLen === 0 || offset + capLen > buffer.byteLength) break;
    const frame = bytes.subarray(offset, offset + capLen);
    offset += capLen;

    const epoch = tsSec + (nano ? tsFrac / 1e9 : tsFrac / 1e6);
    if (id === 1) baseEpoch = epoch;
    packets.push(buildRecord(id++, frame, linkType, epoch, epoch - baseEpoch, origLen));

    if (packets.length >= max) {
      truncated = true;
      break;
    }
  }

  return { packets, linkType, truncated, format: "pcap" };
}

/* ----------------------------- pcapng ----------------------------- */

function parsePcapng(buffer: ArrayBuffer, options: ParseOptions): ParsedCapture {
  const view = new DataView(buffer);
  const bytes = new Uint8Array(buffer);
  const max = options.maxPackets ?? 20000;
  const packets: PacketRecord[] = [];
  const interfaceLinkTypes: number[] = [];
  const interfaceTsResol: number[] = []; // 每接口的时间精度（10^-n 秒）

  let offset = 0;
  let little = true;
  let truncated = false;
  let baseEpoch = 0;
  let id = 1;
  let primaryLink = LINKTYPE_ETHERNET;

  while (offset + 12 <= buffer.byteLength) {
    const blockType = view.getUint32(offset, little);
    // Section Header Block 决定字节序
    if (blockType === PCAPNG_MAGIC) {
      const bom = view.getUint32(offset + 8, true);
      little = bom === 0x1a2b3c4d;
    }
    const blockLen = view.getUint32(offset + 4, little);
    if (blockLen < 12 || offset + blockLen > buffer.byteLength) break;

    if (blockType === 0x00000001) {
      // Interface Description Block
      const linkType = view.getUint16(offset + 8, little);
      interfaceLinkTypes.push(linkType);
      interfaceTsResol.push(readTsResol(view, bytes, offset, blockLen, little));
      if (interfaceLinkTypes.length === 1) primaryLink = linkType;
    } else if (blockType === 0x00000006 || blockType === 0x00000003) {
      // Enhanced Packet Block (6) / Simple Packet Block (3)
      const enhanced = blockType === 0x00000006;
      const ifaceId = enhanced ? view.getUint32(offset + 8, little) : 0;
      const tsHigh = enhanced ? view.getUint32(offset + 12, little) : 0;
      const tsLow = enhanced ? view.getUint32(offset + 16, little) : 0;
      const capLen = enhanced ? view.getUint32(offset + 20, little) : view.getUint32(offset + 8, little);
      const origLen = enhanced ? view.getUint32(offset + 24, little) : capLen;
      const dataStart = offset + (enhanced ? 28 : 12);
      if (dataStart + capLen <= buffer.byteLength) {
        const frame = bytes.subarray(dataStart, dataStart + capLen);
        const resol = interfaceTsResol[ifaceId] ?? 1e6;
        const ts = (tsHigh * 0x100000000 + tsLow) / resol;
        if (id === 1) baseEpoch = ts;
        const linkType = interfaceLinkTypes[ifaceId] ?? primaryLink;
        packets.push(buildRecord(id++, frame, linkType, ts, ts - baseEpoch, origLen));
        if (packets.length >= max) {
          truncated = true;
          break;
        }
      }
    }
    offset += blockLen;
  }

  return { packets, linkType: primaryLink, truncated, format: "pcapng" };
}

function readTsResol(view: DataView, bytes: Uint8Array, blockOffset: number, blockLen: number, little: boolean): number {
  // 在 IDB options 中查找 if_tsresol (code 9)
  let pos = blockOffset + 16; // 跳过 block header(8) + linktype(2)+reserved(2)+snaplen(4)
  const end = blockOffset + blockLen - 4;
  while (pos + 4 <= end) {
    const code = view.getUint16(pos, little);
    const len = view.getUint16(pos + 2, little);
    if (code === 0) break;
    if (code === 9 && len >= 1) {
      const raw = bytes[pos + 4];
      return raw & 0x80 ? Math.pow(2, raw & 0x7f) : Math.pow(10, raw);
    }
    pos += 4 + len + ((4 - (len % 4)) % 4);
  }
  return 1e6; // 默认微秒
}

/* ----------------------------- 解码 ----------------------------- */

function buildRecord(
  id: number,
  frame: Uint8Array,
  linkType: number,
  epoch: number,
  relTime: number,
  origLen: number
): PacketRecord {
  const decoded = decodeFrame(frame, linkType);
  const time = relTime.toFixed(6);
  const searchText = [
    decoded.source,
    decoded.destination,
    decoded.protocol,
    decoded.info,
    String(origLen),
  ]
    .join(" ")
    .toLowerCase();

  return {
    id,
    time,
    source: decoded.source,
    destination: decoded.destination,
    protocol: decoded.protocol,
    length: origLen,
    info: decoded.info,
    tree: [], // 真实包用 layers 懒解码，tree 留空兼容旧类型
    hex: "",
    sourceFormat: "pcap",
    raw: decoded.raw,
    bytes: frame,
    linkType,
    epoch,
    searchText,
  };
}

interface Decoded {
  source: string;
  destination: string;
  protocol: string;
  info: string;
  raw: Record<string, string | number>;
}

function decodeFrame(frame: Uint8Array, linkType: number): Decoded {
  try {
    if (linkType === LINKTYPE_ETHERNET) return decodeEthernet(frame);
    if (linkType === LINKTYPE_RAW || linkType === LINKTYPE_RAW_IP4 || linkType === LINKTYPE_RAW_IP6) {
      return decodeIp(frame, 0, {});
    }
    if (linkType === LINKTYPE_LINUX_SLL) return decodeLinuxSll(frame);
  } catch {
    // 解码失败时退化为原始帧
  }
  return {
    source: "-",
    destination: "-",
    protocol: `LINK#${linkType}`,
    info: `${frame.length} bytes captured`,
    raw: { linkType, frameLength: frame.length },
  };
}

function decodeLinuxSll(frame: Uint8Array): Decoded {
  const dv = dvOf(frame);
  const proto = dv.getUint16(14, false);
  return decodeByEtherType(frame, 16, proto, {});
}

function decodeEthernet(frame: Uint8Array): Decoded {
  const dv = dvOf(frame);
  const dst = mac(frame, 0);
  const src = mac(frame, 6);
  let etherType = dv.getUint16(12, false);
  let payloadOffset = 14;
  // 802.1Q VLAN tag
  if (etherType === 0x8100 && frame.length >= 18) {
    etherType = dv.getUint16(16, false);
    payloadOffset = 18;
  }
  const base = { "eth.src": src, "eth.dst": dst };
  return decodeByEtherType(frame, payloadOffset, etherType, base);
}

function decodeByEtherType(
  frame: Uint8Array,
  offset: number,
  etherType: number,
  base: Record<string, string | number>
): Decoded {
  if (etherType === 0x0800) return decodeIp(frame, offset, base);
  if (etherType === 0x86dd) return decodeIp(frame, offset, base);
  if (etherType === 0x0806) return decodeArp(frame, offset, base);
  return {
    source: String(base["eth.src"] ?? "-"),
    destination: String(base["eth.dst"] ?? "-"),
    protocol: etherType === 0x8035 ? "RARP" : `0x${etherType.toString(16)}`,
    info: `EtherType 0x${etherType.toString(16)}`,
    raw: { ...base, etherType: `0x${etherType.toString(16)}` },
  };
}

function decodeArp(frame: Uint8Array, offset: number, base: Record<string, string | number>): Decoded {
  const dv = dvOf(frame);
  const op = dv.getUint16(offset + 6, false);
  const senderIp = ip4(frame, offset + 14);
  const targetIp = ip4(frame, offset + 24);
  const info =
    op === 1
      ? `Who has ${targetIp}? Tell ${senderIp}`
      : op === 2
        ? `${senderIp} is at ${mac(frame, offset + 8)}`
        : `ARP opcode ${op}`;
  return {
    source: senderIp,
    destination: targetIp,
    protocol: "ARP",
    info,
    raw: { ...base, "arp.opcode": op, "arp.src": senderIp, "arp.dst": targetIp },
  };
}

function decodeIp(frame: Uint8Array, offset: number, base: Record<string, string | number>): Decoded {
  const dv = dvOf(frame);
  const version = frame[offset] >> 4;
  if (version === 4) {
    const ihl = (frame[offset] & 0x0f) * 4;
    const totalLen = dv.getUint16(offset + 2, false);
    const proto = frame[offset + 9];
    const ttl = frame[offset + 8];
    const src = ip4(frame, offset + 12);
    const dst = ip4(frame, offset + 16);
    const raw = { ...base, "ip.version": 4, "ip.src": src, "ip.dst": dst, "ip.ttl": ttl, "ip.proto": proto, "ip.len": totalLen };
    return decodeTransport(frame, offset + ihl, proto, src, dst, raw);
  }
  if (version === 6) {
    const proto = frame[offset + 6];
    const src = ip6(frame, offset + 8);
    const dst = ip6(frame, offset + 24);
    const raw = { ...base, "ip.version": 6, "ipv6.src": src, "ipv6.dst": dst, "ip.proto": proto };
    return decodeTransport(frame, offset + 40, proto, src, dst, raw);
  }
  return {
    source: "-",
    destination: "-",
    protocol: "IP?",
    info: `IP version ${version}`,
    raw: { ...base, "ip.version": version },
  };
}

function decodeTransport(
  frame: Uint8Array,
  offset: number,
  proto: number,
  src: string,
  dst: string,
  raw: Record<string, string | number>
): Decoded {
  const dv = dvOf(frame);
  if (proto === 6 && offset + 20 <= frame.length) {
    // TCP
    const sport = dv.getUint16(offset, false);
    const dport = dv.getUint16(offset + 2, false);
    const seq = dv.getUint32(offset + 4, false);
    const ack = dv.getUint32(offset + 8, false);
    const dataOffset = (frame[offset + 12] >> 4) * 4;
    const flags = frame[offset + 13];
    const window = dv.getUint16(offset + 14, false);
    const payloadOffset = offset + dataOffset;
    const flagStr = tcpFlags(flags);
    const app = appLayer(frame, payloadOffset, sport, dport, "tcp");
    raw["tcp.srcport"] = sport;
    raw["tcp.dstport"] = dport;
    raw["tcp.seq"] = seq;
    raw["tcp.ack"] = ack;
    raw["tcp.flags"] = flagStr;
    raw["tcp.window"] = window;
    const payloadLen = Math.max(0, frame.length - payloadOffset);
    return {
      source: `${src}:${sport}`,
      destination: `${dst}:${dport}`,
      protocol: app.protocol ?? "TCP",
      info: app.info ?? `${sport} → ${dport} [${flagStr}] Seq=${seq} Ack=${ack} Win=${window} Len=${payloadLen}`,
      raw,
    };
  }
  if (proto === 17 && offset + 8 <= frame.length) {
    // UDP
    const sport = dv.getUint16(offset, false);
    const dport = dv.getUint16(offset + 2, false);
    const ulen = dv.getUint16(offset + 4, false);
    const payloadOffset = offset + 8;
    const app = appLayer(frame, payloadOffset, sport, dport, "udp");
    raw["udp.srcport"] = sport;
    raw["udp.dstport"] = dport;
    raw["udp.length"] = ulen;
    return {
      source: `${src}:${sport}`,
      destination: `${dst}:${dport}`,
      protocol: app.protocol ?? "UDP",
      info: app.info ?? `${sport} → ${dport} Len=${ulen - 8}`,
      raw,
    };
  }
  if (proto === 1) {
    // ICMP
    const type = frame[offset];
    const code = frame[offset + 1];
    raw["icmp.type"] = type;
    raw["icmp.code"] = code;
    return { source: src, destination: dst, protocol: "ICMP", info: icmpInfo(type, code), raw };
  }
  if (proto === 58) {
    return { source: src, destination: dst, protocol: "ICMPv6", info: `ICMPv6 type ${frame[offset]}`, raw };
  }
  return {
    source: src,
    destination: dst,
    protocol: `IP proto ${proto}`,
    info: `protocol ${proto}`,
    raw,
  };
}

/* ----------------------------- 应用层 ----------------------------- */

function appLayer(
  frame: Uint8Array,
  offset: number,
  sport: number,
  dport: number,
  l4: "tcp" | "udp"
): { protocol?: string; info?: string } {
  if (offset >= frame.length) return {};

  if (sport === 53 || dport === 53) {
    const dns = decodeDns(frame, offset);
    if (dns) return dns;
  }
  if (l4 === "tcp" && (sport === 443 || dport === 443)) {
    const tls = decodeTls(frame, offset);
    if (tls) return tls;
  }
  if (l4 === "tcp" && (sport === 80 || dport === 80 || sport === 8080 || dport === 8080)) {
    const http = decodeHttp(frame, offset);
    if (http) return http;
  }
  return {};
}

function decodeDns(frame: Uint8Array, offset: number): { protocol: string; info: string } | null {
  if (offset + 12 > frame.length) return null;
  const dv = dvOf(frame);
  const id = dv.getUint16(offset, false);
  const flags = dv.getUint16(offset + 2, false);
  const qd = dv.getUint16(offset + 4, false);
  const isResponse = (flags & 0x8000) !== 0;
  let pos = offset + 12;
  let qname = "";
  if (qd > 0) {
    const parsed = readDnsName(frame, pos, offset);
    qname = parsed.name;
  }
  return {
    protocol: "DNS",
    info: `${isResponse ? "Standard query response" : "Standard query"} 0x${id.toString(16).padStart(4, "0")} ${qname}`.trim(),
  };
}

function readDnsName(frame: Uint8Array, pos: number, msgStart: number): { name: string; next: number } {
  const labels: string[] = [];
  let jumped = false;
  let next = pos;
  let guard = 0;
  while (pos < frame.length && guard++ < 128) {
    const len = frame[pos];
    if (len === 0) {
      if (!jumped) next = pos + 1;
      break;
    }
    if ((len & 0xc0) === 0xc0) {
      const pointer = ((len & 0x3f) << 8) | frame[pos + 1];
      if (!jumped) next = pos + 2;
      jumped = true;
      pos = msgStart + pointer;
      continue;
    }
    labels.push(textOf(frame, pos + 1, len));
    pos += len + 1;
  }
  return { name: labels.join(".") || "<root>", next };
}

function decodeTls(frame: Uint8Array, offset: number): { protocol: string; info: string } | null {
  const type = frame[offset];
  if (type < 20 || type > 24) return null; // 不是 TLS record
  const major = frame[offset + 1];
  if (major !== 3) return null;
  const recordType =
    type === 22 ? "Handshake" : type === 23 ? "Application Data" : type === 21 ? "Alert" : type === 20 ? "Change Cipher Spec" : "Record";
  let info = `TLS ${recordType}`;
  if (type === 22 && offset + 5 < frame.length) {
    const hs = frame[offset + 5];
    if (hs === 1) info = "TLS Client Hello";
    else if (hs === 2) info = "TLS Server Hello";
    else if (hs === 11) info = "TLS Certificate";
  }
  return { protocol: "TLS", info };
}

function decodeHttp(frame: Uint8Array, offset: number): { protocol: string; info: string } | null {
  const slice = frame.subarray(offset, Math.min(frame.length, offset + 256));
  const text = textOf(slice, 0, slice.length);
  if (/^(GET|POST|PUT|DELETE|HEAD|OPTIONS|PATCH) /.test(text)) {
    const line = text.split("\r\n")[0];
    return { protocol: "HTTP", info: line.slice(0, 120) };
  }
  if (/^HTTP\/\d/.test(text)) {
    const line = text.split("\r\n")[0];
    return { protocol: "HTTP", info: line.slice(0, 120) };
  }
  return null;
}

/* ----------------------------- 协议详情树（懒解码） ----------------------------- */

export function buildLayers(record: PacketRecord): PacketLayer[] {
  if (!record.bytes) {
    // 旧版演示/CSV 数据：用已有的纯文本树
    return [{ title: record.protocol, fields: record.tree.map((line) => ({ name: "", value: line })) }];
  }
  const layers: PacketLayer[] = [];
  layers.push({
    title: `Frame ${record.id}`,
    fields: [
      { name: "Arrival Time", value: `${record.time}s (相对)` },
      { name: "Epoch Time", value: `${record.epoch?.toFixed(6)}` },
      { name: "Frame Length", value: `${record.length} bytes` },
      { name: "Captured Length", value: `${record.bytes.length} bytes` },
      { name: "Link Type", value: linkTypeName(record.linkType ?? 1) },
    ],
  });
  // 从 raw 中按前缀聚合各层字段
  pushLayerFromRaw(layers, record.raw, "eth.", "Ethernet II");
  pushLayerFromRaw(layers, record.raw, "arp.", "Address Resolution Protocol");
  pushLayerFromRaw(layers, record.raw, "ip.", record.raw["ip.version"] === 6 ? "Internet Protocol v6" : "Internet Protocol v4");
  pushLayerFromRaw(layers, record.raw, "ipv6.", "Internet Protocol v6");
  pushLayerFromRaw(layers, record.raw, "tcp.", "Transmission Control Protocol");
  pushLayerFromRaw(layers, record.raw, "udp.", "User Datagram Protocol");
  pushLayerFromRaw(layers, record.raw, "icmp.", "Internet Control Message Protocol");
  return layers.filter((layer) => layer.fields.length > 0);
}

function pushLayerFromRaw(layers: PacketLayer[], raw: Record<string, string | number>, prefix: string, title: string) {
  const fields = Object.entries(raw)
    .filter(([key]) => key.startsWith(prefix))
    .map(([key, value]) => ({ name: key, value: String(value) }));
  if (fields.length) layers.push({ title, fields });
}

export function hexDump(bytes: Uint8Array, limit = 1024): string {
  const lines: string[] = [];
  const len = Math.min(bytes.length, limit);
  for (let i = 0; i < len; i += 16) {
    const chunk = bytes.subarray(i, Math.min(i + 16, len));
    const hex = Array.from(chunk)
      .map((b) => b.toString(16).padStart(2, "0"))
      .join(" ")
      .padEnd(16 * 3 - 1, " ");
    const ascii = Array.from(chunk)
      .map((b) => (b >= 32 && b < 127 ? String.fromCharCode(b) : "."))
      .join("");
    lines.push(`${i.toString(16).padStart(4, "0")}  ${hex}  ${ascii}`);
  }
  if (bytes.length > limit) lines.push(`… (${bytes.length - limit} more bytes)`);
  return lines.join("\n");
}

/* ----------------------------- 工具 ----------------------------- */

function dvOf(frame: Uint8Array): DataView {
  return new DataView(frame.buffer, frame.byteOffset, frame.byteLength);
}

function mac(frame: Uint8Array, offset: number): string {
  return Array.from(frame.subarray(offset, offset + 6))
    .map((b) => b.toString(16).padStart(2, "0"))
    .join(":");
}

function ip4(frame: Uint8Array, offset: number): string {
  return `${frame[offset]}.${frame[offset + 1]}.${frame[offset + 2]}.${frame[offset + 3]}`;
}

function ip6(frame: Uint8Array, offset: number): string {
  const parts: string[] = [];
  for (let i = 0; i < 16; i += 2) {
    parts.push(((frame[offset + i] << 8) | frame[offset + i + 1]).toString(16));
  }
  return compressIp6(parts.join(":"));
}

function compressIp6(addr: string): string {
  return addr.replace(/(^|:)0(:0)+(:|$)/, "::").replace(/:{3,}/, "::");
}

function tcpFlags(flags: number): string {
  const names: string[] = [];
  if (flags & 0x02) names.push("SYN");
  if (flags & 0x10) names.push("ACK");
  if (flags & 0x01) names.push("FIN");
  if (flags & 0x04) names.push("RST");
  if (flags & 0x08) names.push("PSH");
  if (flags & 0x20) names.push("URG");
  return names.join(", ") || "—";
}

function icmpInfo(type: number, code: number): string {
  if (type === 8) return "Echo (ping) request";
  if (type === 0) return "Echo (ping) reply";
  if (type === 3) return `Destination unreachable (code ${code})`;
  if (type === 11) return "Time-to-live exceeded";
  return `ICMP type ${type} code ${code}`;
}

function textOf(frame: Uint8Array, offset: number, len: number): string {
  let out = "";
  for (let i = 0; i < len && offset + i < frame.length; i += 1) {
    out += String.fromCharCode(frame[offset + i]);
  }
  return out;
}

function linkTypeName(linkType: number): string {
  const names: Record<number, string> = {
    1: "Ethernet (1)",
    101: "Raw IP (101)",
    113: "Linux cooked (113)",
    228: "Raw IPv4 (228)",
    229: "Raw IPv6 (229)",
  };
  return names[linkType] ?? `LinkType ${linkType}`;
}
