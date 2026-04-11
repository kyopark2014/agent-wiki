# Agent Wiki


OpenAI 공동 창업자이자 Tesla 전 AI 리드인 **Andrej Karpathy**가 AI 커뮤니티를 멈추게 한 내용을 공유했다.

- 구조화된 Markdown
- 로컬 실행
- RAG/벡터DB 불필요

> **"LLM에게 질문하는 시대에서, LLM이 당신의 지식을 구축하고 유지하는 시대로."**


### 핵심 루프 (Core Loop)

```
원시 데이터 투입 → LLM이 위키 컴파일·유지 → 쿼리 → 출력물 다시 위키에 저장 → 지식 복리 축적
```

| 항목 | 내용 |
|------|------|
| 저장 형식 | 구조화된 **Markdown 파일** (Obsidian) |
| 인프라 | RAG 파이프라인 없음, 벡터 DB 없음 |
| 자동 기능 | 인덱스, 요약, 토픽 간 백링크 자동 유지 |
| 린팅(Linting) | 불일치 감지, 새 아티클 필요 갭 자동 발굴 |
| 출력 형식 | Markdown 리포트, Marp 슬라이드, Matplotlib 차트 |
| 장기 비전 | 합성 데이터 생성 + 파인튜닝 → 모델 가중치에 코퍼스 내재화 |



## ⚖️ LLM Wiki vs RAG — 언제 뭘 쓸까?

| **LLM Wiki가 유리한 경우** | **RAG가 유리한 경우** |
|---|---|
| 여러 문서를 넘나드는 복잡한 질문 | 실시간으로 변하는 대규모 데이터 |
| 깊은 이해와 합성이 필요할 때 | 단순 사실 조회 |
| 전문가가 직접 큐레이션한 코퍼스 | 출처(provenance) 추적이 중요할 때 |
| 구조적 추론이 필요한 질문 | 빠른 배포가 필요할 때 |

> 💡 **핵심 비유**: RAG는 데이터베이스 쿼리, LLM Wiki는 제2의 두뇌 — 경쟁 관계가 아니라 상호 보완 관계!

## graphify

코드, 문서, 논문, 이미지, 영상, YouTube 링크가 담긴 폴더를 /graphify 명령어 하나로 쿼리 가능한 지식 그래프로 변환하는 AI 코딩 어시스턴트 스킬입니다.

graphify는 Karpathy의 /raw 폴더 아이디어를 실제로 구현한 도구이며, 어떤 폴더든 명령어 하나로 쿼리 가능한 지식 그래프로 만들어주는 강력한 오픈소스 프로젝트입니다.

```text
graphify-out/
├── graph.html       # 인터랙티브 그래프 (노드 클릭, 검색, 커뮤니티 필터)
├── GRAPH_REPORT.md  # 갓 노드, 놀라운 연결, 추천 질문
├── graph.json       # 영구 그래프 (몇 주 후에도 재쿼리 가능)
└── cache/           # SHA256 캐시 (변경된 파일만 재처리)
```

```text
pip install graphifyy && graphify install
/graphify .   # 현재 폴더에 실행
```

## 검색하는 방법

### 1️⃣ `/graphify query` - 질문으로 검색

가장 기본적인 검색 방법입니다. 자연어로 질문하면 그래프를 탐색해서 답변해줍니다.

```bash
# 기본 BFS 탐색 (넓게 탐색 - "X는 무엇과 연결되어 있나?")
/graphify query "RAG는 어떻게 동작하나요?"

# DFS 탐색 (깊게 탐색 - "X에서 Y까지 어떻게 연결되나?")
/graphify query "인증 모듈이 데이터베이스에 어떻게 연결되나?" --dfs

# 토큰 예산 제한 (기본값 2000)
/graphify query "트랜스포머 아키텍처란?" --budget 1500
```

| 모드 | 특징 | 적합한 질문 |
|------|------|------------|
| **BFS** (기본) | 넓게 탐색, 가까운 노드부터 | "X는 무엇인가?", "X와 연결된 것은?" |
| **DFS** (`--dfs`) | 깊게 탐색, 특정 경로 추적 | "X에서 Y까지 어떻게 연결되나?" |

---

### 2️⃣ `/graphify path` - 두 개념 사이의 최단 경로 찾기

두 노드 사이의 연결 경로를 찾아줍니다.

```bash
/graphify path "AuthModule" "Database"
/graphify path "RAG" "LLM"
```

결과 예시:
```
Shortest path (3 hops):
  AuthModule --calls--> [EXTRACTED]
  TokenValidator --depends_on--> [INFERRED]
  Database
```

---

### 3️⃣ `/graphify explain` - 특정 개념 설명

특정 노드(개념)에 대한 상세 설명과 연결 관계를 보여줍니다.

```bash
/graphify explain "SwinTransformer"
/graphify explain "RAG"
```

결과 예시:
```
NODE: RAG
  source: docs/rag_overview.md
  degree: 12

CONNECTIONS:
  --references--> LLM [EXTRACTED]
  --uses--> VectorDB [EXTRACTED]
  --conceptually_related_to--> Fine-tuning [INFERRED]
```

---

## ⚠️ 검색 전 필수 조건

검색 명령어를 사용하려면 **먼저 그래프가 빌드되어 있어야 합니다!**

```bash
# 1. 먼저 그래프 빌드
/graphify <경로>

# 2. 그 다음 검색 가능
/graphify query "질문"
```

그래프가 없으면 이런 오류가 납니다:
```
ERROR: No graph found. Run /graphify <path> first to build the graph.
```

### 💡 검색 명령어 요약

| 목적 | 명령어 |
|------|--------|
| 개념에 대해 넓게 알고 싶을 때 | `query "질문"` |
| 특정 경로/의존성 추적 | `query "질문" --dfs` |
| 두 개념의 연결 관계 | `path "개념A" "개념B"` |
| 특정 개념 상세 설명 | `explain "개념명"` |


## Reference

[RAG Is Not Enough. Karpathy Just Showed Us What Comes Next.](./contents/rag_vs_llm_wiki_summary.md)

[What Karpathy’s Second Brain Looks Like Inside a Real Business](./contents/karpathy_second_brain_in_business_summary.md)

[Andrej Karpathy let an agent run overnight on his own model.](./contents/karpathy_autoresearch_overnight_summary.md)

[Karpathy on AI Coding Agents](./contents/karpathy_ai_coding_agents_summary.md)

[Andrej Karpathy Just Redefined the "Second Brain", and It Has Massive Implications for Enterprise Innovation.](./contents/karpathy_second_brain_enterprise_summary.md)

[Karpathy's viral LLM Knowledge Base blueprint](./contents/karpathy_viral_llm_knowledge_base_blueprint_summary.md)

[safishamsi / graphify](https://github.com/safishamsi/graphify)
