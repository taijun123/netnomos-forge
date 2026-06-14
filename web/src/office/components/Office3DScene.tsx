import { useEffect, useMemo, useRef, useState, type CSSProperties } from "react";
import * as THREE from "three";
import { OrbitControls } from "three/examples/jsm/controls/OrbitControls.js";
import type { Agent, AgentId, AgentSeat, AgentPose, CourierWaypoint, FurnitureItem } from "../types/domain";
import { agentSeats3d, courierWaypoints3d, doorways3d, furniture3d, rooms3d } from "../data/office3dData";
import { createCatAgentRig, updateCatAgentRig, type CatActivity, type CatAgentRig } from "./CatAgentRig";

// —— 趣味活动轮换状态机 —— 每个 agent 在自己的活动列表里随时间错相轮换，切段头部 10% 做交叉淡入
const ACTIVITY_PLANS: Record<string, CatActivity[]> = {
  supervisor: ["supervising", "talking", "checkPhone", "reviewing", "coffee"],
  analyst: ["typing", "checkPhone", "talking", "stretch", "coffee"],
  validator: ["typing", "reviewing", "checkPhone", "stretch", "talking"],
  plugin: ["typing", "talking", "checkPhone", "coffee", "stretch"],
  pm: ["reviewing", "talking", "checkPhone", "coffee"],
};
// 段长缩短（~5s）让动作切换更频繁、画面更热闹；互质避免所有猫同步
const ACTIVITY_SEG = [4.6, 5.2, 4.8, 5.4, 5.0, 4.4];
const ACTIVITY_ORDER = ["supervisor", "courier", "analyst", "validator", "plugin", "pm"];
const acSmooth = (x: number) => (x <= 0 ? 0 : x >= 1 ? 1 : x * x * (3 - 2 * x));

function getAgentActivity(agentId: string, t: number): { from: CatActivity; to: CatActivity; blend: number } {
  const list = ACTIVITY_PLANS[agentId] ?? ["idleBreathe"];
  const idx = Math.max(0, ACTIVITY_ORDER.indexOf(agentId));
  const seg = ACTIVITY_SEG[idx % ACTIVITY_SEG.length];
  const u = (t + idx * 2.3) / seg;
  const i = ((Math.floor(u) % list.length) + list.length) % list.length;
  const local = u - Math.floor(u);
  if (local < 0.1) {
    const prev = (i - 1 + list.length) % list.length;
    return { from: list[prev], to: list[i], blend: acSmooth(local / 0.1) };
  }
  return { from: list[i], to: list[i], blend: 0 };
}

// ============== 休息区漫游：去跑步机/沙发、相遇交谈 ==============
type RoamKind = "treadmill" | "sofa" | "chat";
interface RoamEvent {
  start: number;
  outDur: number;
  dwell: number;
  kind: RoamKind;
}

const ROAM_CYCLE = 92; // 漫游主周期（秒），各猫事件在周期内错峰，避免冲突
const ROAM_EVENTS: Record<string, RoamEvent[]> = {
  plugin: [
    { start: 5, outDur: 4.5, dwell: 9, kind: "treadmill" },
    { start: 60, outDur: 5, dwell: 13, kind: "chat" },
  ],
  pm: [
    { start: 24, outDur: 5, dwell: 11, kind: "sofa" },
    { start: 60, outDur: 5, dwell: 13, kind: "chat" },
  ],
  analyst: [{ start: 42, outDur: 6.5, dwell: 9, kind: "treadmill" }],
};

// 目的地落点 + 朝向（rotation.y；猫前方为 -Z）
const ROAM_DEST: Record<string, Partial<Record<RoamKind, { x: number; z: number; facing: number }>>> = {
  plugin: { treadmill: { x: 5.5, z: 2.15, facing: 0 }, chat: { x: 5.7, z: 0.85, facing: 0 } },
  pm: { sofa: { x: 5.75, z: -2.35, facing: Math.PI }, chat: { x: 5.35, z: -0.15, facing: Math.PI } },
  analyst: { treadmill: { x: 5.5, z: 2.15, facing: 0 } },
};

// 工位 → 休息区入口 的前段路径（穿门，避免穿墙）
const ROAM_LEAD: Record<string, Array<{ x: number; z: number }>> = {
  plugin: [{ x: 1.5, z: 1.44 }, { x: 3.8, z: 1.05 }, { x: 4.2, z: 0.9 }, { x: 5.0, z: 0.9 }],
  pm: [{ x: 3.15, z: 1.44 }, { x: 4.0, z: 1.0 }, { x: 4.2, z: 0.9 }, { x: 5.0, z: 0.9 }],
  analyst: [
    { x: -2.7, z: 1.46 },
    { x: -0.2, z: 1.5 },
    { x: 0.4, z: 1.6 },
    { x: 2.5, z: 1.05 },
    { x: 4.2, z: 0.9 },
    { x: 5.0, z: 0.9 },
  ],
};

function roamTail(kind: RoamKind, dest: { x: number; z: number }): Array<{ x: number; z: number }> {
  if (kind === "treadmill") return [{ x: 5.3, z: 1.5 }, { x: dest.x, z: dest.z }];
  if (kind === "sofa") return [{ x: 5.6, z: -0.6 }, { x: 5.7, z: -1.7 }, { x: dest.x, z: dest.z }];
  return [{ x: dest.x, z: dest.z }];
}

function buildRoamPath(agentId: string, kind: RoamKind): Array<{ x: number; z: number }> {
  const lead = ROAM_LEAD[agentId] ?? [];
  const d = ROAM_DEST[agentId]?.[kind];
  return d ? [...lead, ...roamTail(kind, d)] : lead;
}

const segRot = (a: { x: number; z: number }, b: { x: number; z: number }) =>
  Math.atan2(-(b.x - a.x), -(b.z - a.z));

function samplePathPos(wp: Array<{ x: number; z: number }>, f: number) {
  if (wp.length < 2) return { x: wp[0].x, z: wp[0].z, rotY: 0 };
  const cf = Math.max(0, Math.min(1, f));
  const s = cf * (wp.length - 1);
  const i = Math.min(wp.length - 2, Math.floor(s));
  const local = s - i;
  const a = wp[i];
  const b = wp[i + 1];
  return { x: a.x + (b.x - a.x) * local, z: a.z + (b.z - a.z) * local, rotY: segRot(a, b) };
}

interface RoamState {
  pos: { x: number; z: number };
  rotY: number;
  kind: RoamKind;
  walking: boolean;
}

function getRoam(agentId: string, t: number): RoamState | null {
  const events = ROAM_EVENTS[agentId];
  if (!events) return null;
  const u = ((t % ROAM_CYCLE) + ROAM_CYCLE) % ROAM_CYCLE;
  for (const ev of events) {
    const local = u - ev.start;
    const tripDur = ev.outDur * 2 + ev.dwell;
    if (local < 0 || local >= tripDur) continue;
    const path = buildRoamPath(agentId, ev.kind);
    const dest = ROAM_DEST[agentId]?.[ev.kind];
    if (local < ev.outDur) {
      const p = samplePathPos(path, local / ev.outDur);
      return { pos: { x: p.x, z: p.z }, rotY: p.rotY, kind: ev.kind, walking: true };
    }
    if (dest && local < ev.outDur + ev.dwell) {
      return { pos: { x: dest.x, z: dest.z }, rotY: dest.facing, kind: ev.kind, walking: false };
    }
    const p = samplePathPos([...path].reverse(), (local - ev.outDur - ev.dwell) / ev.outDur);
    return { pos: { x: p.x, z: p.z }, rotY: p.rotY, kind: ev.kind, walking: true };
  }
  return null;
}

// 语音气泡里的「乱码」，每 ~1.3s 变一次表示在持续交流
const GARBLE = ["#@%!", "?!#…", "@¥%&", "…#@?", "%&#@", "!?@#", "#…%!", "@#?！"];
const garbleFor = (id: string, t: number) => GARBLE[(Math.floor(t / 1.3) + id.length) % GARBLE.length];

