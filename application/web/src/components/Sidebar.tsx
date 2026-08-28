import { useEffect, useRef, useState } from "react";
import { api } from "../api";
import { formatBrandTitle } from "../formatBrandTitle";
import { useTheme } from "../hooks/useTheme";
import type { Theme } from "../theme";
import type { AppConfig, Task } from "../types";
import { ConfigDrawer } from "./ConfigDrawer";
import { KnowledgeGraphModal } from "./KnowledgeGraphModal";
import { LlmGatewayModal } from "./LlmGatewayModal";
import { WikiGraphModal } from "./WikiGraphModal";
import { WikiConfigureModal } from "./WikiConfigureModal";
import { SyncProgressModal } from "./SyncProgressModal";
import { TaskListItem } from "./TaskListItem";
import {
  AppearanceIcon,
  ChevronIcon,
  DashboardIcon,
  GuardrailIcon,
  KnowledgeGraphIcon,
  LlmGatewayIcon,
  LogoutIcon,
  McpIcon,
  MemoryIcon,
  ModelIcon,
  NewTaskIcon,
  SettingsIcon,
  SkillIcon,
  WikiIcon,
  CloseIcon,
} from "./SidebarIcons";

type DrawerKind = "skill" | "mcp" | "model" | "appearance" | "wiki" | "knowledge" | null;

const LLM_GATEWAY_NOT_CONFIGURED =
  "LLM Gateway가 설정되어 있지 않아 활성화할 수 없습니다. 관리자에게 설정을 요청하세요.";

const THEME_OPTIONS = ["Light", "Dark"] as const;
const WIKI_OPTIONS = ["Sync", "Graph", "Configure"] as const;
const KNOWLEDGE_ACTIONS = ["Sync", "Graph"] as const;

function themeToLabel(theme: Theme): string {
  return theme === "light" ? "Light" : "Dark";
}

function labelToTheme(label: string): Theme {
  return label === "Light" ? "light" : "dark";
}

interface Props {
  userId: string;
  tasks: Task[];
  activeTask: Task | null;
  config: AppConfig | null;
  drawer: DrawerKind;
  open: boolean;
  onClose: () => void;
  onNewTask: () => void;
  onSelectTask: (id: string) => void;
  onOpenDrawer: (kind: DrawerKind) => void;
  onCloseDrawer: () => void;
  onPatchTask: (taskId: string, patch: Partial<Task>) => void | Promise<void>;
  onDeleteTask: (taskId: string) => void;
  onLogout: () => void;
  knowledgeGraphEnabled?: boolean;
  onPatchKnowledgeGraphEnabled?: (enabled: boolean) => void | Promise<void>;
  onOpenDashboard?: () => void;
  onRefreshConfig?: () => Promise<AppConfig | void> | AppConfig | void;
}

