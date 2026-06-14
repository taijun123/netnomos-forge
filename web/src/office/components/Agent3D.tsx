import { useEffect, useRef, type CSSProperties } from "react";
import * as THREE from "three";
import type { Agent, AgentPose } from "../types/domain";
import { createCatAgentRig, updateCatAgentRig } from "./CatAgentRig";

interface Agent3DProps {
  agent: Agent;
  active?: boolean;
  size?: "sm" | "md" | "lg";
  pose?: AgentPose;
}

const sizeClass = {
  sm: "agent-3d--sm",
  md: "agent-3d--md",
  lg: "agent-3d--lg",
};

export function Agent3D({ agent, active = false, size = "md", pose }: Agent3DProps) {
  const mountRef = useRef<HTMLDivElement | null>(null);

  useEffect(() => {
    const mount = mountRef.current;
    if (!mount) return;
    const host = mount;

    const reduceMotion = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
    const scene = new THREE.Scene();
    const camera = new THREE.OrthographicCamera(-2.4, 2.4, 2.4, -2.4, 0.1, 100);
    camera.position.set(0, 1.15, 7);
    camera.lookAt(0, 0.35, 0);

    const renderer = new THREE.WebGLRenderer({ alpha: true, antialias: true });
    renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2));
    renderer.outputColorSpace = THREE.SRGBColorSpace;
    host.appendChild(renderer.domElement);

    const ambient = new THREE.AmbientLight(0xffffff, 2.2);
    const key = new THREE.DirectionalLight(0xffffff, 2.8);
    key.position.set(3, 5, 5);
    const rim = new THREE.DirectionalLight(new THREE.Color(agent.color), 1.6);
    rim.position.set(-3, 2, 4);
    scene.add(ambient, key, rim);

    const rigPose = pose ?? agent.pose ?? (agent.id === "courier" ? "carryingParcel" : "seatedTyping");
    const cat = createCatAgentRig(agent, rigPose);
    scene.add(cat.root);

    function resize() {
      const width = Math.max(1, host.clientWidth);
      const height = Math.max(1, host.clientHeight);
      renderer.setSize(width, height, false);
    }

    const observer = new ResizeObserver(resize);
    observer.observe(host);
    resize();

    let frame = 0;
    const startedAt = performance.now();
    const animate = () => {
      const t = (performance.now() - startedAt) / 1000;
      updateCatAgentRig(cat, agent, rigPose, t, active, reduceMotion);
      renderer.render(scene, camera);
      frame = requestAnimationFrame(animate);
    };
    animate();

    return () => {
      cancelAnimationFrame(frame);
      observer.disconnect();
      renderer.dispose();
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
    };
  }, [active, agent, pose, size]);

  return (
    <div
      className={`agent-3d ${sizeClass[size]} ${active ? "is-active" : ""}`}
      style={{ "--agent-color": agent.color } as CSSProperties}
      aria-label={agent.name}
      ref={mountRef}
    />
  );
}