interface Office3DSceneProps {
  agents: Agent[];
  rulesLoaded: boolean;
  dataLoaded: boolean;
  onAgentDoubleClick: (agentId: AgentId) => void;
}

interface AgentLabel {
  id: AgentId;
  left: number;
  top: number;
  agent: Agent;
  active: boolean;
}

// 建筑外壳边界（与 office3dData 中房间坐标一致）
const SHELL = { minX: -4.6, maxX: 7.0, minZ: -3.9, maxZ: 3.9 };
// 半俯视取景下压低墙体，减少遮挡、让房间更通透
const OUTER_WALL = { thickness: 0.22, height: 0.46 };
const INNER_WALL = { thickness: 0.11, height: 0.34 };

export function Office3DScene({
  agents,
  rulesLoaded,
  dataLoaded,
  onAgentDoubleClick,
}: Office3DSceneProps) {
  const mountRef = useRef<HTMLDivElement | null>(null);
  const [hoverLabel, setHoverLabel] = useState<AgentLabel | null>(null);
  const [bubbles, setBubbles] = useState<Array<{ id: string; left: number; top: number; text: string }>>([]);
  const controlsRef = useRef<OrbitControls | null>(null);
  const dblClickRef = useRef(onAgentDoubleClick);
  dblClickRef.current = onAgentDoubleClick;
  const agentsById = useMemo(() => new Map(agents.map((agent) => [agent.id, agent])), [agents]);

  useEffect(() => {
    const mount = mountRef.current;
    if (!mount) return;
    const host = mount;

    const reduceMotion = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
    const scene = new THREE.Scene();
    scene.background = null; // 背景交给 CSS 渐变，营造「模型浮于干净留白」的高级感

    // 半俯视正交相机（~50°）：左右对称（x=0），能看清猫坐姿与耳朵剪影，户型仍可读
    const camera = new THREE.OrthographicCamera(-8, 8, 5, -5, 0.1, 100);
    camera.position.set(0, 10.5, 8.2);
    camera.lookAt(0, 0, -0.8);

    const renderer = new THREE.WebGLRenderer({ antialias: true, alpha: true });
    renderer.setClearColor(0x000000, 0);
    renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2));
    renderer.outputColorSpace = THREE.SRGBColorSpace;
    renderer.toneMapping = THREE.ACESFilmicToneMapping;
    renderer.toneMappingExposure = 1.12;
    renderer.shadowMap.enabled = true;
    renderer.shadowMap.type = THREE.PCFSoftShadowMap;
    host.appendChild(renderer.domElement);

    // 3D 视角控制：左键拖动旋转、滚轮缩放、右键平移
    const controls = new OrbitControls(camera, renderer.domElement);
    controls.enableDamping = true;
    controls.dampingFactor = 0.08;
    controls.target.set(0, 0, -0.8);
    controls.minZoom = 0.55;
    controls.maxZoom = 3.5;
    controls.maxPolarAngle = Math.PI * 0.47; // 不允许转到地面以下
    controls.update();
    controls.saveState();
    controlsRef.current = controls;

    const hemi = new THREE.HemisphereLight(0xffffff, 0xc9d2dc, 1.05);
    const sun = new THREE.DirectionalLight(0xfff6e8, 2.1);
    sun.position.set(-5, 11, 7);
    sun.castShadow = true;
    sun.shadow.mapSize.set(2048, 2048);
    sun.shadow.camera.left = -9.5;
    sun.shadow.camera.right = 9.5;
    sun.shadow.camera.top = 7;
    sun.shadow.camera.bottom = -7;
    sun.shadow.bias = -0.0004;
    sun.shadow.radius = 3;
    const fill = new THREE.DirectionalLight(0xdcebff, 0.5);
    fill.position.set(7, 8, -5);
    // 轮廓光：从高处背后（-Z）斜射，勾出猫的头/耳/背边缘，把暗色毛发从椅背分离出来
    const rim = new THREE.DirectionalLight(0xbfd6ff, 1.35);
    rim.position.set(-2.5, 7.5, -9);
    scene.add(hemi, sun, fill, rim);

    const tex = createTextureKit();

    scene.add(createGround());
    scene.add(createBuildingSlab());
    rooms3d.forEach((room) => scene.add(createRoomFloor(room, tex)));
    createWalls(scene);
    createDoorThresholds(scene);
    furniture3d.forEach((item) => scene.add(createFurniture(item, tex)));
    scene.add(createManagerNameplate());
    // 主管办公室门牌：挂在门左侧的实墙上（门洞在 x∈[-1.85,-0.95]，牌移到 x=-2.3 不压门洞）
    scene.add(createDoorSign("主管办公室", -2.3, -1.2));

    const routeLine = createCourierRouteLine();
    scene.add(routeLine);
    const routePackages = createRoutePackages();
    scene.add(routePackages);

    const timeline = buildCourierTimeline(courierWaypoints3d);

    const rigs = new Map<AgentId, { rig: CatAgentRig; seat: AgentSeat; agent: Agent }>();
    const hitProxies: THREE.Mesh[] = [];
    agentSeats3d.forEach((seat) => {
      const agent = agentsById.get(seat.agentId);
      if (!agent) return;
      const pose = getAgentPose(agent, seat, dataLoaded);
      const rig = createCatAgentRig(agent, pose);
      rig.root.position.set(seat.position.x, 0, seat.position.z);
      rig.root.rotation.y = seat.rotation;
      rig.root.scale.setScalar(agent.id === "supervisor" ? 1.12 : agent.id === "courier" ? 1.02 : 1.02);
      // 透明命中体：鼠标悬浮/双击的拾取目标，比逐网格拾取稳定
      const proxy = new THREE.Mesh(
        new THREE.CylinderGeometry(0.66, 0.66, 1.5, 12),
        new THREE.MeshBasicMaterial({ transparent: true, opacity: 0, depthWrite: false })
      );
      proxy.position.y = 0.45;
      proxy.userData.agentId = agent.id;
      rig.root.add(proxy);
      hitProxies.push(proxy);
      scene.add(rig.root);
      rigs.set(agent.id, { rig, seat, agent });
    });

    const scanRings = createSupervisorScan();
    scene.add(scanRings);

    // 悬浮高亮圈
    const hoverRing = new THREE.Mesh(
      new THREE.RingGeometry(0.5, 0.56, 48),
      new THREE.MeshBasicMaterial({ color: "#1677ff", transparent: true, opacity: 0.5, side: THREE.DoubleSide })
    );
    hoverRing.rotation.x = -Math.PI / 2;
    hoverRing.position.y = 0.03;
    hoverRing.visible = false;
    scene.add(hoverRing);

    // 射线拾取：悬浮提示 + 双击交互
    const raycaster = new THREE.Raycaster();
    const pointer = new THREE.Vector2();
    let pointerInside = false;
    let hoveredId: AgentId | null = null;
    const onPointerMove = (event: PointerEvent) => {
      const rect = renderer.domElement.getBoundingClientRect();
      pointer.x = ((event.clientX - rect.left) / rect.width) * 2 - 1;
      pointer.y = -((event.clientY - rect.top) / rect.height) * 2 + 1;
      pointerInside = true;
    };
    const onPointerLeave = () => {
      pointerInside = false;
    };
    const onDoubleClick = () => {
      if (hoveredId) dblClickRef.current(hoveredId);
    };
    renderer.domElement.addEventListener("pointermove", onPointerMove);
    renderer.domElement.addEventListener("pointerleave", onPointerLeave);
    renderer.domElement.addEventListener("dblclick", onDoubleClick);

    // 调试/自动化钩子：返回角色当前的屏幕坐标（视口坐标系）
    (window as unknown as Record<string, unknown>).__officeAgentScreenPos = (id: AgentId) => {
      const entry = rigs.get(id);
      if (!entry) return null;
      const rect = renderer.domElement.getBoundingClientRect();
      const projected = projectToScreen(
        { x: entry.rig.root.position.x, y: 0.35, z: entry.rig.root.position.z },
        camera,
        renderer.domElement
      );
      return { x: rect.left + projected.left, y: rect.top + projected.top };
    };

    function resize() {
      const width = Math.max(1, host.clientWidth);
      const height = Math.max(1, host.clientHeight);
      const aspect = width / height;
      // 同时保证「整栋楼宽度」与「半俯视投影高度」都框得下（含最左走廊的快递B），
      // 取两者较大值，避免窄/方视口裁掉边缘角色。
      const TARGET_W = 12.4; // 拉近：快递B(-5.8) 仍可见，右侧休息区边缘略裁，换取猫更大更易看清动作
      const TARGET_H = 8.6; // 半俯视下建筑投影高 + 余量
      const viewHeight = Math.max(TARGET_H, TARGET_W / aspect);
      camera.top = viewHeight / 2;
      camera.bottom = -viewHeight / 2;
      camera.left = (-viewHeight * aspect) / 2;
      camera.right = (viewHeight * aspect) / 2;
      camera.updateProjectionMatrix();
      renderer.setSize(width, height, false);
    }

    const observer = new ResizeObserver(resize);
    observer.observe(host);
    resize();

    let frame = 0;
    const startedAt = performance.now();
    let lastLabelUpdate = 0;

    const animate = () => {
      const t = (performance.now() - startedAt) / 1000;
      controls.update();
      routeLine.visible = dataLoaded;
      routePackages.visible = dataLoaded && !reduceMotion;
      scanRings.visible = rulesLoaded && !reduceMotion;
      scanRings.children.forEach((ring, index) => {
        ring.scale.setScalar(1 + Math.sin(t * 1.8 + index) * 0.12);
        const material = (ring as THREE.Mesh).material as THREE.MeshBasicMaterial;
        material.opacity = 0.1 + Math.abs(Math.sin(t * 1.4 + index)) * 0.16;
      });

      const talkers: Array<{ x: number; z: number }> = [];
      rigs.forEach(({ rig, seat, agent }) => {
        const active = isAgentActive(agent, rulesLoaded, dataLoaded);
        const pose = getAgentPose(agent, seat, dataLoaded);
        if (agent.id === "courier" && dataLoaded) {
          const courier = sampleCourier(timeline, t);
          rig.root.position.set(courier.position.x, 0, courier.position.z);
          rig.root.rotation.y = courier.rotation;
          if (courier.moving) {
            updateCatAgentRig(rig, agent, "walking", t, active, reduceMotion);
          } else {
            // 门口停留时拍箱打包
            updateCatAgentRig(rig, agent, "carryingParcel", t, active, reduceMotion, "packing", "packing", 0);
          }
          return;
        }
        const roam = getRoam(agent.id, t);
        if (roam) {
          // 离开工位漫游：去跑步机/沙发/相遇交谈
          rig.root.position.set(roam.pos.x, 0, roam.pos.z);
          rig.root.rotation.y = roam.rotY;
          if (roam.walking || roam.kind === "treadmill") {
            updateCatAgentRig(rig, agent, "walking", t, active, reduceMotion); // 行走 / 跑步机原地跑
          } else if (roam.kind === "sofa") {
            updateCatAgentRig(rig, agent, "seatedTyping", t, active, reduceMotion, "sofaRest", "sofaRest", 0);
          } else {
            updateCatAgentRig(rig, agent, "seatedTyping", t, active, reduceMotion, "talking", "talking", 0);
            talkers.push({ x: roam.pos.x, z: roam.pos.z });
          }
          rig.chair.visible = false; // 不在工位，不显示办公椅
        } else {
          rig.root.position.set(seat.position.x, 0, seat.position.z);
          rig.root.rotation.y = seat.rotation;
          const act = getAgentActivity(agent.id, t);
          updateCatAgentRig(rig, agent, pose, t, active, reduceMotion, act.from, act.to, act.blend);
          if (act.from === "talking" || act.to === "talking") talkers.push({ x: seat.position.x, z: seat.position.z });
        }
      });

      if (dataLoaded && !reduceMotion) {
        routePackages.children.forEach((child, index) => {
          const courier = sampleCourier(timeline, t + index * timeline.total * 0.45);
          child.position.set(courier.position.x, 0.15, courier.position.z);
          child.rotation.y = courier.rotation;
        });
      }

      renderer.render(scene, camera);
      if (t - lastLabelUpdate > 0.08) {
        lastLabelUpdate = t;
        // 交谈语音气泡：在 talking / 相遇的猫头顶弹 ##@%# 乱码
        setBubbles(
          talkers.map((tk, i) => {
            const p = projectToScreen({ x: tk.x, y: 1.3, z: tk.z }, camera, renderer.domElement);
            return { id: `talk-${i}`, left: p.left, top: p.top, text: garbleFor(`b${i}`, t) };
          })
        );
        // 悬浮拾取
        if (pointerInside) {
          raycaster.setFromCamera(pointer, camera);
          const hits = raycaster.intersectObjects(hitProxies, false);
          hoveredId = hits.length ? ((hits[0].object.userData.agentId as AgentId) ?? null) : null;
        } else {
          hoveredId = null;
        }
        renderer.domElement.style.cursor = hoveredId ? "pointer" : "grab";

        const entry = hoveredId ? rigs.get(hoveredId) : undefined;
        if (entry) {
          const base = entry.rig.root.position;
          hoverRing.visible = true;
          hoverRing.position.set(base.x, 0.03, base.z);
          const ringMat = hoverRing.material as THREE.MeshBasicMaterial;
          ringMat.color.set(entry.agent.color);
          const projected = projectToScreen({ x: base.x, y: 1.05, z: base.z }, camera, renderer.domElement);
          setHoverLabel({
            id: entry.agent.id,
            left: projected.left,
            top: projected.top,
            agent: entry.agent,
            active: isAgentActive(entry.agent, rulesLoaded, dataLoaded),
          });
        } else {
          hoverRing.visible = false;
          setHoverLabel(null);
        }
      }
      frame = requestAnimationFrame(animate);
    };
    animate();

    return () => {
      cancelAnimationFrame(frame);
      observer.disconnect();
      renderer.domElement.removeEventListener("pointermove", onPointerMove);
      renderer.domElement.removeEventListener("pointerleave", onPointerLeave);
      renderer.domElement.removeEventListener("dblclick", onDoubleClick);
      controls.dispose();
      controlsRef.current = null;
      delete (window as unknown as Record<string, unknown>).__officeAgentScreenPos;
      renderer.dispose();
      // dispose() 不会释放底层 WebGL 上下文；HMR/重挂时必须强制丢弃，
      // 否则上下文累积到上限会导致 GPU 合成异常（截图卡死、画面变黑）。
      renderer.forceContextLoss();
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
      tex.dispose();
    };
  }, [agentsById, dataLoaded, rulesLoaded]);

  return (
    <section className="office-3d-stage" aria-label="3D 俯视多智能体办公室">
      <div className="office-3d-canvas" ref={mountRef} />
      <div className="office-3d-label-layer" aria-hidden={false}>
        {hoverLabel && (
          <div
            className={`office-agent-tip ${hoverLabel.active ? "is-active" : ""}`}
            style={{
              left: `${hoverLabel.left}px`,
              top: `${hoverLabel.top}px`,
              "--agent-color": hoverLabel.agent.color,
            } as CSSProperties}
          >
            <span className="office-agent-card">
              <i aria-hidden="true" />
              <strong>{hoverLabel.agent.name}</strong>
              <small>{hoverLabel.agent.role}</small>
            </span>
            <em className="office-agent-tip-action">双击交互</em>
          </div>
        )}
        {bubbles.map((b) => (
          <div
            key={b.id}
            className="office-speech-bubble"
            style={{ left: `${b.left}px`, top: `${b.top}px` }}
          >
            {b.text}
          </div>
        ))}
      </div>
      <button type="button" className="office-3d-reset" onClick={() => controlsRef.current?.reset()}>
        复位视角
      </button>
      <div className="office-3d-hint">左键拖动旋转 · 滚轮缩放 · 右键平移 · 悬浮角色查看 · 双击交互</div>
      <button
        type="button"
        className={`office-3d-status-card office-3d-status-card--rules ${rulesLoaded ? "is-done" : "is-pending"}`}
        onClick={() => dblClickRef.current("supervisor")}
      >
        <b>主管办公室</b>
        <span>{rulesLoaded ? "规则扫描线已开启 · 点击重新接入" : "点击接入预设规则集"}</span>
        {!rulesLoaded && <em className="office-3d-status-cta">点击上传 ›</em>}
      </button>
      <button
        type="button"
        className={`office-3d-status-card office-3d-status-card--data ${dataLoaded ? "is-done" : "is-pending"}`}
        onClick={() => dblClickRef.current("courier")}
      >
        <b>门外收发区</b>
        <span>{dataLoaded ? "快递B 往返交接数据 · 点击进抓包台" : "点击上传 pcap/csv 数据目录"}</span>
        {!dataLoaded && <em className="office-3d-status-cta">点击上传 ›</em>}
      </button>
    </section>
  );
}

