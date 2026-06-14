import { AnimatePresence, motion } from "framer-motion";
import { BatteryFull, ChevronLeft, Paperclip, Search, Send, Signal, Smartphone, Wifi, X } from "lucide-react";
import { useEffect, useMemo, useRef, useState } from "react";
import { agents, agentNameMap, conversations, initialMessages } from "../data/mockData";
import { sendConstrainedChatMessage } from "../../lib/apiClient";
import type { AgentId, ChatMessage } from "../types/domain";
import { CatAvatar } from "./CatAvatar";

type ConversationId = AgentId | "group";

interface PhoneChatProps {
  open: boolean;
  focusConversation: ConversationId;
  fConfig: { files: string[]; prompt: string };
  rulesetId?: string;
  injectedMessages?: ChatMessage[];
  groupAsChat?: boolean;
  onOpen: () => void;
  onClose: () => void;
}

const agentColor = (id: string) => agents.find((a) => a.id === id)?.color ?? "#1677ff";

export function PhoneChat({ open, focusConversation, fConfig, rulesetId, injectedMessages, groupAsChat, onOpen, onClose }: PhoneChatProps) {
  const [view, setView] = useState<"list" | "chat">("list");
  const [activeId, setActiveId] = useState<ConversationId>("group");
  const [messages, setMessages] = useState<ChatMessage[]>(initialMessages);
  const [draft, setDraft] = useState("");
  const msgEndRef = useRef<HTMLDivElement | null>(null);

  // 一键演示：父级注入的群聊消息作为「渲染期叠加」（不并入 state）——
  // 父级每轮把 chatInjections 重置为 []，这里即自动清空上一轮，无需手动去重计数。
  const allMessages = useMemo<ChatMessage[]>(() => {
    if (!injectedMessages || injectedMessages.length === 0) return messages;
    const seen = new Set(messages.map((m) => m.id));
    return [...messages, ...injectedMessages.filter((m) => !seen.has(m.id))];
  }, [messages, injectedMessages]);

  useEffect(() => {
    if (!open) return;
    // 普通点开手机 → 群聊默认进会话列表；一键演示(groupAsChat) → 直接进群聊看结果
    if (focusConversation === "group" && !groupAsChat) {
      setView("list");
    } else {
      setActiveId(focusConversation);
      setView("chat");
    }
  }, [open, focusConversation, groupAsChat]);

  const active = conversations.find((c) => c.id === activeId) ?? conversations[0];
  const visibleMessages = useMemo(
    () => allMessages.filter((m) => m.conversationId === activeId),
    [allMessages, activeId]
  );

  useEffect(() => {
    msgEndRef.current?.scrollIntoView({ block: "end" });
  }, [visibleMessages.length, view]);

  const lastByConversation = useMemo(() => {
    const map = new Map<string, ChatMessage>();
    for (const m of allMessages) map.set(m.conversationId, m);
    return map;
  }, [allMessages]);

  function nowLabel() {
    const d = new Date();
    return `${String(d.getHours()).padStart(2, "0")}:${String(d.getMinutes()).padStart(2, "0")}`;
  }

  async function send() {
    const text = draft.trim();
    if (!text) return;
    const time = nowLabel();
    const userMessage: ChatMessage = {
      id: `msg-${Date.now()}`,
      conversationId: activeId,
      sender: "me",
      content: text,
      time,
    };
    setMessages((cur) => [...cur, userMessage]);
    setDraft("");

    if (activeId === "pm") {
      try {
        const response = await sendConstrainedChatMessage({
          conversationId: "pm",
          rulesetId,
          message: text,
          systemPrompt: fConfig.prompt,
          ragFiles: fConfig.files,
        });
      const reply: ChatMessage = {
          id: response.messageId ?? `msg-${Date.now() + 1}`,
        conversationId: "pm",
        sender: "pm",
          content: response.reply ?? response.content ?? "后端返回为空。",
          time: nowLabel(),
          constrained: response.constrained ?? true,
      };
        setMessages((cur) => [...cur, reply]);
      } catch (error) {
        const message = error instanceof Error ? error.message : String(error);
        setMessages((cur) => [
          ...cur,
          {
            id: `msg-${Date.now() + 1}`,
            conversationId: "pm",
            sender: "system",
            content: `受控聊天后端调用失败：${message}`,
            time: nowLabel(),
            constrained: true,
          },
        ]);
      }
    }
  }

  return (
    <>
      <motion.button
        className="phone-dock"
        onClick={onOpen}
        whileHover={{ scale: 1.04 }}
        whileTap={{ scale: 0.97 }}
        aria-label="打开手机对话"
      >
        <div className="phone-dock-island" />
        <Smartphone size={24} />
        <span />
      </motion.button>

      <AnimatePresence>
        {open ? (
          <motion.div className="phone-overlay" initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }}>
            <motion.section
              className="phone-frame"
              initial={{ opacity: 0, y: 40, scale: 0.92 }}
              animate={{ opacity: 1, y: 0, scale: 1 }}
              exit={{ opacity: 0, y: 24, scale: 0.94 }}
              transition={{ type: "spring", stiffness: 210, damping: 24 }}
            >
              <div className="phone-island" />
              <div className="phone-glass-glint" />
              <button className="icon-button phone-close" onClick={onClose} aria-label="关闭手机">
                <X size={16} />
              </button>

              <div className="phone-app">
                <div className="wx-statusbar">
                  <strong>9:41</strong>
                  <span className="wx-statusbar-icons">
                    <Signal size={13} />
                    <Wifi size={13} />
                    <BatteryFull size={15} />
                  </span>
                </div>

                {view === "list" ? (
                  <div className="wx-screen">
                    <div className="wx-topbar">
                      <span className="wx-topbar-title">微信</span>
                      <span className="wx-topbar-count">{conversations.length}</span>
                    </div>
                    <div className="wx-search">
                      <Search size={14} />
                      <span>搜索</span>
                    </div>
                    <div className="wx-convlist">
                      {conversations.map((c) => {
                        const last = lastByConversation.get(c.id);
                        return (
                          <button key={c.id} className="wx-conv" onClick={() => { setActiveId(c.id as ConversationId); setView("chat"); }}>
                            <span className="wx-conv-avatar">
                              {c.id === "group" ? (
                                <span className="wx-group-avatar">群</span>
                              ) : (
                                <CatAvatar color={agentColor(c.avatarAgent ?? c.id)} size={46} radius={10} />
                              )}
                            </span>
                            <span className="wx-conv-main">
                              <strong>{c.title}</strong>
                              <small>{last ? last.content : c.subtitle}</small>
                            </span>
                            <span className="wx-conv-meta">
                              <em>{last?.time ?? ""}</em>
                              {c.id === "pm" ? <i className="wx-dot" /> : null}
                            </span>
                          </button>
                        );
                      })}
                    </div>
                  </div>
                ) : (
                  <div className="wx-screen wx-screen--chat">
                    <div className="wx-chat-top">
                      <button className="wx-back" onClick={() => setView("list")} aria-label="返回">
                        <ChevronLeft size={20} />
                      </button>
                      <div className="wx-chat-title">
                        <strong>{active.title}</strong>
                        <span>{activeId === "pm" ? "受规则约束输出" : active.subtitle}</span>
                      </div>
                      <span className="wx-robot wx-robot--ghost" />
                    </div>

                    <div className="wx-msgs">
                      {visibleMessages.map((m) => (
                        <MessageBubble key={m.id} message={m} isGroup={activeId === "group"} />
                      ))}
                      <div ref={msgEndRef} />
                    </div>

                    <div className="wx-inputbar">
                      <button className="wx-input-icon" aria-label="附件">
                        <Paperclip size={17} />
                      </button>
                      <input
                        value={draft}
                        onChange={(e) => setDraft(e.target.value)}
                        onKeyDown={(e) => {
                          if (e.key === "Enter") send();
                        }}
                        placeholder={activeId === "pm" ? "向产品经理F提问…" : `发消息给${active.title}`}
                      />
                      <button className="wx-send" onClick={send} aria-label="发送">
                        <Send size={15} />
                      </button>
                    </div>
                  </div>
                )}

                <div className="wx-home" />
              </div>
            </motion.section>
          </motion.div>
        ) : null}
      </AnimatePresence>
    </>
  );
}

function MessageBubble({ message, isGroup }: { message: ChatMessage; isGroup: boolean }) {
  const isMe = message.sender === "me";
  const senderName = isMe ? "我" : agentNameMap[message.sender] ?? "系统";
  const color = isMe ? "#07c160" : agentColor(message.sender);

  return (
    <div className={`wx-row ${isMe ? "is-me" : ""}`}>
      <span className="wx-row-avatar">
        <CatAvatar color={color} size={36} radius={8} />
      </span>
      <div className="wx-bubble-wrap">
        {isGroup && !isMe ? <small className="wx-sender">{senderName}</small> : null}
        <div className={`wx-bubble ${isMe ? "is-me" : ""} ${message.constrained ? "is-constrained" : ""}`}>
          {message.constrained ? <span className="wx-constrained-tag">规则约束</span> : null}
          <p>{message.content}</p>
        </div>
      </div>
    </div>
  );
}
