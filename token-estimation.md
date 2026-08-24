# PDF 페이지 이미지 토큰 추정

Wiki Sync Foundation Model Parser는 PDF를 페이지 PNG로 렌더한 뒤 vision LLM으로 Markdown을 뽑고, 그 텍스트로 그래프를 추출한다. 이 문서는 **비전 토큰 공식**, **agent-wiki의 DPI/축소 규칙**, **`error_code.pdf` 1페이지 실측**을 정리한다.

관련 문서: `graph-pipeline.md`(파이프라인), `graph/pdf2text.py`, `application/mcp_server_text_extraction.py`.

---

## 한 페이지에서 토큰이 나가는 두 단계

Wiki Sync가 Foundation Model Parser를 켜면, PDF 한 페이지당 LLM 호출이 **두 번**이다.

```text
PDF page
  → PNG (DPI 150, PyMuPDF)
  → 필요 시 축소 (_prepare_image_base64)
  → [1] Claude 5.0 Sonnet  vision  → Markdown     ← 이미지 토큰
  → [2] Claude Haiku 4.5   text    → nodes/edges  ← 텍스트 토큰
```

그래프 LLM은 PNG를 보지 않는다. 이미지 토큰은 **1단계(페이지 → Markdown)** 에만 붙는다.

| 단계 | 모델 (실측 시점) | 입력 | 과금 단위 |
|---|---|---|---|
| 1. 이미지 → Markdown | `us.anthropic.claude-sonnet-5` | PNG + 추출 프롬프트 | **비전 패치 + 텍스트** |
| 2. Markdown → 그래프 | `us.anthropic.claude-haiku-4-5-20251001-v1:0` | EXTRACT 시스템 프롬프트 + 페이지 Markdown | **텍스트만** |

---

## 비전 토큰 공식

최신 GPT / Claude vision은 **고정 픽셀 면적 ÷ N** 이 아니라, 이미지를 격자 패치로 덮고 패치 1개 = 토큰 1개다. 변 길이가 패치 크기의 배수가 아니면 `ceil` 때문에 토큰이 조금 더 나온다.

| 모델 | 패치 | 공식 | 패치 1개 픽셀 | 비고 |
|---|---|---|---|---|
| **GPT-5.6 Sol** | 32×32 | `ceil(W/32) × ceil(H/32)` | 1024 | `detail=original`/`auto`면 원본 해상도 그대로 |
| **Claude (Opus 4.8, Sonnet 5 등)** | 28×28 | `ceil(W/28) × ceil(H/28)` | 784 | Anthropic 현재 공식 |
| 예전 Claude 근사 | — | `(W × H) / 750` | ~750 | 784에 맞춘 반올림. 패치 공식과 수 % 차이 |

같은 해상도면 패치가 더 작은 Claude 쪽이 비전 토큰이 더 많다. 예: 1024×1024 → GPT 1024, Claude 1369.

문서:

