import { useEffect, useLayoutEffect, useRef, useState } from "react";
import { createPortal } from "react-dom";
import { api, type WikiBrowseResult } from "../api";

const SOURCE_SLOTS = 3;

interface Props {
  onClose: () => void;
}

function emptySlots(values: string[] = [], count = SOURCE_SLOTS): string[] {
  const next = [...values];
  while (next.length < count) next.push("");
  return next.slice(0, count);
}

function shortPath(path: string): string {
  const home = "/Users/";
  if (path.startsWith(home)) {
    const rest = path.slice(home.length);
    const slash = rest.indexOf("/");
    if (slash >= 0) return `~${rest.slice(slash)}`;
  }
  if (path.startsWith("/home/")) {
    const parts = path.split("/");
    if (parts.length > 3) return `~/${parts.slice(3).join("/")}`;
  }
  return path;
}

export function WikiConfigureModal({ onClose }: Props) {
  const [sourceSlots, setSourceSlots] = useState<string[]>(emptySlots());
  const [urlInput, setUrlInput] = useState("");
  const [pendingDocs, setPendingDocs] = useState<File[]>([]);
  const [wikiDir, setWikiDir] = useState("");
  const [foundationModelParser, setFoundationModelParser] = useState(false);
  const [parallelProcessing, setParallelProcessing] = useState(true);
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState(false);
  const [addingUrl, setAddingUrl] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState<string | null>(null);
  const [menuIndex, setMenuIndex] = useState<number | null>(null);
  const sourceBtnRefs = useRef<Array<HTMLButtonElement | null>>([]);
  const fileInputRef = useRef<HTMLInputElement | null>(null);

  useEffect(() => {
    let cancelled = false;
    (async () => {
      setLoading(true);
      setError(null);
      try {
        const data = await api.getWikiSources();
        if (cancelled) return;
        setWikiDir(data.wiki_dir || "");
        setSourceSlots(emptySlots(data.folders || [], data.max_sources || SOURCE_SLOTS));
        setFoundationModelParser(
          Boolean(data.foundation_model_parser_enabled),
        );
        setParallelProcessing(data.parallel_processing_enabled !== false);
      } catch (err) {
        if (!cancelled) {
          setError(err instanceof Error ? err.message : String(err));
        }
      } finally {
        if (!cancelled) setLoading(false);
      }
    })();
    return () => {
      cancelled = true;
    };
  }, []);

  useEffect(() => {
    function onKeyDown(e: KeyboardEvent) {
      if (e.key === "Escape") {
        if (menuIndex !== null) {
          setMenuIndex(null);
          return;
        }
        if (!busy && !addingUrl) onClose();
      }
    }
    window.addEventListener("keydown", onKeyDown);
    return () => window.removeEventListener("keydown", onKeyDown);
  }, [busy, addingUrl, menuIndex, onClose]);

  async function handleSave() {
    setBusy(true);
    setError(null);
    setSuccess(null);
    try {
      const messages: string[] = [];

      if (pendingDocs.length > 0) {
        const result = await api.uploadWikiRawFiles(pendingDocs);
        setPendingDocs([]);
        if (fileInputRef.current) fileInputRef.current.value = "";
        const names = (result.saved || []).map((s) => s.name).join(", ");
        messages.push(
          `문서 ${result.count}개를 raw에 저장` +
            (names ? ` (${names})` : ""),
        );
      }

      const folders = sourceSlots.map((s) => s.trim()).filter(Boolean);
      const saved = await api.putWikiSources({
        folders,
        foundation_model_parser_enabled: foundationModelParser,
        parallel_processing_enabled: parallelProcessing,
      });
      setSourceSlots(emptySlots(saved.folders || [], saved.max_sources || SOURCE_SLOTS));
      setFoundationModelParser(
        Boolean(saved.foundation_model_parser_enabled),
      );
      setParallelProcessing(saved.parallel_processing_enabled !== false);
      if (saved.folders.length > 0) {
        messages.push(`Source ${saved.folders.length}개 저장`);
      } else {
        messages.push("Sources 비움 (Sync 시 raw 포함)");
      }
      messages.push(
        foundationModelParser
          ? "Foundation Model Parser On"
          : "Foundation Model Parser Off",
      );
      messages.push(
        parallelProcessing
          ? "Parallel Processing On"
          : "Parallel Processing Off",
      );

      setSuccess(
        messages.join(". ") + ". Sync를 실행하면 그래프에 반영됩니다.",
      );
      onClose();
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    } finally {
      setBusy(false);
    }
  }

  function handlePickDocuments(fileList: FileList | null) {
    if (!fileList || fileList.length === 0) return;
    const incoming = Array.from(fileList);
    if (fileInputRef.current) fileInputRef.current.value = "";

    setPendingDocs((prev) => {
      const byKey = new Map<string, File>();
      for (const f of prev) {
        byKey.set(`${f.name}:${f.size}:${f.lastModified}`, f);
      }
      for (const f of incoming) {
        byKey.set(`${f.name}:${f.size}:${f.lastModified}`, f);
      }
      return Array.from(byKey.values());
    });
    setError(null);
    setSuccess(null);
  }

  function removePendingDoc(index: number) {
    setPendingDocs((prev) => prev.filter((_, i) => i !== index));
  }

  async function handleAddUrl() {
    const url = urlInput.trim();
    if (!url) {
      setError("URL을 입력하세요.");
      return;
    }
    setAddingUrl(true);
    setError(null);
    setSuccess(null);
    try {
      const result = await api.ingestWikiUrl(url);
      setUrlInput("");
      setSuccess(
        `URL을 ${result.path || `${wikiDir || "wiki"}/raw`}에 저장했습니다.`,
      );
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    } finally {
      setAddingUrl(false);
    }
  }

  function applySourcePath(index: number, path: string) {
    const next = [...sourceSlots];
    next[index] = path;
    setSourceSlots(next);
    setMenuIndex(null);
    setSuccess(null);
    setError(null);
  }

  function clearSourcePath(index: number) {
    applySourcePath(index, "");
  }

  return createPortal(
    <div
      className="modal-overlay"
      role="dialog"
      aria-modal="true"
      aria-labelledby="wiki-configure-title"
      onMouseDown={(e) => {
        if (
          e.target === e.currentTarget &&
          !busy &&
          !addingUrl &&
          menuIndex === null
        ) {
          onClose();
        }
      }}
    >
      <div className="modal wiki-configure-modal">
        <h2 id="wiki-configure-title">Wiki Configure</h2>
        {loading ? (
          <p className="llm-gateway-muted">불러오는 중…</p>
        ) : (
          <>
            <label className="wiki-configure-toggle">
              <span className="wiki-configure-toggle-title">
                Foundation Model Parser
              </span>
              <input
                type="checkbox"
                checked={foundationModelParser}
                disabled={busy || addingUrl}
                onChange={(e) => {
                  setFoundationModelParser(e.target.checked);
                  setSuccess(null);
                }}
              />
            </label>

            <label className="wiki-configure-toggle">
              <span className="wiki-configure-toggle-title">
                Parallel Processing
              </span>
              <input
                type="checkbox"
                checked={parallelProcessing}
                disabled={busy || addingUrl}
                onChange={(e) => {
                  setParallelProcessing(e.target.checked);
                  setSuccess(null);
                }}
              />
            </label>

            <div className="wiki-configure-section-label">문서 추가</div>
            <div className="wiki-configure-docs">
              <input
                ref={fileInputRef}
                type="file"
                multiple
                className="wiki-configure-file-input"
                accept=".pdf,.md,.txt,.markdown,.rst,.docx,.pptx,.csv,.json,.html,.htm,application/pdf,text/plain,text/markdown"
                disabled={busy || addingUrl}
                onChange={(e) => {
                  handlePickDocuments(e.target.files);
                }}
              />
              <div className="wiki-configure-docs-actions">
                <button
                  type="button"
                  className="modal-btn-secondary"
                  disabled={busy || addingUrl}
                  onClick={() => fileInputRef.current?.click()}
                >
                  파일 선택…
                </button>
              </div>
              {pendingDocs.length > 0 ? (
                <ul className="wiki-configure-docs-list">
                  {pendingDocs.map((file, index) => (
                    <li key={`${file.name}-${file.size}-${file.lastModified}`}>
                      <span className="wiki-configure-docs-name">
                        {file.name}
                      </span>
                      <span className="wiki-configure-docs-meta">
                        {(file.size / 1024).toFixed(1)} KB
                      </span>
                      <button
                        type="button"
                        className="wiki-configure-docs-remove"
                        disabled={busy}
                        aria-label={`${file.name} 제거`}
                        onClick={() => removePendingDoc(index)}
                      >
                        제거
                      </button>
                    </li>
                  ))}
                </ul>
              ) : (
                <p className="wiki-configure-docs-empty">
                  파일을 선택한 뒤 하단 <strong>저장</strong>을 누르면
                  wiki/raw로 복사됩니다. 이후 Sync로 그래프에 반영하세요.
                </p>
              )}
            </div>

            <div className="wiki-configure-section-label">Sources</div>
            <div className="wiki-configure-sources">
              {sourceSlots.map((value, index) => (
                <button
                  key={`source-${index}`}
                  ref={(el) => {
                    sourceBtnRefs.current[index] = el;
                  }}
                  type="button"
                  className={`wiki-configure-source-btn${menuIndex === index ? " is-open" : ""}`}
                  disabled={busy || addingUrl}
                  aria-haspopup="dialog"
                  aria-expanded={menuIndex === index}
                  onClick={() =>
                    setMenuIndex((cur) => (cur === index ? null : index))
                  }
                >
                  <span className="wiki-configure-source-label">
                    Source {index + 1}
                  </span>
                  <span className="wiki-configure-source-path">
                    {value ? shortPath(value) : "경로 선택…"}
                  </span>
                </button>
              ))}
            </div>
            {menuIndex !== null ? (
              <SourceFolderMenu
                index={menuIndex}
                currentPath={sourceSlots[menuIndex] || ""}
                wikiDir={wikiDir}
                anchorEl={sourceBtnRefs.current[menuIndex]}
                onSelect={(path) => applySourcePath(menuIndex, path)}
                onClear={() => clearSourcePath(menuIndex)}
                onClose={() => setMenuIndex(null)}
              />
            ) : null}
            <div className="wiki-configure-section-label">URL</div>
            <div className="wiki-configure-url-row">
              <label className="llm-gateway-field wiki-configure-url-field">
                <input
                  type="url"
                  value={urlInput}
                  placeholder="예: https://example.com/article"
                  aria-label="URL"
                  disabled={busy || addingUrl}
                  autoComplete="off"
                  onChange={(e) => setUrlInput(e.target.value)}
                  onKeyDown={(e) => {
                    if (e.key === "Enter") {
                      e.preventDefault();
                      void handleAddUrl();
                    }
                  }}
                />
              </label>
              <button
                type="button"
                className="modal-btn-primary wiki-configure-url-add"
                disabled={busy || addingUrl || !urlInput.trim()}
                onClick={() => void handleAddUrl()}
              >
                {addingUrl ? "저장 중…" : "추가"}
              </button>
            </div>
          </>
        )}
        {error ? (
          <p className="modal-error" role="alert">
            {error}
          </p>
        ) : null}
        {success ? <p className="llm-gateway-success">{success}</p> : null}
        <div className="modal-actions">
          <button
            type="button"
            className="modal-btn-secondary"
            disabled={busy || addingUrl}
            onClick={onClose}
          >
            닫기
          </button>
          <button
            type="button"
            className="modal-btn-primary"
            disabled={busy || addingUrl || loading}
            onClick={() => void handleSave()}
          >
            {busy ? "저장 중…" : "저장"}
          </button>
        </div>
      </div>
    </div>,
    document.body,
  );
}