export function Sidebar({
  userId,
  tasks,
  activeTask,
  config,
  drawer,
  open,
  onClose,
  onNewTask,
  onSelectTask,
  onOpenDrawer,
  onCloseDrawer,
  onPatchTask,
  onDeleteTask,
  onLogout,
  knowledgeGraphEnabled = true,
  onPatchKnowledgeGraphEnabled,
  onOpenDashboard,
  onRefreshConfig,
}: Props) {
  const skillBtnRef = useRef<HTMLButtonElement>(null);
  const mcpBtnRef = useRef<HTMLButtonElement>(null);
  const modelBtnRef = useRef<HTMLButtonElement>(null);
  const appearanceBtnRef = useRef<HTMLButtonElement>(null);
  const wikiBtnRef = useRef<HTMLButtonElement>(null);
  const knowledgeBtnRef = useRef<HTMLButtonElement>(null);
  const settingsSectionRef = useRef<HTMLDivElement>(null);
  const [llmGatewayOpen, setLlmGatewayOpen] = useState(false);
  const [knowledgeGraphOpen, setKnowledgeGraphOpen] = useState(false);
  const [wikiGraphOpen, setWikiGraphOpen] = useState(false);
  const [wikiConfigureOpen, setWikiConfigureOpen] = useState(false);
  const [wikiSyncBusy, setWikiSyncBusy] = useState(false);
  const [wikiSyncMessage, setWikiSyncMessage] = useState<string | null>(null);
  const [wikiSyncProgress, setWikiSyncProgress] = useState<{
    file?: string | null;
    file_i?: number | null;
    file_n?: number | null;
    page?: number | null;
    page_n?: number | null;
    pct?: number | null;
    aggregated?: boolean | null;
  } | null>(null);
  const [wikiSyncPopupOpen, setWikiSyncPopupOpen] = useState(false);
  const [knowledgeSyncBusy, setKnowledgeSyncBusy] = useState(false);
  const [knowledgeSyncMessage, setKnowledgeSyncMessage] = useState<string | null>(null);
  const [knowledgeSyncPopupOpen, setKnowledgeSyncPopupOpen] = useState(false);
  const [settingsExpanded, setSettingsExpanded] = useState(false);
  const { theme, setTheme } = useTheme();
  const skills = activeTask?.skills ?? config?.default_skills ?? [];
  const mcpServers = activeTask?.mcp_servers ?? config?.default_mcp_servers ?? [];
  const modelName = activeTask?.model_name ?? config?.default_model ?? "";
  const brandTitle = formatBrandTitle(config?.projectName ?? "agent", userId);
  const pinnedTasks = tasks.filter((task) => task.pinned);
  const regularTasks = tasks.filter((task) => !task.pinned);
  const llmGatewayEnabled = activeTask?.llm_gateway_enabled ?? false;
  const gatewayModels = config?.gateway_models ?? [];
  const modelOptions =
    llmGatewayEnabled && gatewayModels.length > 0 ? gatewayModels : (config?.models ?? []);

  function collapseSettings() {
    setSettingsExpanded(false);
    setLlmGatewayOpen(false);
    onCloseDrawer();
  }

  useEffect(() => {
    if (!activeTask || !llmGatewayEnabled || gatewayModels.length === 0) return;
    if (gatewayModels.includes(modelName)) return;
    const next =
      config?.default_gateway_model && gatewayModels.includes(config.default_gateway_model)
        ? config.default_gateway_model
        : gatewayModels[0];
    onPatchTask(activeTask.id, { model_name: next });
  }, [
    activeTask,
    llmGatewayEnabled,
    gatewayModels,
    modelName,
    config?.default_gateway_model,
    onPatchTask,
  ]);

  useEffect(() => {
    if (!settingsExpanded) return;

    function onPointerDown(e: MouseEvent) {
      const target = e.target;
      if (!(target instanceof Element)) return;
      if (settingsSectionRef.current?.contains(target)) return;
      if (target.closest(".config-popover")) return;
      if (target.closest(".modal-overlay, .llm-gateway-modal, .knowledge-graph-modal, .wiki-configure-modal, .sync-progress-modal")) return;
      collapseSettings();
    }

    document.addEventListener("mousedown", onPointerDown);
    return () => document.removeEventListener("mousedown", onPointerDown);
  }, [settingsExpanded, onCloseDrawer]);

  async function handleWikiAction(choice: string) {
    if (choice === "Graph") {
      setWikiGraphOpen(true);
      handleSettingApplied();
      return;
    }
    if (choice === "Configure") {
      setWikiConfigureOpen(true);
      handleSettingApplied();
      return;
    }
    if (choice !== "Sync") return;
    setWikiSyncPopupOpen(true);
    setWikiSyncBusy(true);
    setWikiSyncMessage("Wiki 동기화를 시작합니다…");
    try {
      const result = await api.syncWiki(false, modelName || undefined);
      const status = result.status;
      if (status === "error") {
        setWikiSyncBusy(false);
        setWikiSyncMessage(result.error || "Wiki 동기화에 실패했습니다.");
      } else if (status === "unchanged") {
        setWikiSyncBusy(false);
        setWikiSyncMessage("변경된 파일이 없습니다.");
      } else {
        // Keep syncing indicator; background poll clears it when done.
        setWikiSyncBusy(true);
        setWikiSyncMessage(
          result.message || "Wiki 동기화를 백그라운드에서 실행 중입니다.",
        );
      }
    } catch (err) {
      setWikiSyncBusy(false);
      setWikiSyncMessage(
        err instanceof Error ? err.message : "Wiki 동기화에 실패했습니다.",
      );
    } finally {
      // Do not open Graph modal — sync continues independently.
      handleSettingApplied();
    }
  }

  async function handleKnowledgeAction(choice: string) {
    if (choice === "On" || choice === "Off") {
      // Label shows current state; click toggles the opposite.
      const enabled = choice === "Off";
      try {
        await onPatchKnowledgeGraphEnabled?.(enabled);
      } finally {
        handleSettingApplied();
      }
      return;
    }
    if (choice === "Graph") {
      setKnowledgeGraphOpen(true);
      handleSettingApplied();
      return;
    }
    if (choice !== "Sync") return;
    setKnowledgeSyncPopupOpen(true);
    setKnowledgeSyncBusy(true);
    setKnowledgeSyncMessage("Knowledge 동기화를 시작합니다…");
    try {
      const result = await api.rebuildGraph(false);
      const status = result.status;
      if (status === "error") {
        setKnowledgeSyncBusy(false);
        setKnowledgeSyncMessage(result.error || "Knowledge 동기화에 실패했습니다.");
      } else if (status === "skipped_cooldown") {
        setKnowledgeSyncBusy(false);
        setKnowledgeSyncMessage(
          result.message || "잠시 후 다시 동기화할 수 있습니다.",
        );
      } else if (status === "skipped_unchanged") {
        setKnowledgeSyncBusy(false);
        setKnowledgeSyncMessage(result.message || "변경된 소스가 없습니다.");
      } else if (status === "disabled") {
        setKnowledgeSyncBusy(false);
        setKnowledgeSyncMessage("Knowledge가 Off 상태입니다. On으로 켠 뒤 Sync 하세요.");
      } else if (status === "queued" || status === "running") {
        setKnowledgeSyncBusy(true);
        setKnowledgeSyncMessage(
          result.message || "Knowledge 동기화를 백그라운드에서 실행 중입니다.",
        );
      } else {
        setKnowledgeSyncBusy(false);
        setKnowledgeSyncMessage(
          result.message || "Knowledge 동기화가 완료되었습니다.",
        );
      }
    } catch (err) {
      setKnowledgeSyncBusy(false);
      setKnowledgeSyncMessage(
        err instanceof Error ? err.message : "Knowledge 동기화에 실패했습니다.",
      );
    } finally {
      handleSettingApplied();
    }
  }

  useEffect(() => {
    let cancelled = false;
    let timer: ReturnType<typeof setTimeout> | null = null;

    async function pollWikiSync() {
      try {
        const next = await api.getWikiStatus();
        if (cancelled) return;
        const busy = next.status === "queued" || next.status === "running";
        setWikiSyncBusy(busy);
        if (next.progress) {
          setWikiSyncProgress(next.progress);
        }
        if (busy) {
          setWikiSyncMessage(
            next.message || "Wiki 동기화를 백그라운드에서 실행 중입니다.",
          );
          timer = setTimeout(pollWikiSync, 1500);
          return;
        }
        if (next.status === "ready") {
          setWikiSyncMessage(next.message || "Wiki 동기화가 완료되었습니다.");
        } else if (next.status === "unchanged") {
          setWikiSyncMessage("변경된 파일이 없습니다.");
        } else if (next.status === "error") {
          setWikiSyncMessage(next.error || "Wiki 동기화에 실패했습니다.");
        }
      } catch {
        if (cancelled) return;
        // Keep polling while we believe a sync may be running.
        if (wikiSyncBusy) {
          timer = setTimeout(pollWikiSync, 3000);
        }
      }
    }

    void pollWikiSync();
    return () => {
      cancelled = true;
      if (timer) clearTimeout(timer);
    };
  }, [wikiSyncBusy]);

  useEffect(() => {
    let cancelled = false;
    let timer: ReturnType<typeof setTimeout> | null = null;

    async function pollKnowledgeSync() {
      try {
        const next = await api.getGraphStatus();
        if (cancelled) return;
        const busy = next.status === "queued" || next.status === "running";
        setKnowledgeSyncBusy(busy);
        if (busy) {
          setKnowledgeSyncMessage(
            next.message || "Knowledge 동기화를 백그라운드에서 실행 중입니다.",
          );
          timer = setTimeout(pollKnowledgeSync, 2500);
          return;
        }
        if (next.status === "ready") {
          setKnowledgeSyncMessage(
            next.message || "Knowledge 동기화가 완료되었습니다.",
          );
        } else if (next.status === "error") {
          setKnowledgeSyncMessage(next.error || "Knowledge 동기화에 실패했습니다.");
        }
      } catch {
        if (cancelled) return;
        if (knowledgeSyncBusy) {
          timer = setTimeout(pollKnowledgeSync, 4000);
        }
      }
    }

    void pollKnowledgeSync();
    return () => {
      cancelled = true;
      if (timer) clearTimeout(timer);
    };
  }, [knowledgeSyncBusy]);

  function renderTask(task: Task, hidePinBadge = false) {
    return (
      <TaskListItem
        key={task.id}
        task={task}
        active={activeTask?.id === task.id}
        hidePinBadge={hidePinBadge}
        onSelect={() => {
          collapseSettings();
          onSelectTask(task.id);
        }}
        onDelete={() => onDeleteTask(task.id)}
        onRename={(title) => onPatchTask(task.id, { title })}
        onTogglePin={() => onPatchTask(task.id, { pinned: !task.pinned })}
      />
    );
  }

  function toggleDrawer(kind: Exclude<DrawerKind, null>) {
    onOpenDrawer(drawer === kind ? null : kind);
  }

  function handleSettingApplied() {
    collapseSettings();
  }

  function handleDrawerClose() {
    onCloseDrawer();
    setSettingsExpanded(false);
  }

  return (
    <>
      <aside className={`sidebar${open ? " sidebar-panel-open" : ""}`}>
        <div className="sidebar-header">
          <div className="brand-row">
            <button
              type="button"
              className={`brand brand-graph-btn${knowledgeGraphEnabled ? "" : " is-disabled"}`}
              title={
                knowledgeGraphEnabled
                  ? "Knowledge Graph 보기"
                  : "Knowledge Graph가 꺼져 있습니다"
              }
              aria-label={
                knowledgeGraphEnabled
                  ? `${brandTitle} Knowledge Graph 보기`
                  : brandTitle
              }
              aria-disabled={!knowledgeGraphEnabled}
              onClick={() => {
                if (!knowledgeGraphEnabled) return;
                collapseSettings();
                setKnowledgeGraphOpen(true);
              }}
            >
              {brandTitle}
            </button>
            <div className="sidebar-header-actions">
              <button
                type="button"
                className="sidebar-close-btn"
                aria-label="메뉴 닫기"
                onClick={onClose}
              >
                <CloseIcon className="sidebar-icon" />
              </button>
              <button
                type="button"
                className="brand-logout-btn"
                aria-label="나가기"
                title="나가기"
                onClick={onLogout}
              >
                <LogoutIcon className="sidebar-icon" />
              </button>
            </div>
          </div>
        </div>

        <button
          type="button"
          className="sidebar-menu-btn"
          onClick={() => {
            collapseSettings();
            onNewTask();
          }}
        >
          <NewTaskIcon className="sidebar-icon" />
          <span>New task</span>
        </button>

        {config?.is_admin && onOpenDashboard && (
          <button
            type="button"
            className="sidebar-menu-btn"
            onClick={() => {
              collapseSettings();
              onOpenDashboard();
            }}
          >
            <DashboardIcon className="sidebar-icon" />
            <span>Dashboard</span>
          </button>
        )}

        <div className="task-list">
          {pinnedTasks.length > 0 && (
            <div className="task-list-section">
              <div className="section-label">Pinned</div>
              {pinnedTasks.map((task) => renderTask(task, true))}
            </div>
          )}
          {regularTasks.length > 0 && (
            <div className="task-list-section">
              {pinnedTasks.length > 0 && <div className="section-label">Tasks</div>}
              {regularTasks.map((task) => renderTask(task))}
            </div>
          )}
        </div>

        <button
          ref={modelBtnRef}
          type="button"
          className={`sidebar-menu-btn${drawer === "model" ? " is-active" : ""}`}
          aria-expanded={drawer === "model"}
          aria-haspopup="dialog"
          title={modelName || "Model"}
          disabled={!activeTask}
          onClick={() => {
            setSettingsExpanded(false);
            setLlmGatewayOpen(false);
            if (drawer === "model") {
              onCloseDrawer();
            } else {
              onOpenDrawer("model");
            }
          }}
        >
          <ModelIcon className="sidebar-icon" />
          <span>{modelName || "Model"}</span>
        </button>

        <div
          ref={settingsSectionRef}
          className={`sidebar-section${settingsExpanded ? " is-expanded" : ""}`}
        >
          <button
            type="button"
            className="section-toggle"
            aria-expanded={settingsExpanded}
            onClick={() => {
              if (settingsExpanded) {
                collapseSettings();
                return;
              }
              onCloseDrawer();
              setSettingsExpanded(true);
            }}
          >
            <SettingsIcon className="sidebar-icon" />
            <span>Settings</span>
            <ChevronIcon className="section-chevron" />
          </button>
          {settingsExpanded && (
            <div className="sidebar-section-body">
              <button
                ref={skillBtnRef}
                type="button"
                className={`sidebar-menu-btn${drawer === "skill" ? " is-active" : ""}`}
                aria-expanded={drawer === "skill"}
                aria-haspopup="dialog"
                onClick={() => toggleDrawer("skill")}
                disabled={!activeTask}
              >
                <SkillIcon className="sidebar-icon" />
                <span>Skill ({skills.length})</span>
              </button>
              <button
                ref={mcpBtnRef}
                type="button"
                className={`sidebar-menu-btn${drawer === "mcp" ? " is-active" : ""}`}
                aria-expanded={drawer === "mcp"}
                aria-haspopup="dialog"
                onClick={() => toggleDrawer("mcp")}
                disabled={!activeTask}
              >
                <McpIcon className="sidebar-icon" />
                <span>MCP ({mcpServers.length})</span>
              </button>
              <button
                ref={wikiBtnRef}
                type="button"
                className={`sidebar-menu-btn${drawer === "wiki" || wikiSyncBusy ? " is-active" : ""}`}
                aria-expanded={drawer === "wiki"}
                aria-haspopup="dialog"
                title={wikiSyncMessage ?? "Wiki"}
                onClick={() => toggleDrawer("wiki")}
              >
                <WikiIcon className="sidebar-icon" />
                <span>{wikiSyncBusy ? "Wiki (Syncing…)" : "Wiki"}</span>
              </button>
              <button
                ref={knowledgeBtnRef}
                type="button"
                className={`sidebar-menu-btn${drawer === "knowledge" || knowledgeSyncBusy ? " is-active" : ""}`}
                aria-expanded={drawer === "knowledge"}
                aria-haspopup="dialog"
                title={knowledgeSyncMessage ?? "Knowledge"}
                onClick={() => toggleDrawer("knowledge")}
              >
                <KnowledgeGraphIcon className="sidebar-icon" />
                <span>{knowledgeSyncBusy ? "Knowledge (Syncing…)" : "Knowledge"}</span>
              </button>
              <label className="sidebar-menu-btn settings-toggle">
                <GuardrailIcon className="sidebar-icon" />
                <span>Guardrail</span>
                <input
                  type="checkbox"
                  checked={activeTask?.guardrail_enabled ?? false}
                  disabled={!activeTask}
                  onChange={(e) => {
                    if (!activeTask) return;
                    onPatchTask(activeTask.id, {
                      guardrail_enabled: e.target.checked,
                    });
                    handleSettingApplied();
                  }}
                />
              </label>
              <label className="sidebar-menu-btn settings-toggle">
                <MemoryIcon className="sidebar-icon" />
                <span>Memory</span>
                <input
                  type="checkbox"
                  checked={activeTask?.memory_enabled ?? true}
                  disabled={!activeTask}
                  onChange={(e) => {
                    if (!activeTask) return;
                    onPatchTask(activeTask.id, {
                      memory_enabled: e.target.checked,
                    });
                    handleSettingApplied();
                  }}
                />
              </label>
              <button
                type="button"
                className={`sidebar-menu-btn${llmGatewayOpen ? " is-active" : ""}`}
                disabled={!activeTask}
                onClick={() => setLlmGatewayOpen(true)}
              >
                <LlmGatewayIcon className="sidebar-icon" />
                <span>
                  LLM Gateway{llmGatewayEnabled ? " (On)" : ""}
                </span>
              </button>
              <button
                ref={appearanceBtnRef}
                type="button"
                className={`sidebar-menu-btn${drawer === "appearance" ? " is-active" : ""}`}
                aria-expanded={drawer === "appearance"}
                aria-haspopup="dialog"
                onClick={() => toggleDrawer("appearance")}
              >
                <AppearanceIcon className="sidebar-icon" />
                <span>Appearance ({themeToLabel(theme)})</span>
              </button>
            </div>
          )}
        </div>
      </aside>

      {drawer === "skill" && config && activeTask && (
        <ConfigDrawer
          title="Skill"
          options={config.skills}
          selected={skills}
          anchorEl={skillBtnRef.current}
          onChange={(next) => activeTask && onPatchTask(activeTask.id, { skills: next })}
          onClose={handleDrawerClose}
        />
      )}
      {drawer === "mcp" && config && activeTask && (
        <ConfigDrawer
          title="MCP"
          options={config.mcp_servers}
          selected={mcpServers}
          anchorEl={mcpBtnRef.current}
          onChange={(next) => activeTask && onPatchTask(activeTask.id, { mcp_servers: next })}
          onClose={handleDrawerClose}
        />
      )}
      {drawer === "model" && config && activeTask && (
        <ConfigDrawer
          title={llmGatewayEnabled ? "Model (LLM Gateway)" : "Model"}
          options={modelOptions}
          selected={modelName ? [modelName] : []}
          mode="single"
          anchorEl={modelBtnRef.current}
          onChange={(next) =>
            activeTask && next[0] && onPatchTask(activeTask.id, { model_name: next[0] })
          }
          onClose={onCloseDrawer}
        />
      )}
      {drawer === "appearance" && (
        <ConfigDrawer
          title="Appearance"
          options={[...THEME_OPTIONS]}
          selected={[themeToLabel(theme)]}
          mode="single"
          anchorEl={appearanceBtnRef.current}
          onChange={(next) => {
            if (next[0]) setTheme(labelToTheme(next[0]));
          }}
          onClose={handleDrawerClose}
        />
      )}
      {drawer === "wiki" && (
        <ConfigDrawer
          title="Wiki"
          options={[...WIKI_OPTIONS]}
          selected={[]}
          mode="single"
          anchorEl={wikiBtnRef.current}
          onChange={(next) => {
            if (next[0]) void handleWikiAction(next[0]);
          }}
          onClose={handleDrawerClose}
        />
      )}
      {drawer === "knowledge" && (
        <ConfigDrawer
          title="Knowledge"
          options={[
            ...KNOWLEDGE_ACTIONS,
            knowledgeGraphEnabled ? "On" : "Off",
          ]}
          selected={[]}
          mode="single"
          anchorEl={knowledgeBtnRef.current}
          onChange={(next) => {
            if (next[0]) void handleKnowledgeAction(next[0]);
          }}
          onClose={handleDrawerClose}
        />
      )}

      {knowledgeGraphOpen && (
        <KnowledgeGraphModal
          userId={userId}
          title={brandTitle}
          onClose={() => setKnowledgeGraphOpen(false)}
        />
      )}

      {wikiGraphOpen && (
        <WikiGraphModal onClose={() => setWikiGraphOpen(false)} />
      )}

      {wikiConfigureOpen && (
        <WikiConfigureModal onClose={() => setWikiConfigureOpen(false)} />
      )}

      {wikiSyncPopupOpen && (
        <SyncProgressModal
          title="Wiki Sync"
          busy={wikiSyncBusy}
          message={wikiSyncMessage}
          progress={wikiSyncProgress}
          onClose={() => setWikiSyncPopupOpen(false)}
        />
      )}

      {knowledgeSyncPopupOpen && (
        <SyncProgressModal
          title="Knowledge Sync"
          busy={knowledgeSyncBusy}
          message={knowledgeSyncMessage}
          onClose={() => setKnowledgeSyncPopupOpen(false)}
        />
      )}

      {llmGatewayOpen && activeTask && (
        <LlmGatewayModal
          enabled={llmGatewayEnabled}
          isAdmin={Boolean(config?.is_admin)}
          gatewayConfigured={Boolean(config?.llm_gateway_configured)}
          onConfirmEnable={async (uiModels) => {
            const refreshed = await onRefreshConfig?.();
            const gatewayStatus = await api.getLlmGateway();
            const configured = Boolean(
              gatewayStatus.configured ||
                (refreshed &&
                  "llm_gateway_configured" in refreshed &&
                  refreshed.llm_gateway_configured),
            );
            if (!configured) {
              throw new Error(LLM_GATEWAY_NOT_CONFIGURED);
            }
            const gatewayList =
              uiModels && uiModels.length > 0
                ? uiModels
                : refreshed && "gateway_models" in refreshed
                  ? (refreshed.gateway_models ?? [])
                  : (config?.gateway_models ?? []);
            const defaultGw =
              refreshed && "default_gateway_model" in refreshed
                ? refreshed.default_gateway_model
                : config?.default_gateway_model;
            const patch: Partial<Task> = { llm_gateway_enabled: true };
            if (gatewayList.length > 0 && !gatewayList.includes(modelName)) {
              patch.model_name =
                defaultGw && gatewayList.includes(defaultGw)
                  ? defaultGw
                  : gatewayList[0];
            }
            await onPatchTask(activeTask.id, patch);
          }}
          onDisable={() =>
            onPatchTask(activeTask.id, { llm_gateway_enabled: false })
          }
          onClose={() => {
            setLlmGatewayOpen(false);
            setSettingsExpanded(false);
            onCloseDrawer();
          }}
        />
      )}
    </>
  );
}