/* ============================== 材质 ============================== */

interface TextureKit {
  floorWood: (w: number, d: number) => THREE.MeshStandardMaterial;
  floorTile: (w: number, d: number) => THREE.MeshStandardMaterial;
  woodTop: () => THREE.MeshStandardMaterial;
  dispose: () => void;
}

function createTextureKit(): TextureKit {
  const loader = new THREE.TextureLoader();
  const owned: Array<THREE.Texture | THREE.Material> = [];

  const load = (path: string, srgb: boolean) => {
    const texture = loader.load(path);
    if (srgb) texture.colorSpace = THREE.SRGBColorSpace;
    texture.wrapS = THREE.RepeatWrapping;
    texture.wrapT = THREE.RepeatWrapping;
    texture.anisotropy = 8;
    owned.push(texture);
    return texture;
  };

  const woodDiff = load("/assets/textures/wood_diff.jpg", true);
  const woodNor = load("/assets/textures/wood_nor.jpg", false);
  const woodRough = load("/assets/textures/wood_rough.jpg", false);
  const tileDiff = load("/assets/textures/tile_diff.jpg", true);
  const tileNor = load("/assets/textures/tile_nor.jpg", false);
  const tileRough = load("/assets/textures/tile_rough.jpg", false);

  const repeated = (base: THREE.Texture, rx: number, ry: number) => {
    const texture = base.clone();
    texture.repeat.set(rx, ry);
    texture.needsUpdate = true;
    owned.push(texture);
    return texture;
  };

  const make = (options: THREE.MeshStandardMaterialParameters) => {
    const material = new THREE.MeshStandardMaterial(options);
    owned.push(material);
    return material;
  };

  return {
    floorWood: (w, d) =>
      make({
        map: repeated(woodDiff, w * 0.42, d * 0.42),
        normalMap: repeated(woodNor, w * 0.42, d * 0.42),
        roughnessMap: repeated(woodRough, w * 0.42, d * 0.42),
        normalScale: new THREE.Vector2(0.55, 0.55),
        roughness: 1,
        metalness: 0.02,
      }),
    floorTile: (w, d) =>
      make({
        map: repeated(tileDiff, w * 0.5, d * 0.5),
        normalMap: repeated(tileNor, w * 0.5, d * 0.5),
        roughnessMap: repeated(tileRough, w * 0.5, d * 0.5),
        normalScale: new THREE.Vector2(0.4, 0.4),
        roughness: 1,
        metalness: 0.02,
      }),
    woodTop: () =>
      make({
        map: repeated(woodDiff, 0.7, 0.5),
        roughness: 0.6,
        metalness: 0.04,
      }),
    dispose: () => owned.forEach((item) => item.dispose()),
  };
}

