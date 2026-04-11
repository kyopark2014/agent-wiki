# Graph Report - contents  (2026-04-11)

## Corpus Check
- Corpus is ~3,413 words - fits in a single context window. You may not need a graph.

## Summary
- 36 nodes · 44 edges · 7 communities detected
- Extraction: 75% EXTRACTED · 25% INFERRED · 0% AMBIGUOUS · INFERRED: 11 edges (avg confidence: 0.84)
- Token cost: 4,200 input · 1,800 output

## God Nodes (most connected - your core abstractions)
1. `Andrej Karpathy` - 7 edges
2. `Second Brain (세컨드 브레인)` - 5 edges
3. `LLM 지식 베이스 (LLM Knowledge Base)` - 5 edges
4. `Second Brain 재정의 (Second Brain Redefined)` - 5 edges
5. `LLM 지식 베이스 블루프린트 (LLM KB Blueprint)` - 5 edges
6. `에이전트 워크플로우 (Agent Workflow)` - 4 edges
7. `밤새 실행 에이전트 (Overnight Agent)` - 4 edges
8. `LLM Wiki (LLM 위키)` - 4 edges
9. `인간의 역할 변화 (Human Role Shift)` - 3 edges
10. `인간이 병목이 되는 문제 (Human Bottleneck)` - 3 edges

## Surprising Connections (you probably didn't know these)
- `에이전틱 루프 (Agentic Loop)` --semantically_similar_to--> `에이전트 워크플로우 (Agent Workflow)`  [INFERRED] [semantically similar]
  contents/karpathy_autoresearch_overnight_summary.md → contents/karpathy_ai_coding_agents_summary.md
- `인간이 병목이 되는 문제 (Human Bottleneck)` --semantically_similar_to--> `인간의 역할 변화 (Human Role Shift)`  [INFERRED] [semantically similar]
  contents/karpathy_autoresearch_overnight_summary.md → contents/karpathy_ai_coding_agents_summary.md
- `컨텍스트 주입 (Context Injection)` --semantically_similar_to--> `컨텍스트 윈도우 (Context Window)`  [INFERRED] [semantically similar]
  contents/karpathy_viral_llm_knowledge_base_blueprint_summary.md → contents/karpathy_ai_coding_agents_summary.md
- `LLM Wiki (LLM 위키)` --semantically_similar_to--> `LLM 지식 베이스 (LLM Knowledge Base)`  [INFERRED] [semantically similar]
  contents/rag_vs_llm_wiki_summary.md → contents/karpathy_second_brain_in_business_summary.md
- `지식 합성 (Knowledge Synthesis)` --semantically_similar_to--> `구조화된 지식 시스템 (Structured Knowledge System)`  [INFERRED] [semantically similar]
  contents/rag_vs_llm_wiki_summary.md → contents/karpathy_viral_llm_knowledge_base_blueprint_summary.md

## Hyperedges (group relationships)
- **Karpathy 지식 생태계 (Knowledge Ecosystem)** — second_brain_biz_llm_knowledge_base, blueprint_llm_kb_blueprint, rag_llm_wiki, second_brain_biz_raw_folder, blueprint_raw_folder [EXTRACTED 0.90]
- **자율 에이전트 패러다임 (Autonomous Agent Paradigm)** — autoresearch_overnight_agent, autoresearch_agentic_loop, ai_coding_agents_agent_workflow, autoresearch_autonomous_research, autoresearch_trust_delegation [INFERRED 0.85]
- **엔터프라이즈 지식 변환 (Enterprise Knowledge Transformation)** — enterprise_second_brain_redef, enterprise_innovation, enterprise_ai_transformation, enterprise_knowledge_management, second_brain_biz_institutional_memory [INFERRED 0.80]

## Communities

### Community 0 - "LLM 지식 베이스 & 블루프린트"
Cohesion: 0.33
Nodes (7): 컨텍스트 주입 (Context Injection), LLM 지식 베이스 블루프린트 (LLM KB Blueprint), /raw 폴더 시스템 (/raw Folder System), 구조화된 지식 시스템 (Structured Knowledge System), 지식 그래프 (Knowledge Graph), LLM 지식 베이스 (LLM Knowledge Base), /raw 폴더 워크플로우 (/raw Folder Workflow)

