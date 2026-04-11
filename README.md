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

## Reference

[RAG Is Not Enough. Karpathy Just Showed Us What Comes Next.](./contents/rag_vs_llm_wiki_summary.md)

[What Karpathy’s Second Brain Looks Like Inside a Real Business](./contents/karpathy_second_brain_in_business_summary.md)

[Andrej Karpathy let an agent run overnight on his own model.](./contents/karpathy_autoresearch_overnight_summary.md)

[Karpathy on AI Coding Agents](./contents/karpathy_ai_coding_agents_summary.md)

[Andrej Karpathy Just Redefined the "Second Brain", and It Has Massive Implications for Enterprise Innovation.](./contents/karpathy_second_brain_enterprise_summary.md)

[Karpathy's viral LLM Knowledge Base blueprint](./contents/karpathy_viral_llm_knowledge_base_blueprint_summary.md)

[safishamsi / graphify](https://github.com/safishamsi/graphify)