/* ============================== 建筑 ============================== */

function createGround() {
  const group = new THREE.Group();
  // 干净的浅色「展台」：仅略大于建筑，四周交给 CSS 渐变背景，模型像漂浮在留白上
  const platform = new THREE.Mesh(
    new THREE.PlaneGeometry(16.2, 9.4),
    new THREE.MeshStandardMaterial({ color: "#eef2f7", roughness: 0.96 })
  );
  platform.rotation.x = -Math.PI / 2;
  platform.position.set(0.05, -0.03, 0);
  platform.receiveShadow = true;
  group.add(platform);
  // 建筑下方的柔和接地阴影（径向渐变贴图），增强漂浮立体感
  const shadowTex = makeRadialShadowTexture();
  const contact = new THREE.Mesh(
    new THREE.PlaneGeometry(15.6, 9.2),
    new THREE.MeshBasicMaterial({ map: shadowTex, transparent: true, opacity: 0.5, depthWrite: false })
  );
  contact.rotation.x = -Math.PI / 2;
  contact.position.set(0.2, -0.02, 0.35);
  group.add(contact);
  return group;
}

function makeRadialShadowTexture() {
  const size = 256;
  const canvas = document.createElement("canvas");
  canvas.width = canvas.height = size;
  const ctx = canvas.getContext("2d")!;
  const g = ctx.createRadialGradient(size / 2, size / 2, size * 0.1, size / 2, size / 2, size * 0.5);
  g.addColorStop(0, "rgba(40,52,74,0.45)");
  g.addColorStop(0.6, "rgba(40,52,74,0.18)");
  g.addColorStop(1, "rgba(40,52,74,0)");
  ctx.fillStyle = g;
  ctx.fillRect(0, 0, size, size);
  const tex = new THREE.CanvasTexture(canvas);
  tex.colorSpace = THREE.SRGBColorSpace;
  return tex;
}

function createBuildingSlab() {
  const width = SHELL.maxX - SHELL.minX + 0.7;
  const depth = SHELL.maxZ - SHELL.minZ + 0.7;
  const slab = new THREE.Mesh(
    new THREE.BoxGeometry(width, 0.1, depth),
    new THREE.MeshStandardMaterial({ color: "#f3f5f7", roughness: 0.85 })
  );
  slab.position.set((SHELL.minX + SHELL.maxX) / 2, -0.052, (SHELL.minZ + SHELL.maxZ) / 2);
  slab.receiveShadow = true;
  return slab;
}

function createRoomFloor(room: (typeof rooms3d)[number], tex: TextureKit) {
  const material =
    room.floor === "tile"
      ? tex.floorTile(room.size.width, room.size.depth)
      : tex.floorWood(room.size.width, room.size.depth);
  const floor = new THREE.Mesh(new THREE.PlaneGeometry(room.size.width, room.size.depth), material);
  floor.rotation.x = -Math.PI / 2;
  floor.position.set(room.center.x, 0.002, room.center.z);
  floor.receiveShadow = true;
  floor.userData.roomId = room.id;
  return floor;
}

interface WallSpec {
  axis: "x" | "z"; // 墙体延伸方向
  fixed: number; // 垂直方向上的固定坐标
  from: number;
  to: number;
  outer: boolean;
  gaps: Array<{ center: number; size: number }>;
}