interface SourceFolderMenuProps {
  index: number;
  currentPath: string;
  wikiDir: string;
  anchorEl: HTMLElement | null;
  onSelect: (path: string) => void;
  onClear: () => void;
  onClose: () => void;
}

function SourceFolderMenu({
  index,
  currentPath,
  wikiDir,
  anchorEl,
  onSelect,
  onClear,
  onClose,
}: SourceFolderMenuProps) {
  const menuRef = useRef<HTMLDivElement>(null);
  const [browse, setBrowse] = useState<WikiBrowseResult | null>(null);
  const [pathDraft, setPathDraft] = useState(currentPath);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [position, setPosition] = useState<{
    left: number;
    top: number;
    width: number;
  } | null>(null);

  async function loadBrowse(path?: string) {
    setLoading(true);
    setError(null);
    try {
      const data = await api.browseWikiSources(path);
      setBrowse(data);
      setPathDraft(data.path);
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    void loadBrowse(currentPath || wikiDir || undefined);
  }, [currentPath, wikiDir]);

  function updatePosition() {
    if (!anchorEl) return;
    const rect = anchorEl.getBoundingClientRect();
    const width = Math.max(rect.width, 320);
    const left = Math.min(
      Math.max(8, rect.left),
      window.innerWidth - width - 8,
    );
    const top = Math.min(rect.bottom + 6, window.innerHeight - 360);
    setPosition({ left, top, width });
  }

  useLayoutEffect(() => {
    updatePosition();
  }, [anchorEl]);

  useEffect(() => {
    if (!anchorEl) return;
    updatePosition();
    window.addEventListener("resize", updatePosition);
    window.addEventListener("scroll", updatePosition, true);

    function onPointerDown(e: MouseEvent) {
      const target = e.target as Node;
      if (menuRef.current?.contains(target)) return;
      if (anchorEl?.contains(target)) return;
      onClose();
    }

    document.addEventListener("mousedown", onPointerDown);
    return () => {
      window.removeEventListener("resize", updatePosition);
      window.removeEventListener("scroll", updatePosition, true);
      document.removeEventListener("mousedown", onPointerDown);
    };
  }, [anchorEl, onClose]);

  if (!position) return null;

  return createPortal(
    <div
      ref={menuRef}
      className="wiki-source-menu"
      role="dialog"
      aria-label={`Source ${index + 1} 폴더 선택`}
      style={{
        left: position.left,
        top: position.top,
        width: position.width,
      }}
    >
      <div className="wiki-source-menu-header">Source {index + 1}</div>
      <div className="wiki-source-menu-shortcuts">
        {(browse?.shortcuts || []).map((item) => (
          <button
            key={item.path}
            type="button"
            className="wiki-source-menu-chip"
            onClick={() => void loadBrowse(item.path)}
          >
            {item.name}
          </button>
        ))}
      </div>
      <div className="wiki-source-menu-pathrow">
        <input
          type="text"
          value={pathDraft}
          placeholder="폴더 경로"
          autoComplete="off"
          onChange={(e) => setPathDraft(e.target.value)}
          onKeyDown={(e) => {
            if (e.key === "Enter") {
              e.preventDefault();
              void loadBrowse(pathDraft.trim());
            }
          }}
        />
        <button
          type="button"
          className="modal-btn-secondary"
          onClick={() => void loadBrowse(pathDraft.trim())}
        >
          이동
        </button>
      </div>
      {error ? (
        <p className="modal-error" role="alert">
          {error}
        </p>
      ) : null}
      <div className="wiki-source-menu-list">
        {loading ? (
          <div className="wiki-source-menu-empty">불러오는 중…</div>
        ) : (
          <>
            {browse?.parent ? (
              <button
                type="button"
                className="wiki-source-menu-item"
                onClick={() => void loadBrowse(browse.parent || undefined)}
              >
                ← ..
              </button>
            ) : null}
            {(browse?.dirs || []).length === 0 ? (
              <div className="wiki-source-menu-empty">하위 폴더가 없습니다.</div>
            ) : (
              browse?.dirs.map((dir) => (
                <button
                  key={dir.path}
                  type="button"
                  className="wiki-source-menu-item"
                  onClick={() => void loadBrowse(dir.path)}
                >
                  {dir.name}/
                </button>
              ))
            )}
          </>
        )}
      </div>
      <div className="wiki-source-menu-actions">
        <button type="button" className="modal-btn-secondary" onClick={onClear}>
          비우기
        </button>
        <button
          type="button"
          className="modal-btn-primary"
          disabled={!browse?.path}
          onClick={() => {
            if (browse?.path) onSelect(browse.path);
          }}
        >
          이 폴더 선택
        </button>
      </div>
    </div>,
    document.body,
  );
}
