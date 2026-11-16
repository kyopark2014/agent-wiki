import type { ToolEvent } from "../types";

export interface AgentActivityStep {
  id: string;
  label: string;
  detail?: string;
  pending: boolean;
}

export interface AgentActivityState {
  summary: string;
  steps: AgentActivityStep[];
}

const TOOL_PROGRESS: Record<string, string> = {
  vault_tree: "노트 목록 확인 중",
  vault_list: "노트 목록 확인 중",
  vault_read: "문서 구조 검토 중",
  vault_search: "노트 검색 중",
  vault_graph: "그래프 관계 확인 중",
  vault_backlinks: "백링크 확인 중",
  vault_write: "노트 저장 중",
  vault_append: "노트에 내용 추가 중",
  vault_delete: "노트 삭제 중",
  vault_mkdir: "폴더 생성 중",
  vault_move: "노트 이동 중",
  vault_rename: "노트 이름 변경 중",
  get_skill_instructions: "작업 지침 확인 중",
  read_file: "파일 읽는 중",
  write_file: "파일 작성 중",
  grep: "파일 검색 중",
  execute_code: "코드 실행 중",
  bash: "명령 실행 중",
  upload_file_to_s3: "파일 업로드 중",
  get_current_time: "시간 확인 중",
  tavily_search: "웹 검색 중",
  web_search: "웹 검색 중",
  web_fetch: "웹 페이지 읽는 중",
};

function inputRecord(input: unknown): Record<string, unknown> | null {
  if (!input || typeof input !== "object" || Array.isArray(input)) return null;
  return input as Record<string, unknown>;
}

function stringField(
  input: Record<string, unknown> | null,
  ...keys: string[]
): string | undefined {
  if (!input) return undefined;
  for (const key of keys) {
    const value = input[key];
    if (typeof value === "string" && value.trim()) return value.trim();
  }
  return undefined;
}

function skillNameFromEvent(event: ToolEvent): string | undefined {
  if (event.skillName) return event.skillName;
  if (event.tool !== "get_skill_instructions") return undefined;
  return stringField(inputRecord(event.input), "skill_name", "skillName");
}

function pathFromEvent(event: ToolEvent): string | undefined {
  return stringField(
    inputRecord(event.input),
    "path",
    "filepath",
    "file_path",
    "filePath",
    "note_path",
    "notePath",
  );
}

function progressForTool(event: ToolEvent): string {
  const tool = event.tool?.trim();
  if (!tool) return "도구 실행 중";

  if (tool === "get_skill_instructions") {
    const skill = skillNameFromEvent(event);
    return skill ? `${skill} 지침 확인 중` : TOOL_PROGRESS[tool];
  }

  const mapped = TOOL_PROGRESS[tool];
  if (mapped) return mapped;

  if (event.mcpServer === "use-vault" || tool.startsWith("vault_")) {
    return `vault 작업 중 (${tool})`;
  }
  if (event.mcpServer) return `${tool} 실행 중`;
  return `${tool} 실행 중`;
}

function detailForEvent(event: ToolEvent): string | undefined {
  const path = pathFromEvent(event);
  if (path) return path;
  const skill = skillNameFromEvent(event);
  if (skill) return skill;
  if (event.type === "info" && event.data?.trim()) {
    const line = event.data.trim().split("\n")[0] ?? "";
    return line.length > 80 ? `${line.slice(0, 77)}…` : line;
  }
  return undefined;
}

function eventKey(event: ToolEvent, index: number): string {
  return event.toolUseId || `${event.type}-${event.tool ?? "x"}-${index}`;
}

/** Build a Claude-like activity summary from live stream tool events. */
export function deriveAgentActivity(
  events: ToolEvent[],
  streamText = "",
): AgentActivityState | null {
  const steps: AgentActivityStep[] = [];
  const byId = new Map<string, number>();

  events.forEach((event, index) => {
    if (event.type === "text") return;

    if (event.type === "info") {
      const detail = detailForEvent(event);
      if (!detail) return;
      steps.push({
        id: eventKey(event, index),
        label: detail,
        pending: false,
      });
      return;
    }

    if (event.type === "tool") {
      const id = event.toolUseId || eventKey(event, index);
      const step: AgentActivityStep = {
        id,
        label: progressForTool(event),
        detail: detailForEvent(event),
        pending: true,
      };
      const existing = byId.get(id);
      if (existing !== undefined) {
        steps[existing] = step;
      } else {
        byId.set(id, steps.length);
        steps.push(step);
      }
      return;
    }

    if (event.type === "tool_result") {
      const id = event.toolUseId || eventKey(event, index);
      const existing = byId.get(id);
      const label = progressForTool(event).replace(/ 중$/, " 완료");
      const step: AgentActivityStep = {
        id,
        label,
        detail: detailForEvent(event),
        pending: false,
      };
      if (existing !== undefined) {
        steps[existing] = {
          ...steps[existing],
          label: step.label,
          detail: step.detail ?? steps[existing].detail,
          pending: false,
        };
      } else {
        byId.set(id, steps.length);
        steps.push(step);
      }
    }
  });

  const pending = [...steps].reverse().find((s) => s.pending);
  const latest = steps[steps.length - 1];
  const hasLiveText = Boolean(streamText.trim());

  let summary: string;
  if (pending) {
    summary = pending.label;
  } else if (hasLiveText) {
    summary = "응답 작성 중";
  } else if (latest) {
    summary = "다음 단계 준비 중";
  } else {
    summary = "요청 처리 중";
  }

  return { summary, steps };
}