function collectWalls(): WallSpec[] {
  const gapsAt = (axis: "x" | "z", fixed: number) =>
    doorways3d
      .filter((door) => (axis === "x" ? Math.abs(door.position.z - fixed) < 0.05 : Math.abs(door.position.x - fixed) < 0.05))
      .map((door) => ({ center: axis === "x" ? door.position.x : door.position.z, size: door.width }));

  return [
    // 外壳四面
    { axis: "z", fixed: SHELL.minX, from: SHELL.minZ, to: SHELL.maxZ, outer: true, gaps: gapsAt("z", SHELL.minX) },
    { axis: "z", fixed: SHELL.maxX, from: SHELL.minZ, to: SHELL.maxZ, outer: true, gaps: [] },
    { axis: "x", fixed: SHELL.minZ, from: SHELL.minX, to: SHELL.maxX, outer: true, gaps: [] },
    { axis: "x", fixed: SHELL.maxZ, from: SHELL.minX, to: SHELL.maxX, outer: true, gaps: [] },
    // 内隔断：上排房间与中部的横向隔断（休息区以西）
    { axis: "x", fixed: -1.2, from: SHELL.minX, to: 4.2, outer: false, gaps: gapsAt("x", -1.2) },
    // 主管室 | 验证区
    { axis: "z", fixed: -0.6, from: SHELL.minZ, to: -1.2, outer: false, gaps: [] },
    // 分析区 | 插件间
    { axis: "z", fixed: 0.4, from: -1.2, to: SHELL.maxZ, outer: false, gaps: gapsAt("z", 0.4) },
    // 休息区隔断
    { axis: "z", fixed: 4.2, from: SHELL.minZ, to: SHELL.maxZ, outer: false, gaps: gapsAt("z", 4.2) },
  ];
}

function createWalls(scene: THREE.Scene) {
  const outerMat = new THREE.MeshStandardMaterial({ color: "#fcfdfe", roughness: 0.6 });
  const innerMat = new THREE.MeshStandardMaterial({ color: "#f4f6f9", roughness: 0.62 });

  collectWalls().forEach((wall) => {
    const profile = wall.outer ? OUTER_WALL : INNER_WALL;
    const material = wall.outer ? outerMat : innerMat;
    splitSegments(wall.from, wall.to, wall.gaps).forEach(([start, end]) => {
      const length = end - start + (wall.outer ? profile.thickness : 0);
      const mid = (start + end) / 2;
      const mesh = new THREE.Mesh(
        wall.axis === "x"
          ? new THREE.BoxGeometry(length, profile.height, profile.thickness)
          : new THREE.BoxGeometry(profile.thickness, profile.height, length),
        material
      );
      mesh.position.set(
        wall.axis === "x" ? mid : wall.fixed,
        profile.height / 2,
        wall.axis === "x" ? wall.fixed : mid
      );
      mesh.castShadow = true;
      mesh.receiveShadow = true;
      scene.add(mesh);
    });
  });
}

function createDoorThresholds(scene: THREE.Scene) {
  const thresholdMat = new THREE.MeshStandardMaterial({ color: "#cdd6de", roughness: 0.7 });
  const leafMat = new THREE.MeshStandardMaterial({ color: "#f8fafc", roughness: 0.5 });
  doorways3d.forEach((door) => {
    const vertical = Math.abs(Math.abs(door.rotation) - Math.PI / 2) < 0.01;
    // 门槛条
    const strip = new THREE.Mesh(
      vertical
        ? new THREE.BoxGeometry(0.3, 0.02, door.width)
        : new THREE.BoxGeometry(door.width, 0.02, 0.3),
      thresholdMat
    );
    strip.position.set(door.position.x, 0.012, door.position.z);
    strip.receiveShadow = true;
    // 敞开的门扇：贴在门洞一侧、与墙呈 100° 角
    const leaf = new THREE.Mesh(new THREE.BoxGeometry(door.width * 0.92, 0.4, 0.045), leafMat);
    const hingeOffset = door.width / 2;
    if (vertical) {
      leaf.rotation.y = Math.PI / 2 + 0.62;
      leaf.position.set(door.position.x + 0.18, 0.2, door.position.z - hingeOffset + 0.1);
    } else {
      leaf.rotation.y = -0.62;
      leaf.position.set(door.position.x - hingeOffset + 0.1, 0.2, door.position.z + 0.18);
    }
    leaf.castShadow = true;
    scene.add(strip, leaf);
  });
}

/* ============================== 家具 ============================== */

// 主管办公室桌牌「主管 · MANAGER」，强化领导工位的可分辨度
function createManagerNameplate() {
  const group = new THREE.Group();
  const size = { w: 256, h: 96 };
  const canvas = document.createElement("canvas");
  canvas.width = size.w;
  canvas.height = size.h;
  const ctx = canvas.getContext("2d")!;
  ctx.fillStyle = "#1f2532";
  ctx.fillRect(0, 0, size.w, size.h);
  ctx.fillStyle = "#f1c544";
  ctx.fillRect(0, 0, size.w, 6);
  ctx.fillStyle = "#f4e6c0";
  ctx.textAlign = "center";
  ctx.textBaseline = "middle";
  ctx.font = "bold 40px 'Segoe UI', sans-serif";
  ctx.fillText("主管", size.w / 2, 38);
  ctx.fillStyle = "#c9a14a";
  ctx.font = "600 22px 'Segoe UI', sans-serif";
  ctx.fillText("MANAGER", size.w / 2, 72);
  const tex = new THREE.CanvasTexture(canvas);
  tex.colorSpace = THREE.SRGBColorSpace;
  const plate = new THREE.Mesh(
    new THREE.BoxGeometry(0.34, 0.12, 0.03),
    [
      new THREE.MeshStandardMaterial({ color: "#2a3140", roughness: 0.5 }),
      new THREE.MeshStandardMaterial({ color: "#2a3140", roughness: 0.5 }),
      new THREE.MeshStandardMaterial({ color: "#2a3140", roughness: 0.5 }),
      new THREE.MeshStandardMaterial({ color: "#2a3140", roughness: 0.5 }),
      new THREE.MeshStandardMaterial({ map: tex, roughness: 0.45 }),
      new THREE.MeshStandardMaterial({ color: "#2a3140", roughness: 0.5 }),
    ]
  );
  plate.castShadow = true;
  // 斜置在主管桌前沿（朝向房间 +z），底座小三角支撑
  const base = new THREE.Mesh(
    new THREE.BoxGeometry(0.34, 0.02, 0.1),
    new THREE.MeshStandardMaterial({ color: "#c9a14a", roughness: 0.4, metalness: 0.4 })
  );
  plate.position.set(0, 0.40, 0);
  plate.rotation.x = -0.18;
  base.position.set(0, 0.33, 0.02);
  group.add(plate, base);
  // 完全落在主管桌面内（桌 x∈[-3.65,-1.95]、z∈[-3.33,-2.67]），不超出桌沿
  group.position.set(-2.45, 0, -2.86);
  return group;
}

