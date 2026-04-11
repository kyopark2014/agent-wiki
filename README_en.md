# Agent Wiki


**Andrej Karpathy**, co-founder of OpenAI and former AI lead at Tesla, proposed a method of querying data using an LLM Wiki locally with structured Markdown. This approach enables querying various local data as a Graph without the need for RAG or vector databases.

### Core Loop

```
Raw data ingestion → LLM compiles & maintains wiki → Query → Output saved back to wiki → Compound knowledge accumulation
```

| Item | Description |
|------|-------------|
| Storage Format | Structured **Markdown files** (Obsidian) |
| Infrastructure | No RAG pipeline, no vector DB |
| Automation | Auto-maintained index, summaries, and backlinks between topics |
| Linting | Detects inconsistencies, automatically discovers gaps requiring new articles |
| Output Formats | Markdown reports, Marp slides, Matplotlib charts |
| Long-term Vision | Synthetic data generation + fine-tuning → Internalize corpus into model weights |



## ⚖️ LLM Wiki vs RAG — When to Use Which?

| **LLM Wiki is better when** | **RAG is better when** |
|---|---|
| Complex questions spanning multiple documents | Large-scale data that changes in real-time |
| Deep understanding and synthesis are required | Simple fact lookups |
| Expert-curated corpus | Source provenance tracking is important |
| Questions requiring structural reasoning | Rapid deployment is needed |

> 💡 **Key Analogy**: RAG is a database query, LLM Wiki is a second brain — they're not competitors but complementary!

## graphify

graphify is a [skill that transforms folders containing code, documents, papers, images, videos, and YouTube links into a queryable knowledge graph](https://github.com/safishamsi/graphify) with a single `/graphify` command. graphify is a tool that practically implements Karpathy's `/raw` folder idea — a powerful open-source project that turns any folder into a queryable knowledge graph with just one command.

```text
graphify-out/
├── graph.html       # Interactive graph (click nodes, search, filter by community)
├── GRAPH_REPORT.md  # God nodes, surprising connections, suggested questions
├── graph.json       # Persistent graph (re-queryable even weeks later)
└── cache/           # SHA256 cache (only reprocesses changed files)
```

Installation instructions are as follows:

```text
pip install graphifyy && graphify install
/graphify .   # Run on the current folder
```

## How to Search

### 1️⃣ `/graphify query` - Search by Question

The most basic search method. Ask a question in natural language and it will traverse the graph to provide an answer.

```bash
# Default BFS traversal (broad search - "What is X connected to?")
/graphify query "How does RAG work?"

# DFS traversal (deep search - "How does X connect to Y?")
/graphify query "How does the auth module connect to the database?" --dfs

# Token budget limit (default 2000)
/graphify query "What is transformer architecture?" --budget 1500
```

| Mode | Characteristics | Best For |
|------|----------------|----------|
| **BFS** (default) | Broad traversal, starting from nearest nodes | "What is X?", "What is connected to X?" |
| **DFS** (`--dfs`) | Deep traversal, traces specific paths | "How does X connect to Y?" |


### 2️⃣ `/graphify path` - Find the Shortest Path Between Two Concepts

Finds the connection path between two nodes.

```bash
/graphify path "AuthModule" "Database"
/graphify path "RAG" "LLM"
```


### 3️⃣ `/graphify explain` - Explain a Specific Concept

Shows a detailed explanation and connections for a specific node (concept).

```bash
/graphify explain "SwinTransformer"
/graphify explain "RAG"
```

## Execution Results

Running `/graphify contents/` generates a graph from the files in the contents folder, as shown below.

<img width="723" height="510" alt="image" src="https://github.com/user-attachments/assets/366be416-3179-4072-bb2e-981b7b4e50ea" />

Then, asking a question like `/graphify query "How to transition from RAG to LLM Wiki?"` queries the graph as shown below.

<img width="728" height="667" alt="image" src="https://github.com/user-attachments/assets/b99ba277-445c-47ee-80a6-6a20d4b1dbd9" />

Ultimately, you can obtain results like the following.

<img width="676" height="762" alt="image" src="https://github.com/user-attachments/assets/d0fea24b-e907-4c60-a1f0-4cee72c45a23" />

The generated graph looks like this:

<img width="866" height="900" alt="image" src="https://github.com/user-attachments/assets/60a895a4-3cd6-460c-809e-8ac919e59b67" />


## Reference

[RAG Is Not Enough. Karpathy Just Showed Us What Comes Next.](./contents/rag_vs_llm_wiki_summary.md)

[What Karpathy's Second Brain Looks Like Inside a Real Business](./contents/karpathy_second_brain_in_business_summary.md)

[Andrej Karpathy let an agent run overnight on his own model.](./contents/karpathy_autoresearch_overnight_summary.md)

[Karpathy on AI Coding Agents](./contents/karpathy_ai_coding_agents_summary.md)

[Andrej Karpathy Just Redefined the "Second Brain", and It Has Massive Implications for Enterprise Innovation.](./contents/karpathy_second_brain_enterprise_summary.md)

[Karpathy's viral LLM Knowledge Base blueprint](./contents/karpathy_viral_llm_knowledge_base_blueprint_summary.md)

[safishamsi / graphify](https://github.com/safishamsi/graphify)
