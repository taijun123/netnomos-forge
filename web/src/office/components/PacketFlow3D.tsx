import { useEffect, useMemo, useRef } from "react";
import * as THREE from "three";
import type { PacketRecord } from "../types/domain";

interface PacketFlow3DProps {
  packets: PacketRecord[];
  selectedId: number;
  onSelectPacket: (id: number) => void;
  playing: boolean;
}

const protocolColor: Record<string, string> = {
  DNS: "#5aa8ff",
  TCP: "#8b98a7",
  UDP: "#3fb6c4",
  HTTP: "#f3a51f",
  TLS: "#8f5cff",
  ICMP: "#e06c9f",
  ARP: "#c79a3a",
  PLUGIN: "#21b66f",
  CSV: "#12b8c8",
};
const OTHER_COLOR = "#9aa6b2";
const MAX_NODES = 14; // 大文件下只展示流量最高的端点，避免节点爆炸

function colorFor(protocol: string): string {
  if (protocolColor[protocol]) return protocolColor[protocol];
  const lower = protocol.toLowerCase();
  const key = Object.keys(protocolColor).find((k) => lower.includes(k.toLowerCase()));
  return key ? protocolColor[key] : OTHER_COLOR;
}

export function PacketFlow3D({ packets, selectedId, onSelectPacket, playing }: PacketFlow3DProps) {
  const mountRef = useRef<HTMLDivElement | null>(null);
  const onSelectRef = useRef(onSelectPacket);
  onSelectRef.current = onSelectPacket;

  const graph = useMemo(() => buildGraph(packets), [packets]);

  useEffect(() => {
    const mount = mountRef.current;
    if (!mount) return;
    const host = mount;

    const reduceMotion = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
    const scene = new THREE.Scene();
    scene.background = new THREE.Color("#f7fafc");

    const camera = new THREE.OrthographicCamera(-5.2, 5.2, 3.2, -3.2, 0.1, 100);
    camera.position.set(0, 4.2, 8);
    camera.lookAt(0, 0, 0);

    const renderer = new THREE.WebGLRenderer({ antialias: true, alpha: false });
    renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2));
    renderer.outputColorSpace = THREE.SRGBColorSpace;
    host.appendChild(renderer.domElement);

    const ambient = new THREE.AmbientLight(0xffffff, 1.8);
    const key = new THREE.DirectionalLight(0xffffff, 2.5);
    key.position.set(2, 5, 5);
    scene.add(ambient, key);

    const raycaster = new THREE.Raycaster();
    const pointer = new THREE.Vector2();
    const clickable: THREE.Mesh[] = [];
    const particles: Array<{
      mesh: THREE.Mesh;
      start: THREE.Vector3;
      end: THREE.Vector3;
      offset: number;
    }> = [];

    const floor = new THREE.Mesh(
      new THREE.PlaneGeometry(10.5, 6.2),
      new THREE.MeshStandardMaterial({ color: "#edf3f7", roughness: 0.85 })
    );
    floor.rotation.x = -Math.PI / 2;
    floor.position.y = -0.08;
    scene.add(floor);

    const nodePositions = new Map<string, THREE.Vector3>();
    graph.nodes.forEach((node, index) => {
      const angle = (index / Math.max(graph.nodes.length, 1)) * Math.PI * 2 - Math.PI / 2;
      const radiusX = 3.6;
      const radiusZ = 1.9;
      const position = new THREE.Vector3(Math.cos(angle) * radiusX, 0.18, Math.sin(angle) * radiusZ);
      nodePositions.set(node.id, position);

      const material = new THREE.MeshStandardMaterial({
        color: node.kind === "plugin" ? "#111827" : node.kind === "service" ? "#334155" : "#0f172a",
        roughness: 0.48,
        emissive: node.kind === "agent" ? new THREE.Color("#1d9bf0") : new THREE.Color("#000000"),
        emissiveIntensity: node.kind === "agent" ? 0.15 : 0,
      });
      const sphere = new THREE.Mesh(new THREE.SphereGeometry(0.18, 24, 16), material);
      sphere.position.copy(position);
      sphere.userData = { label: node.label };
      scene.add(sphere);

      const halo = new THREE.Mesh(
        new THREE.RingGeometry(0.26, 0.32, 32),
        new THREE.MeshBasicMaterial({
          color: node.kind === "plugin" ? "#22c55e" : "#93c5fd",
          transparent: true,
          opacity: 0.42,
          side: THREE.DoubleSide,
        })
      );
      halo.rotation.x = -Math.PI / 2;
      halo.position.copy(position);
      halo.position.y = 0.02;
      scene.add(halo);
    });

    graph.edges.forEach((edge, index) => {
      const start = nodePositions.get(edge.source);
      const end = nodePositions.get(edge.destination);
      if (!start || !end) return;

      const selected = edge.packetIds.includes(selectedId);
      const color = colorFor(edge.protocol);
      const tube = makeEdgeTube(start, end, color, selected);
      tube.userData = { packetId: edge.packetIds[0], edgeId: edge.id };
      clickable.push(tube);
      scene.add(tube);

      const particle = new THREE.Mesh(
        new THREE.SphereGeometry(selected ? 0.075 : 0.055, 16, 10),
        new THREE.MeshStandardMaterial({
          color,
          emissive: new THREE.Color(color),
          emissiveIntensity: selected ? 0.8 : 0.45,
        })
      );
      particle.position.copy(start);
      particles.push({ mesh: particle, start: start.clone(), end: end.clone(), offset: index / Math.max(graph.edges.length, 1) });
      scene.add(particle);
    });

    function handlePointerDown(event: PointerEvent) {
      const rect = renderer.domElement.getBoundingClientRect();
      pointer.x = ((event.clientX - rect.left) / rect.width) * 2 - 1;
      pointer.y = -((event.clientY - rect.top) / rect.height) * 2 + 1;
      raycaster.setFromCamera(pointer, camera);
      const hit = raycaster.intersectObjects(clickable, false)[0];
      if (hit?.object.userData.packetId) {
        onSelectRef.current(hit.object.userData.packetId);
      }
    }
    renderer.domElement.addEventListener("pointerdown", handlePointerDown);

    function resize() {
      const width = Math.max(1, host.clientWidth);
      const height = Math.max(1, host.clientHeight);
      const aspect = width / height;
      camera.left = -4.5 * Math.max(1, aspect);
      camera.right = 4.5 * Math.max(1, aspect);
      camera.top = 3.2;
      camera.bottom = -3.2;
      camera.updateProjectionMatrix();
      renderer.setSize(width, height, false);
    }
    const observer = new ResizeObserver(resize);
    observer.observe(host);
    resize();

    let frame = 0;
    const startedAt = performance.now();
    function animate() {
      const t = (performance.now() - startedAt) / 1000;
      particles.forEach((item) => {
        const progress = reduceMotion || !playing ? item.offset : (t * 0.22 + item.offset) % 1;
        item.mesh.position.lerpVectors(item.start, item.end, progress);
        item.mesh.position.y = 0.32 + Math.sin(progress * Math.PI) * 0.2;
      });
      scene.rotation.y = reduceMotion ? 0 : Math.sin(t * 0.18) * 0.04;
      renderer.render(scene, camera);
      frame = requestAnimationFrame(animate);
    }
    animate();

    return () => {
      cancelAnimationFrame(frame);
      observer.disconnect();
      renderer.domElement.removeEventListener("pointerdown", handlePointerDown);
      renderer.dispose();
      host.removeChild(renderer.domElement);
      scene.traverse((object) => {
        const mesh = object as THREE.Mesh;
        mesh.geometry?.dispose?.();
        const material = mesh.material as THREE.Material | THREE.Material[] | undefined;
        if (Array.isArray(material)) {
          material.forEach((item) => item.dispose());
        } else {
          material?.dispose?.();
        }
      });
    };
  }, [graph, selectedId, playing]);

  return (
    <div className="packet-flow-card">
      <div className="packet-flow-canvas" ref={mountRef} />
      <div className="packet-flow-legend">
        {Object.entries(protocolColor).map(([protocol, color]) => (
          <span key={protocol}>
            <i style={{ background: color }} />
            {protocol}
          </span>
        ))}
      </div>
    </div>
  );
}

