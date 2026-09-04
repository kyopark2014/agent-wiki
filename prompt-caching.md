# Prompt Caching

LangGraph 에이전트는 tool loop마다 동일한 **system prompt + tool schema**를 Bedrock에 다시 보냅니다. [Amazon Bedrock prompt caching](https://docs.aws.amazon.com/bedrock/latest/userguide/prompt-caching.html)을 켜서 이 정적 prefix를 재사용합니다. 구현은 [`runtime_agent/langgraph/langgraph_agent.py`](./runtime_agent/langgraph/langgraph_agent.py)의 `call_model`에 있습니다.

공식 `BedrockPromptCachingMiddleware`는 LangChain Agents middleware 전용이라, 이 프로젝트의 커스텀 `StateGraph` + `call_model`에는 그대로 붙일 수 없습니다. 동일 효과를 `call_model`에서 직접 재현합니다.

## 대상 모델

| 경로 | model_type | 모델 예 | 캐싱 방식 |
|------|------------|---------|-----------|
| **Claude / Nova** | `claude`, `nova` | `us.anthropic.claude-sonnet-5` | Explicit (`cache_control`) |
| **GPT 5.6+ (Mantle)** | `openai` | `openai.gpt-5.6-sol`, `-terra`, `-luna` | Explicit (`prompt_cache_breakpoint`) |
| **GPT 5.5 이하 (Mantle)** | `openai` | `openai.gpt-5.5`, `openai.gpt-5.4` | Implicit (AWS 자동, 코드 미적용) |

GPT 5.6+는 Mantle Responses API(`mantle_api: "responses"`)에서 explicit caching을 사용합니다. GPT 5.5/5.4는 AWS가 implicit caching을 자동 적용하지만, agent tool loop에서는 hit rate가 낮을 수 있어 별도 마커를 붙이지 않습니다.

---

## Claude / Nova (Bedrock Converse)

### 적용 방식

1. **Plain SystemMessage** — system에 Anthropic-format `cache_control`을 붙이지 **않습니다**.
   (`ChatBedrock`가 system의 `ttl`을 제거하고 `5m` 기본값으로 두면, last-message `1h`와 충돌해 `ValidationException`이 납니다.)
2. **`model.bind(cache_control=PROMPT_CACHE_CONTROL)`** — TTL **`1h`** 로 last-message(및 Converse의 tools/system) breakpoint를 맞춥니다.
3. **관측** — 응답 `usage_metadata.input_token_details`의 `cache_read` / `cache_creation`을 로그합니다.

```python
# langgraph_agent.py
PROMPT_CACHE_CONTROL = {"type": "ephemeral", "ttl": "1h"}


def _supports_bedrock_prompt_caching(model_type: str | None) -> bool:
    return model_type in ("claude", "nova")


def _system_message_with_bedrock_cache(system: str) -> SystemMessage:
    # No embedded cache_control — bind() alone owns the 1h breakpoint(s).
    return SystemMessage(content=system)
```

`call_model`에서의 사용:

```python
model = chatModel.bind_tools(tools) if tools else chatModel
if use_bedrock_cache:
    model = model.bind(cache_control=PROMPT_CACHE_CONTROL)
    system_msg = _system_message_with_bedrock_cache(system)
```

| Wrapper | cache 동작 |
|---------|------------|
| `ChatBedrock` (기본 Claude, Guardrail 없음) | last message `cache_control` ttl=`1h` → prefix(system/tools 포함) 캐시 |
| `ChatBedrockConverse` (Guardrail 활성) | `bind` 시 system / tools / last message에 `cachePoint` ttl=`1h` 삽입 |

### 특성

- TTL: **1시간** (`ephemeral`, tools/system/messages 동일)
- 최소 prefix: 모델별 512~4,096 tokens (대부분 skill XML + tool schema는 임계치 초과)
- tool loop **2번째 LLM 호출부터** `cache_read` 발생이 일반적
- 스트리밍 usage 파싱: [`bedrock_stream_usage_patch.py`](./runtime_agent/langgraph/bedrock_stream_usage_patch.py)

---

## GPT 5.6+ (Mantle Responses API)

### 적용 방식

Agent tool loop에서는 implicit mode(마지막 메시지에 자동 breakpoint)보다 **explicit mode**가 적합합니다. system prompt 끝에 breakpoint를 두면, 이후 턴은 고정 prefix를 cache read하고 변하는 대화만 처리합니다.

1. **SystemMessage explicit breakpoint** — content block에 `prompt_cache_breakpoint: {"mode": "explicit"}` 추가
2. **`model.bind(prompt_cache_key=..., prompt_cache_options=...)`** — 세션·tool set별 stable cache key + explicit mode
3. **관측** — LangChain이 `cached_tokens` → `cache_read`, `cache_write_tokens` → `cache_creation`으로 매핑

```python
# runtime_agent/langgraph/langgraph_agent.py
GPT_PROMPT_CACHE_OPTIONS = {"mode": "explicit", "ttl": "30m"}


def _supports_gpt_explicit_caching(model_type: str | None, model_id: str | None) -> bool:
    # openai.gpt-5.6+ → True (5.7, 6.0 등 미래 모델 포함)
    ...


def _system_message_with_gpt_cache(system: str) -> SystemMessage:
    return SystemMessage(
        content=[
            {
                "type": "text",
                "text": system,
                "prompt_cache_breakpoint": {"mode": "explicit"},
            }
        ]
    )
```

`call_model`에서의 사용:

```python
elif use_gpt_cache:
    model = model.bind(
        prompt_cache_key=_gpt_prompt_cache_key(config, tools),
        prompt_cache_options=GPT_PROMPT_CACHE_OPTIONS,
    )
    system_msg = _system_message_with_gpt_cache(system)
```

`prompt_cache_key` 형식: `{projectName}:{thread_id}:{tools_digest}`  
(`thread_id` = `runtime_session_id`, tools_digest = tool name 목록 SHA256 앞 12자)

### 특성

| 항목 | 값 |
|------|-----|
| API | Mantle Responses (`https://bedrock-mantle.{region}.api.aws/openai/v1`) |
| TTL | **30분** (기본) |
| 최소 prefix | **1,024 tokens** per breakpoint |
| cache read 할인 | uncached input 대비 **90%** |
| cache write 비용 | uncached input의 **1.25×** |
| breakpoint 최대 | 4개 (현재 system 1개 사용) |

### GPT 5.5 / 5.4 (implicit only)

AWS 문서상 별도 파라미터 없이 implicit caching이 자동 적용됩니다. cache write 비용은 없고, read만 할인됩니다. agent loop hit rate는 GPT 5.6 explicit보다 예측하기 어렵습니다.

---

## 측정 (`test_prompt_caching.py`)

실제 skill system prompt + builtin/skill tools로 **2-step tool loop**를 재현합니다.

```bash
cd runtime_agent/langgraph

# Claude (기본)
python test_prompt_caching.py

# GPT 5.6 Mantle
python test_prompt_caching.py --model-id openai.gpt-5.6-sol --region us-east-2
```

성공 기준: call1 `cache_creation > 0`, call2 `cache_read > 0`

### Claude 측정 결과 (참고)

| 항목 | 값 |
|------|-----|
| 모델 | `us.anthropic.claude-sonnet-5` (`us-west-2`) |
| Skills | skill-creator, pptx, xlsx, myslide, docx, pdf, frontend-design |
| System prompt | 5,513 chars (~1.4K tokens 추정) |
| Tools | 8 |

| 호출 | input | cache_creation | cache_read | output | hit ratio |
|------|------:|---------------:|-----------:|-------:|----------:|
| Call 1 | 2 | **4,293** | 0 | 56 | 0% |
| Call 2 | 2 | 66 | **4,293** | 32 | **98.4%** |

**전체 input token 절감률 (2-call): 49.6%**

```text
reduction_% = sum(cache_read) / sum(input + cache_creation + cache_read)
            = 4293 / 8656 ≈ 49.6%
```

---

## 확인 방법

1. 위 probe 스크립트 실행, 또는 해당 모델로 tool을 2회 이상 쓰는 질의 실행
2. stdout의 `input token reduction: XX.X%` 또는 로그의 `cache_read` / `cache_creation` 확인
3. CloudWatch: `CacheReadTokens`, `CacheCreationTokens`, `CacheHitRatio` ([`cloudwatch_metrics.py`](./runtime_agent/langgraph/cloudwatch_metrics.py))

## 의도적으로 하지 않은 것

- LangChain Agents + `BedrockPromptCachingMiddleware`로 전체 이전
- 기본 LLM 경로를 `ChatBedrockConverse`로 강제 전환
- skill 본문(`SKILL.md`)을 system에 넣는 구조 변경 (이미 `get_skill_instructions` tool로 로드)
- GPT 5.5/5.4에 explicit breakpoint 적용 (AWS implicit 전용)

## 참고

- [Prompt caching (AWS)](https://docs.aws.amazon.com/bedrock/latest/userguide/prompt-caching.html)
- [GPT-5.6 explicit caching (AWS Blog)](https://aws.amazon.com/blogs/machine-learning/introducing-explicit-prompt-caching-for-openai-gpt-5-6-models-on-amazon-bedrock/)
- [LangChain ChatOpenAI prompt caching](https://reference.langchain.com/python/langchain-openai/ChatOpenAI)