// 房间门口悬挂的门牌（如「主管办公室」），canvas 贴图小木牌 + 吊杆
function createDoorSign(label: string, x: number, z: number) {
  const group = new THREE.Group();
  const w = 320;
  const h = 110;
  const canvas = document.createElement("canvas");
  canvas.width = w;
  canvas.height = h;
  const ctx = canvas.getContext("2d")!;
  ctx.fillStyle = "#3a4255";
  ctx.fillRect(0, 0, w, h);
  ctx.fillStyle = "#f1c544";
  ctx.fillRect(0, 0, w, 7);
  ctx.fillRect(0, h - 7, w, 7);
  ctx.fillStyle = "#f6efe0";
  ctx.textAlign = "center";
  ctx.textBaseline = "middle";
  ctx.font = "bold 46px 'Segoe UI', 'Microsoft YaHei', sans-serif";
  ctx.fillText(label, w / 2, h / 2 + 2);
  const tex = new THREE.CanvasTexture(canvas);
  tex.colorSpace = THREE.SRGBColorSpace;
  const sideMat = new THREE.MeshStandardMaterial({ color: "#2f3647", roughness: 0.5 });
  const board = new THREE.Mesh(new THREE.BoxGeometry(0.72, 0.2, 0.035), [
    sideMat,
    sideMat,
    sideMat,
    sideMat,
    new THREE.MeshStandardMaterial({ map: tex, roughness: 0.45 }),
    sideMat,
  ]);
  // 贴在 z=-1.2 内墙的 +z 面上（墙厚0.11→外面≈-1.145），略凸出墙面、高度落在墙体内不悬空
  board.position.set(0, 0.23, 0.08);
  board.castShadow = true;
  board.receiveShadow = true;
  // 四角小固定螺栓（贴墙），替代原来悬空的吊杆
  const studMat = new THREE.MeshStandardMaterial({ color: "#9aa3af", roughness: 0.35, metalness: 0.6 });
  [
    [-0.3, 0.07],
    [0.3, 0.07],
    [-0.3, -0.07],
    [0.3, -0.07],
  ].forEach(([dx, dy]) => {
    const stud = new THREE.Mesh(new THREE.CylinderGeometry(0.012, 0.012, 0.05, 10), studMat);
    stud.rotation.x = Math.PI / 2;
    stud.position.set(dx, 0.23 + dy, 0.06);
    group.add(stud);
  });
  group.add(board);
  group.position.set(x, 0, z);
  return group;
}

function createFurniture(item: FurnitureItem, tex: TextureKit) {
  const group = new THREE.Group();
  group.position.set(item.position.x, 0.004, item.position.z);
  group.rotation.y = item.rotation;

  switch (item.kind) {
    case "desk":
      group.add(createDeskModel(item.size.width, item.size.depth, tex));
      break;
    case "meetingTable":
      group.add(createMeetingModel(item.size.width, item.size.depth, tex));
      break;
    case "sofa":
      group.add(createSofaModel(item.size.width, item.size.depth));
      break;
    case "coffee":
      group.add(createCoffeeMachineModel(item.size.width, item.size.depth));
      break;
    case "coffeeTable":
      group.add(createCoffeeTableModel(item.size.width, item.size.depth, tex));
      break;
    case "treadmill":
      group.add(createTreadmillModel(item.size.width, item.size.depth));
      break;
    case "plant":
      group.add(createPlantModel(item.size.width));
      break;
    case "server":
      group.add(createServerRackModel(item.size.width, item.size.depth));
      break;
    case "shelf":
      group.add(createShelfModel(item.size.width, item.size.depth));
      break;
    case "bookshelf":
      group.add(createBookshelfModel(item.size.width, item.size.depth));
      break;
    case "package":
      group.add(createPackageModel(item.size.width, item.size.depth));
      break;
    case "rug":
      group.add(createRugModel(item.size.width, item.size.depth, tex));
      break;
    case "doormat":
      group.add(createDoormatModel(item.size.width, item.size.depth));
      break;
    case "chair":
      break;
  }

  return group;
}

function createDeskModel(width: number, depth: number, tex: TextureKit) {
  const group = new THREE.Group();
  // 桌面 + 四条腿
  const top = new THREE.Mesh(new THREE.BoxGeometry(width, 0.05, depth * 0.74), tex.woodTop());
  top.position.y = 0.3;
  top.castShadow = true;
  top.receiveShadow = true;
  group.add(top);
  const legX = width / 2 - 0.06;
  const legZ = (depth * 0.74) / 2 - 0.05;
  [-1, 1].forEach((sx) =>
    [-1, 1].forEach((sz) => group.add(meshBox(0.06, 0.3, 0.06, "#d8dee5", sx * legX, 0.15, sz * legZ)))
  );
  // 显示器：底座 + 支架 + 屏幕（屏幕面朝座位/相机一侧）
  const standBase = meshBox(0.22, 0.02, 0.14, "#aeb8c2", 0, 0.34, -depth * 0.2);
  const pole = meshBox(0.035, 0.16, 0.035, "#9aa5b0", 0, 0.42, -depth * 0.22);
  const screenBody = meshBox(0.56, 0.34, 0.035, "#22272e", 0, 0.56, -depth * 0.24);
  const screenFace = new THREE.Mesh(
    new THREE.PlaneGeometry(0.5, 0.28),
    new THREE.MeshStandardMaterial({
      color: "#bfe3ff",
      emissive: "#5fb2ff",
      emissiveIntensity: 0.55,
      roughness: 0.3,
    })
  );
  screenFace.position.set(0, 0.56, -depth * 0.24 + 0.02);
  group.add(standBase, pole, screenBody, screenFace);
  // 键盘 + 鼠标 + 杯子
  group.add(meshBox(0.34, 0.022, 0.12, "#2b333b", -0.04, 0.34, depth * 0.08));
  group.add(meshBox(0.07, 0.02, 0.1, "#3a434d", 0.24, 0.34, depth * 0.08));
  group.add(meshCylinder(0.035, 0.06, "#ffffff", -width * 0.34, 0.36, -depth * 0.05));
  return group;
}

function createMeetingModel(width: number, depth: number, tex: TextureKit) {
  const group = new THREE.Group();
  const top = new THREE.Mesh(new THREE.BoxGeometry(width * 0.8, 0.05, depth * 0.58), tex.woodTop());
  top.position.y = 0.28;
  top.castShadow = true;
  group.add(top);
  group.add(meshBox(0.1, 0.28, 0.1, "#d8dee5", -width * 0.3, 0.14, 0));
  group.add(meshBox(0.1, 0.28, 0.1, "#d8dee5", width * 0.3, 0.14, 0));
  group.add(meshCylinder(0.12, 0.035, "#74a85e", 0, 0.32, 0));
  [-0.5, 0, 0.5].forEach((x) => {
    group.add(createSmallChair(x * width * 0.62, -depth * 0.46, 0));
    group.add(createSmallChair(x * width * 0.62, depth * 0.46, Math.PI));
  });
  return group;
}

function createSmallChair(x: number, z: number, rotation: number) {
  const chair = new THREE.Group();
  chair.position.set(x, 0, z);
  chair.rotation.y = rotation;
  chair.add(meshBox(0.3, 0.04, 0.3, "#f2f5f8", 0, 0.16, 0));
  chair.add(meshBox(0.3, 0.22, 0.04, "#e8edf2", 0, 0.3, -0.14));
  chair.add(meshCylinder(0.03, 0.16, "#c3cdd6", 0, 0.08, 0));
  return chair;
}

function createSofaModel(width: number, depth: number) {
  const group = new THREE.Group();
  const fabric = "#8fa3b8";
  const fabricDark = "#7d92a8";
  group.add(meshBox(width, 0.18, depth, fabric, 0, 0.14, 0));
  group.add(meshBox(width, 0.3, 0.16, fabricDark, 0, 0.32, -depth / 2 + 0.08));
  group.add(meshBox(0.16, 0.26, depth, fabricDark, -width / 2 + 0.08, 0.26, 0));
  group.add(meshBox(0.16, 0.26, depth, fabricDark, width / 2 - 0.08, 0.26, 0));
  // 坐垫
  group.add(meshBox(width * 0.42, 0.07, depth * 0.62, "#a3b6c9", -width * 0.22, 0.26, 0.05));
  group.add(meshBox(width * 0.42, 0.07, depth * 0.62, "#a3b6c9", width * 0.22, 0.26, 0.05));
  // 抱枕
  group.add(meshBox(0.2, 0.12, 0.08, "#f0c36e", -width * 0.28, 0.34, -depth * 0.24));
  group.add(meshBox(0.2, 0.12, 0.08, "#ffffff", width * 0.28, 0.34, -depth * 0.24));
  return group;
}