function buildGraph(packets: PacketRecord[]) {
  // 按主机（去掉端口）聚合，统计每个主机的总流量，只保留 top-N
  const hostBytes = new Map<string, number>();
  const bumpHost = (host: string, bytes: number) => hostBytes.set(host, (hostBytes.get(host) ?? 0) + bytes);
  packets.forEach((packet) => {
    bumpHost(host(packet.source), packet.length);
    bumpHost(host(packet.destination), packet.length);
  });
  const topHosts = new Set(
    [...hostBytes.entries()].sort((a, b) => b[1] - a[1]).slice(0, MAX_NODES).map(([h]) => h)
  );

  const nodes = new Map<string, { id: string; label: string; kind: "client" | "service" | "agent" | "plugin" }>();
  const edges = new Map<
    string,
    { id: string; source: string; destination: string; protocol: string; packetIds: number[]; bytes: number }
  >();

  packets.forEach((packet) => {
    const src = host(packet.source);
    const dst = host(packet.destination);
    if (!topHosts.has(src) || !topHosts.has(dst) || src === dst) return;
    [src, dst].forEach((h) => {
      if (!nodes.has(h)) nodes.set(h, { id: h, label: shortLabel(h), kind: nodeKind(h) });
    });
    const edgeId = `${src}->${dst}:${packet.protocol}`;
    const edge =
      edges.get(edgeId) ?? { id: edgeId, source: src, destination: dst, protocol: packet.protocol, packetIds: [], bytes: 0 };
    if (edge.packetIds.length < 200) edge.packetIds.push(packet.id);
    edge.bytes += packet.length;
    edges.set(edgeId, edge);
  });

  return { nodes: [...nodes.values()], edges: [...edges.values()] };
}

function host(value: string): string {
  const idx = value.lastIndexOf(":");
  return idx > 0 ? value.slice(0, idx) : value;
}

function shortLabel(value: string): string {
  return value.length > 18 ? `${value.slice(0, 16)}…` : value;
}

function nodeKind(value: string) {
  if (value.includes("plugin")) return "plugin";
  if (value.includes("pm") || value.includes("192.168")) return "agent";
  if (value.includes("local") || value.match(/\d+\.\d+\.\d+\.\d+/)) return "service";
  return "client";
}

function makeEdgeTube(start: THREE.Vector3, end: THREE.Vector3, color: string, selected: boolean) {
  const direction = new THREE.Vector3().subVectors(end, start);
  const length = direction.length();
  const geometry = new THREE.CylinderGeometry(selected ? 0.035 : 0.022, selected ? 0.035 : 0.022, length, 12);
  const material = new THREE.MeshStandardMaterial({
    color,
    transparent: true,
    opacity: selected ? 0.92 : 0.55,
    emissive: new THREE.Color(color),
    emissiveIntensity: selected ? 0.32 : 0.08,
    roughness: 0.38,
  });
  const tube = new THREE.Mesh(geometry, material);
  const mid = new THREE.Vector3().addVectors(start, end).multiplyScalar(0.5);
  tube.position.copy(mid);
  tube.quaternion.setFromUnitVectors(new THREE.Vector3(0, 1, 0), direction.normalize());
  return tube;
}