### Community 1 - "엔터프라이즈 혁신 & 변환"
Cohesion: 0.38
Nodes (7): AI 기반 조직 변환 (AI-Driven Org Transformation), 엔터프라이즈 혁신 (Enterprise Innovation), 지식 관리 혁신 (Knowledge Management Innovation), Second Brain 재정의 (Second Brain Redefined), 비즈니스 적용 사례 (Business Application), 기업 기억 (Institutional Memory), Second Brain (세컨드 브레인)

### Community 2 - "자율 에이전트 & 밤새 연구"
Cohesion: 0.33
Nodes (6): 에이전틱 루프 (Agentic Loop), 자율 연구 (Autonomous Research), 인간이 병목이 되는 문제 (Human Bottleneck), LLM 모델 자기 연구 (LLM Self-Research), 밤새 실행 에이전트 (Overnight Agent), 신뢰와 위임 (Trust & Delegation)

### Community 3 - "AI 코딩 에이전트 워크플로우"
Cohesion: 0.4
Nodes (5): 에이전트 워크플로우 (Agent Workflow), 컨텍스트 윈도우 (Context Window), 환각 문제 (Hallucination), 인간의 역할 변화 (Human Role Shift), 소프트웨어 엔지니어 역할 재정의

### Community 4 - "RAG vs LLM Wiki"
Cohesion: 0.4
Nodes (5): 지식 합성 (Knowledge Synthesis), LLM Wiki (LLM 위키), AI의 다음 단계 (Next Step in AI), RAG의 한계 (RAG Limitations), 검색 vs 합성 (Retrieval vs Synthesis)

### Community 5 - "Karpathy & 바이브 코딩"
Cohesion: 0.5
Nodes (4): 새로운 추상화 레벨 (New Abstraction Level), AI 사이코시스 (AI Psychosis), Andrej Karpathy, 바이브 코딩 (Vibe Coding)

### Community 6 - "바이럴 커뮤니티 반응"
Cohesion: 1.0
Nodes (2): AI 커뮤니티 반응 (AI Community Reaction), 바이럴 X 포스트 (Viral X Post)

## Knowledge Gaps
- **10 isolated node(s):** `새로운 추상화 레벨 (New Abstraction Level)`, `소프트웨어 엔지니어 역할 재정의`, `LLM 모델 자기 연구 (LLM Self-Research)`, `신뢰와 위임 (Trust & Delegation)`, `지식 그래프 (Knowledge Graph)` (+5 more)
  These have ≤1 connection - possible missing edges or undocumented components.
- **Thin community `바이럴 커뮤니티 반응`** (2 nodes): `AI 커뮤니티 반응 (AI Community Reaction)`, `바이럴 X 포스트 (Viral X Post)`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.

## Suggested Questions
_Questions this graph is uniquely positioned to answer:_

- **Why does `Andrej Karpathy` connect `Karpathy & 바이브 코딩` to `LLM 지식 베이스 & 블루프린트`, `엔터프라이즈 혁신 & 변환`, `자율 에이전트 & 밤새 연구`, `RAG vs LLM Wiki`?**
  _High betweenness centrality (0.523) - this node is a cross-community bridge._
- **Why does `밤새 실행 에이전트 (Overnight Agent)` connect `자율 에이전트 & 밤새 연구` to `Karpathy & 바이브 코딩`?**
  _High betweenness centrality (0.265) - this node is a cross-community bridge._
- **Why does `LLM 지식 베이스 블루프린트 (LLM KB Blueprint)` connect `LLM 지식 베이스 & 블루프린트` to `Karpathy & 바이브 코딩`?**
  _High betweenness centrality (0.223) - this node is a cross-community bridge._
- **Are the 2 inferred relationships involving `LLM 지식 베이스 (LLM Knowledge Base)` (e.g. with `LLM 지식 베이스 블루프린트 (LLM KB Blueprint)` and `LLM Wiki (LLM 위키)`) actually correct?**
  _`LLM 지식 베이스 (LLM Knowledge Base)` has 2 INFERRED edges - model-reasoned connections that need verification._
- **What connects `새로운 추상화 레벨 (New Abstraction Level)`, `소프트웨어 엔지니어 역할 재정의`, `LLM 모델 자기 연구 (LLM Self-Research)` to the rest of the system?**
  _10 weakly-connected nodes found - possible documentation gaps or missing edges._