function createCoffeeTableModel(width: number, depth: number, tex: TextureKit) {
  const group = new THREE.Group();
  const top = new THREE.Mesh(new THREE.BoxGeometry(width, 0.04, depth), tex.woodTop());
  top.position.y = 0.2;
  top.castShadow = true;
  group.add(top);
  group.add(meshBox(width * 0.8, 0.03, depth * 0.7, "#e8ecef", 0, 0.09, 0));
  [-1, 1].forEach((sx) =>
    [-1, 1].forEach((sz) => group.add(meshBox(0.04, 0.2, 0.04, "#c8d0d8", sx * (width / 2 - 0.05), 0.1, sz * (depth / 2 - 0.05))))
  );
  group.add(meshCylinder(0.04, 0.05, "#ffffff", -0.12, 0.24, 0));
  group.add(meshCylinder(0.05, 0.02, "#74a85e", 0.16, 0.23, 0.05));
  return group;
}

function createCoffeeMachineModel(width: number, depth: number) {
  const group = new THREE.Group();
  // 操作台
  group.add(meshBox(width, 0.34, depth, "#eef1f4", 0, 0.17, 0));
  group.add(meshBox(width * 1.04, 0.03, depth * 1.04, "#dfe5ea", 0, 0.35, 0));
  // 咖啡机本体
  group.add(meshBox(width * 0.46, 0.26, depth * 0.5, "#2b333b", 0, 0.5, -depth * 0.1));
  group.add(meshBox(width * 0.3, 0.05, depth * 0.3, "#11161b", 0, 0.64, -depth * 0.1));
  group.add(meshCylinder(0.035, 0.05, "#ffffff", 0, 0.39, depth * 0.16));
  group.add(meshCylinder(0.03, 0.04, "#ffffff", width * 0.26, 0.39, depth * 0.1));
  return group;
}

function createTreadmillModel(width: number, depth: number) {
  const group = new THREE.Group();
  group.add(meshBox(width * 0.8, 0.07, depth * 0.85, "#2b3138", 0, 0.06, 0.06));
  group.add(meshBox(width * 0.62, 0.025, depth * 0.66, "#14191e", 0, 0.105, 0.1));
  group.add(meshBox(0.05, 0.34, 0.05, "#aeb8c2", -width * 0.34, 0.24, -depth * 0.34));
  group.add(meshBox(0.05, 0.34, 0.05, "#aeb8c2", width * 0.34, 0.24, -depth * 0.34));
  group.add(meshBox(width * 0.74, 0.05, 0.1, "#e8edf2", 0, 0.43, -depth * 0.38));
  group.add(
    meshBox(width * 0.4, 0.035, 0.06, "#9ed4ff", 0, 0.47, -depth * 0.38, {
      emissive: "#4da9ff",
      emissiveIntensity: 0.3,
    })
  );
  return group;
}

function createPlantModel(size: number) {
  const group = new THREE.Group();
  const pot = new THREE.Mesh(
    new THREE.CylinderGeometry(size * 0.3, size * 0.24, 0.2, 20),
    new THREE.MeshStandardMaterial({ color: "#e9ddcb", roughness: 0.8 })
  );
  pot.position.y = 0.1;
  pot.castShadow = true;
  group.add(pot);
  const leafMat = new THREE.MeshStandardMaterial({ color: "#5f8f43", roughness: 0.8 });
  const leafMatLight = new THREE.MeshStandardMaterial({ color: "#7aa85c", roughness: 0.8 });
  for (let index = 0; index < 14; index += 1) {
    const leaf = new THREE.Mesh(new THREE.SphereGeometry(size * 0.14, 10, 8), index % 2 ? leafMat : leafMatLight);
    const angle = (index / 14) * Math.PI * 2;
    const radius = size * (0.1 + (index % 3) * 0.06);
    leaf.scale.set(1.6, 0.5, 0.7);
    leaf.position.set(Math.cos(angle) * radius, 0.26 + (index % 3) * 0.05, Math.sin(angle) * radius);
    leaf.rotation.y = -angle;
    leaf.castShadow = true;
    group.add(leaf);
  }
  return group;
}

function createServerRackModel(width: number, depth: number) {
  const group = new THREE.Group();
  group.add(meshBox(width, 0.62, depth, "#3a434e", 0, 0.31, 0));
  for (let i = 0; i < 6; i += 1) {
    const y = 0.12 + i * 0.09;
    group.add(meshBox(width * 0.8, 0.02, depth * 0.06, "#14191e", 0, y, depth / 2 + 0.005));
    group.add(
      meshBox(width * 0.06, 0.02, depth * 0.04, i % 2 ? "#4ade80" : "#38bdf8", width * 0.3, y + 0.03, depth / 2 + 0.01, {
        emissive: i % 2 ? "#22c55e" : "#0ea5e9",
        emissiveIntensity: 0.6,
      })
    );
  }
  return group;
}

function createShelfModel(width: number, depth: number) {
  const group = new THREE.Group();
  group.add(meshBox(width, 0.5, depth, "#f4f6f9", 0, 0.25, 0));
  const colors = ["#dbe2e8", "#f0c36e", "#9ec3e8", "#d6a4a4", "#a9c8a2"];
  colors.forEach((color, index) => {
    group.add(meshBox(width * 0.13, 0.18, depth * 0.5, color, -width * 0.36 + index * width * 0.18, 0.42, depth * 0.1));
  });
  group.add(meshBox(width * 0.92, 0.03, depth * 0.9, "#dfe5ea", 0, 0.52, 0));
  return group;
}

function createBookshelfModel(width: number, depth: number) {
  const group = new THREE.Group();
  group.add(meshBox(width, 0.58, depth, "#f4f6f9", 0, 0.29, 0));
  const colors = ["#f0c36e", "#9ec3e8", "#d6a4a4", "#a9c8a2", "#dbe2e8", "#e8b87f"];
  colors.forEach((color, index) => {
    const z = -depth / 2 + 0.16 + index * ((depth - 0.3) / colors.length);
    group.add(meshBox(width * 0.6, 0.16, 0.1, color, width * 0.1, 0.5, z));
  });
  return group;
}

function createPackageModel(width: number, depth: number) {
  const group = new THREE.Group();
  const tapeMat = new THREE.MeshStandardMaterial({ color: "#b98539", roughness: 0.7 });
  const boxMat = new THREE.MeshStandardMaterial({ color: "#d8a653", roughness: 0.75 });
  const boxMatLight = new THREE.MeshStandardMaterial({ color: "#e0b260", roughness: 0.75 });

  const big = new THREE.Mesh(new THREE.BoxGeometry(width * 0.55, 0.3, depth * 0.6), boxMat);
  big.position.set(-width * 0.16, 0.15, 0);
  big.castShadow = true;
  const tape = new THREE.Mesh(new THREE.BoxGeometry(width * 0.55 + 0.01, 0.3, 0.06), tapeMat);
  tape.position.copy(big.position);
  const small = new THREE.Mesh(new THREE.BoxGeometry(width * 0.36, 0.2, depth * 0.4), boxMatLight);
  small.position.set(width * 0.26, 0.1, depth * 0.12);
  small.rotation.y = 0.3;
  small.castShadow = true;
  const top = new THREE.Mesh(new THREE.BoxGeometry(width * 0.32, 0.16, depth * 0.34), boxMatLight);
  top.position.set(-width * 0.16, 0.38, 0.02);
  top.rotation.y = -0.2;
  top.castShadow = true;
  group.add(big, tape, small, top);
  return group;
}

function createRugModel(width: number, depth: number, _tex: TextureKit) {
  const group = new THREE.Group();
  const shape = roundedRectShape(width, depth, 0.22);
  const rug = new THREE.Mesh(
    new THREE.ShapeGeometry(shape, 12),
    new THREE.MeshStandardMaterial({ color: "#d9e1e9", roughness: 1, metalness: 0 })
  );
  rug.rotation.x = -Math.PI / 2;
  rug.position.y = 0.012;
  rug.receiveShadow = true;
  const inner = new THREE.Mesh(
    new THREE.ShapeGeometry(roundedRectShape(width - 0.3, depth - 0.3, 0.18), 12),
    new THREE.MeshStandardMaterial({ color: "#cbd6e0", roughness: 1, metalness: 0 })
  );
  inner.rotation.x = -Math.PI / 2;
  inner.position.y = 0.016;
  inner.receiveShadow = true;
  group.add(rug, inner);
  return group;
}