- OpenAI [Images and vision](https://developers.openai.com/api/docs/guides/images-vision) — GPT-5.6 패치 토큰화
- Anthropic [Vision](https://platform.claude.com/docs/en/build-with-claude/vision) — `ceil(W/28)×ceil(H/28)`

`1 token = 1024 pixels`(GPT) / `784 pixels`(Claude)는 **변 길이가 패치 배수일 때만** 정확하다.

---

## agent-wiki가 실제로 만드는 이미지 크기

고정 해상도(예: 1024×1024)로 맞추지 않는다. **렌더 DPI**와 **픽셀/용량 한도**만 있다.

### 렌더: DPI 150

`graph/pdf2text.py` `pdf_to_images()` 기본값 `dpi=150`. Wiki Sync도 DPI를 넘기지 않는다.

```text
zoom = 150 / 72 ≈ 2.083
픽셀 가로 = PDF 포인트 가로 × zoom
```

US Letter(612×792 pt)면 약 **1275×1650**. A4(595×842 pt)면 약 **1240×1754**.

### 축소: `_prepare_image_base64`

LLM에 넣기 직전 `application/mcp_server_text_extraction.py`가 한도에 걸릴 때만 비율을 유지한 채 줄인다.

| 한도 | 값 | 동작 |
|---|---|---|
| `max_pixels` | **2,000,000** | 넘으면 가로·세로를 **1/2**로. 될 때까지 반복 |
| `max_size` | **5MB** (base64 바이트) | 넘으면 가로·세로를 **0.8배**. 최대 5번 |

목표 한 변 길이는 없다. Letter 150 DPI는 2,103,750픽셀이라 **한 번 반으로** 줄어 **637×825**가 된다. PNG가 작으면 5MB 한도는 타지 않는다.

---

## 실측: `error_code.pdf` 1페이지

입력: `.session_storage/ksdyb/wiki/raw/error_code.pdf`  
문서: US Letter, **4페이지**. 아래는 **1페이지만**.

### 이미지

| | 값 |
|---|---|
| 렌더 PNG | 1275×1650 (2,103,750 px, 약 110 KB) |
| LLM에 넣은 PNG | **637×825** (525,525 px, 약 81 KB) |
| 축소 이유 | 2M 픽셀 초과 → `/2` 1회. 5MB는 미적용 |

### 이론 비전 토큰 (축소 후 637×825)

| 방식 | 계산 | 결과 |
|---|---|---|
| Claude 28×28 | `ceil(637/28)×ceil(825/28)` = 23×30 | **690** |
| GPT 32×32 | `ceil(637/32)×ceil(825/32)` = 20×26 | **520** |
| 예전 `/750` | 525,525 / 750 | **701** |

### Bedrock 실제 usage (2026-08-24)

**1단계 — 이미지 → Markdown** (`claude-sonnet-5`, `us-west-2`)

| | 토큰 |
|---|---|
| input | **1,003** |
| output | **579** |
| total | **1,582** |
| cache read | 0 |

분해: 비전 패치 **690** + 추출 프롬프트/오버헤드 **약 313** ≈ 실측 input **1,003**.  
28×28 공식이 실측과 맞다. `/750`(701)도 가깝고, 32×32(520)는 이 이미지에서 약 25% 적다.

Markdown은 약 704자(보일러 에러코드 목록).

**2단계 — Markdown → 그래프** (`claude-haiku-4-5`, Converse `usage` 직접 확인)

| | 토큰 |
|---|---|
| input | **1,238** |
| output | **6,132** |
| total | **7,370** |

산출: 노드 23, 엣지 27, 하이퍼엣지 3. output이 큰 이유는 추출 JSON이 길기 때문이다.

> `lib/semantic.py`가 돌려준 `input_tokens`/`output_tokens`는 0이었다. 스키마에 `"input_tokens":0`이 들어 있어 `setdefault`가 Bedrock usage를 덮지 못한다. 위 수치는 Converse `usage`를 읽은 값이다.

### 1페이지 합계

| | 토큰 |
|---|---|
| input | **2,241** (비전 1,003 + 그래프 1,238) |
| output | **6,711** (비전 579 + 그래프 6,132) |
| 전체 | **8,952** |

---

## 동일 테스트: GPT-5.6 Sol vs Opus 4.8

같은 `error_code.pdf` 1페이지 PNG(637×825)로, 두 단계 모두 해당 모델만 썼다.  
Bedrock Converse `usage` (2026-08-24, `us-west-2`).

| 모델 | Bedrock ID | 단가 (input / output, $ / 1M) |
|---|---|---|
| GPT-5.6 Sol | `us.openai.gpt-5.6-sol` | **$4 / $20** |
| Opus 4.8 Standard | `us.anthropic.claude-opus-4-8` | **$5 / $25** |

비용 식: `input/1e6 × 단가_in + output/1e6 × 단가_out`.  
GPT는 on-demand 모델 ID(`openai.gpt-5.6-sol`)가 아니라 **inference profile** `us.openai.gpt-5.6-sol`이 필요하다.

### 1단계 — 이미지 → Markdown

| | GPT-5.6 Sol | Opus 4.8 |
|---|---|---|
| 이론 비전 패치 | 32×32 → **520** | 28×28 → **690** |
| 실제 input | **831** | **1,003** |
| 실제 output | **910** | **579** |
| 추정 텍스트(input − 패치) | 831 − 520 = **311** | 1,003 − 690 = **313** |
| Markdown 글자 수 | 725 | 660 |
| 비용 | **$0.0215** | **$0.0195** |

비전 패치 공식은 두 모델 모두 실측과 맞다. 프롬프트 텍스트는 약 310토큰으로 같다. GPT는 비전 input이 172토큰 적고, Markdown을 더 길게 써서 output이 더 많다. 그 결과 **비전 단계 비용은 GPT가 약간 더 높다**.

### 2단계 — Markdown → 그래프

| | GPT-5.6 Sol | Opus 4.8 |
|---|---|---|
| input | **930** | **1,438** |
| output | **5,315** | **4,436** |
| total | 6,245 | 5,874 |
| 비용 | **$0.1100** | **$0.1181** |

Opus는 EXTRACT 시스템 프롬프트 때문에 그래프 input이 더 크다. GPT는 JSON을 더 길게 써서 output이 더 많다.

### 1페이지 합계 (비전 + 그래프)

| | GPT-5.6 Sol | Opus 4.8 |
|---|---|---|
| input | 1,761 | 2,441 |
| output | 6,225 | 5,015 |
| 전체 토큰 | **7,986** | **7,456** |
| **비용** | **$0.1315** | **$0.1376** |

이 페이지에서는 Opus가 토큰은 적고, 단가가 높아 **비용은 GPT보다 약 $0.006(약 4.6%) 더 나온다**. 비전만 보면 Opus가 더 싸고($0.0195 vs $0.0215), 합치면 JSON output 때문에 역전된다.

4페이지가 1페이지와 비슷하면 대략 GPT **$0.53**, Opus **$0.55**. 본문이 긴 페이지는 그래프 output이 커져서 비용이 더 벌어진다.

---

## 다른 PDF를 어림잡는 방법

페이지마다 아래를 반복한다.

1. 렌더 크기: `(pdf_pt_w × 150/72) × (pdf_pt_h × 150/72)`
2. 2,000,000을 넘으면 가로·세로를 반으로 (필요하면 반복)
3. 비전 input ≈ `ceil(W/28)×ceil(H/28)` + **300~400** (현재 추출 프롬프트 기준)
4. 비전 output ≈ 페이지에서 뽑힌 Markdown 길이 (이 실측은 약 580)
5. 그래프 input ≈ EXTRACT 시스템 프롬프트 + Markdown
6. 그래프 output ≈ 노드/엣지 JSON 크기 (페이지 개념이 많으면 수천 토큰)

`error_code.pdf` 4페이지가 1페이지와 비슷하면 비전 input은 대략 **4,000** 근처. 2~3페이지는 본문이 더 길어서 그래프 output이 1페이지보다 클 수 있다. 페이지마다 밀도가 다르면 1페이지 값에 페이지 수를 곱하지 말고, 페이지별로 3~6을 적용한다.

같은 PNG를 GPT-5.6 Sol에 넣을 때의 비전 패치는 32×32다. 이 이미지(637×825)는 Claude **690** vs GPT **520**. 실측 input은 각각 **1,003** / **831** (패치 + 프롬프트 약 310).

---

## 코드 위치

| 항목 | 파일 |
|---|---|
| PDF → PNG (DPI 150) | `graph/pdf2text.py` `pdf_to_images()` |
| 픽셀/용량 축소 | `application/mcp_server_text_extraction.py` `_prepare_image_base64()` |
| 페이지 → Markdown 프롬프트 | `graph/pdf2text.py` `LLM_PROMPT` |
| 그래프 추출 프롬프트 | `graph/lib/semantic.py` `EXTRACT_SYSTEM` |
| Wiki Sync 호출 | `graph/sync_wiki.py` |


## 정리

GPT 5.6 Sol이 Opus 4.8에 비해 입력 토큰이 적게 필요하지만, Output 글자수가 많아서 전체적인 비용은 비슷합니다.
