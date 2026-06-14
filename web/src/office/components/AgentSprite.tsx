import type { Agent } from "../types/domain";
import { Agent3D } from "./Agent3D";

interface AgentSpriteProps {
  agent: Agent;
  active?: boolean;
  size?: "sm" | "md" | "lg";
}

export function AgentSprite({ agent, active, size = "md" }: AgentSpriteProps) {
  return <Agent3D agent={agent} active={active} size={size} />;
}