function createDoormatModel(width: number, depth: number) {
  const mat = new THREE.Mesh(
    new THREE.BoxGeometry(width, 0.015, depth),
    new THREE.MeshStandardMaterial({ color: "#9aa6b1", roughness: 0.95 })
  );
  mat.position.y = 0.01;
  mat.receiveShadow = true;
  return mat;
}

function roundedRectShape(width: number, depth: number, radius: number) {
  const shape = new THREE.Shape();
  const w = width / 2;
  const d = depth / 2;
  shape.moveTo(-w + radius, -d);
  shape.lineTo(w - radius, -d);
  shape.quadraticCurveTo(w, -d, w, -d + radius);
  shape.lineTo(w, d - radius);
  shape.quadraticCurveTo(w, d, w - radius, d);
  shape.lineTo(-w + radius, d);
  shape.quadraticCurveTo(-w, d, -w, d - radius);
  shape.lineTo(-w, -d + radius);
  shape.quadraticCurveTo(-w, -d, -w + radius, -d);
  return shape;
}

function meshBox(
  width: number,
  height: number,
  depth: number,
  color: string,
  x = 0,
  y = 0,
  z = 0,
  extra?: { emissive?: string; emissiveIntensity?: number }
) {
  const material = new THREE.MeshStandardMaterial({
    color,
    roughness: 0.58,
    metalness: 0.02,
    emissive: extra?.emissive ?? "#000000",
    emissiveIntensity: extra?.emissiveIntensity ?? 0,
  });
  const mesh = new THREE.Mesh(new THREE.BoxGeometry(width, height, depth), material);
  mesh.position.set(x, y, z);
  mesh.castShadow = true;
  mesh.receiveShadow = true;
  return mesh;
}

function meshCylinder(radius: number, height: number, color: string, x = 0, y = 0, z = 0) {
  const mesh = new THREE.Mesh(
    new THREE.CylinderGeometry(radius, radius, height, 24),
    new THREE.MeshStandardMaterial({ color, roughness: 0.64 })
  );
  mesh.position.set(x, y, z);
  mesh.castShadow = true;
  mesh.receiveShadow = true;
  return mesh;
}

/* ============================== 快递路线 ============================== */

interface CourierSegment {
  from: { x: number; z: number };
  to: { x: number; z: number };
  start: number;
  end: number;
  rotation: number | null; // null = 原地停留，沿用上一段朝向
}

interface CourierTimeline {
  segments: CourierSegment[];
  total: number;
}

const COURIER_SPEED = 1.05; // 世界单位 / 秒
const COURIER_DWELL = 1.6; // 停留秒数

function buildCourierTimeline(waypoints: CourierWaypoint[]): CourierTimeline {
  const segments: CourierSegment[] = [];
  let clock = 0;
  for (let i = 0; i < waypoints.length - 1; i += 1) {
    const from = waypoints[i].position;
    const to = waypoints[i + 1].position;
    const dx = to.x - from.x;
    const dz = to.z - from.z;
    const distance = Math.hypot(dx, dz);
    const duration = distance < 0.01 ? COURIER_DWELL : distance / COURIER_SPEED;
    segments.push({
      from,
      to,
      start: clock,
      end: clock + duration,
      // 猫的前方是 -Z，要朝向移动方向需用 atan2(-dx,-dz)（否则倒着走）
      rotation: distance < 0.01 ? null : Math.atan2(-dx, -dz),
    });
    clock += duration;
  }
  return { segments, total: clock };
}

function sampleCourier(timeline: CourierTimeline, time: number) {
  const t = ((time % timeline.total) + timeline.total) % timeline.total;
  let index = timeline.segments.findIndex((segment) => t >= segment.start && t < segment.end);
  if (index === -1) index = timeline.segments.length - 1;
  const segment = timeline.segments[index];
  const local = (t - segment.start) / (segment.end - segment.start);
  const eased = local * local * (3 - 2 * local);
  let rotation = segment.rotation;
  for (let i = index; rotation === null && i >= 0; i -= 1) rotation = timeline.segments[i].rotation;
  if (rotation === null) rotation = 0;
  return {
    position: {
      x: THREE.MathUtils.lerp(segment.from.x, segment.to.x, eased),
      z: THREE.MathUtils.lerp(segment.from.z, segment.to.z, eased),
    },
    rotation,
    moving: segment.rotation !== null,
  };
}

function createCourierRouteLine() {
  const unique: THREE.Vector3[] = [];
  courierWaypoints3d.forEach((point) => {
    const vec = new THREE.Vector3(point.position.x, 0.04, point.position.z);
    if (!unique.some((existing) => existing.distanceTo(vec) < 0.01)) unique.push(vec);
  });
  const geometry = new THREE.BufferGeometry().setFromPoints(unique);
  const material = new THREE.LineDashedMaterial({
    color: "#f5a623",
    dashSize: 0.16,
    gapSize: 0.12,
    transparent: true,
    opacity: 0.65,
  });
  const line = new THREE.Line(geometry, material);
  line.computeLineDistances();
  return line;
}

function createRoutePackages() {
  const group = new THREE.Group();
  const material = new THREE.MeshStandardMaterial({ color: "#d8a653", roughness: 0.72 });
  for (let index = 0; index < 2; index += 1) {
    const box = new THREE.Mesh(new THREE.BoxGeometry(0.15, 0.11, 0.11), material);
    box.castShadow = true;
    group.add(box);
  }
  return group;
}

/* ============================== 其他 ============================== */

function createSupervisorScan() {
  const group = new THREE.Group();
  const material = new THREE.MeshBasicMaterial({ color: "#1677ff", transparent: true, opacity: 0.16, side: THREE.DoubleSide });
  [0.85, 1.1, 1.35].forEach((radius, index) => {
    const ring = new THREE.Mesh(new THREE.RingGeometry(radius, radius + 0.016, 64), material.clone());
    ring.rotation.x = -Math.PI / 2;
    ring.position.set(-2.8, 0.06 + index * 0.004, -2.55);
    group.add(ring);
  });
  return group;
}

function getAgentPose(agent: Agent, seat: AgentSeat, dataLoaded: boolean): AgentPose {
  if (agent.id === "courier") return dataLoaded ? "walking" : "carryingParcel";
  return agent.pose ?? seat.pose;
}

function isAgentActive(agent: Agent, rulesLoaded: boolean, dataLoaded: boolean) {
  if (agent.id === "supervisor") return rulesLoaded;
  if (agent.id === "courier") return dataLoaded;
  return agent.status !== "idle";
}

function projectToScreen(
  point: { x: number; y: number; z: number },
  camera: THREE.Camera,
  canvas: HTMLCanvasElement
) {
  const vector = new THREE.Vector3(point.x, point.y, point.z).project(camera);
  return {
    left: (vector.x * 0.5 + 0.5) * canvas.clientWidth,
    top: (-vector.y * 0.5 + 0.5) * canvas.clientHeight,
  };
}

function splitSegments(start: number, end: number, gaps: Array<{ center: number; size: number }>) {
  const sorted = gaps
    .map((gap) => ({ start: gap.center - gap.size / 2, end: gap.center + gap.size / 2 }))
    .sort((a, b) => a.start - b.start);
  const segments: Array<[number, number]> = [];
  let cursor = start;
  sorted.forEach((gap) => {
    if (gap.start > cursor) segments.push([cursor, Math.min(gap.start, end)]);
    cursor = Math.max(cursor, gap.end);
  });
  if (cursor < end) segments.push([cursor, end]);
  return segments.filter(([a, b]) => b - a > 0.08);
}
