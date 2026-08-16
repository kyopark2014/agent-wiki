# Knowledge Graph


## 🌐 RDF / OWL 이란?

한 마디로 요약하면:
> **RDF = 데이터를 표현하는 방법 (문법)**
> **OWL = 개념 간 관계와 규칙을 정의하는 언어 (의미론)**

이 둘은 **시맨틱 웹(Semantic Web)** 기술 스택의 핵심이에요.

---

## 1️⃣ RDF (Resource Description Framework)

### 정의
- W3C 표준으로 **"웹상의 모든 것을 트리플(Triple)로 표현"** 하는 데이터 모델
- 1999년 처음 발표, 현재 RDF 1.1 (2014)

### 핵심 개념: 트리플 (Triple)
모든 정보를 딱 3가지로 표현해요:

```
주어(Subject) — 서술어(Predicate) — 목적어(Object)
```

| 주어 | 서술어 | 목적어 |
|---|---|---|
| 홍길동 | 근무한다 | AWS |
| AWS | 위치한다 | 서울 |
| 홍길동 | 직책이다 | 엔지니어 |

### 실제 코드 예시 (Turtle 포맷)
```turtle
@prefix steel: <http://steel-manufacturing.com/ontology#> .
@prefix inst:  <http://steel-manufacturing.com/instance#> .

# T-Box (스키마 정의)
steel:Quality  a  owl:Class .

# A-Box (실제 데이터)
inst:AirEmission_AM001_2025-09-01_070000
    a                  steel:Environment ;
    steel:pollutantType "CO" ;
    steel:concentration "37.52"^^xsd:float .
```
> 위키 문서의 철강 제조 온톨로지 실제 코드예요! 🏭

### RDF 직렬화(저장) 포맷
| 포맷 | 특징 | 예시 |
|---|---|---|
| **Turtle** | 사람이 읽기 쉬움 | `.ttl` 파일 |
| **RDF/XML** | W3C 공식, XML 기반 | `.rdf` 파일 |
| **JSON-LD** | JSON 기반, 웹 친화적 | `.jsonld` 파일 |
| **N-Triples** | 한 줄에 트리플 하나, 단순 | `.nt` 파일 |

---


## 🏗️ T-Box 설계 및 시험 방법

---

### 1️⃣ T-Box 설계 전체 프로세스 개요

```
T-Box 설계 → 구현 → 시험 전체 흐름
──────────────────────────────────────────────────
① 요구사항 분석    → 도메인 이해, CQ 작성
② 개념 모델링      → 클래스·관계·속성 정의
③ OWL 구현        → Protégé 또는 코드로 작성
④ 일관성 검사      → HermiT/Pellet 추론기 실행
⑤ 추론 검증       → 예상 추론 결과 확인
⑥ 인스턴스 테스트 → A-Box 붙여서 통합 검증
⑦ 반복 개선       → 피드백 반영 후 수정
```

---

### 2️⃣ STEP 1: 요구사항 분석 — Competency Question(CQ)

T-Box 설계의 **첫 번째 단계**는 온톨로지가 답해야 할 질문 목록을 먼저 정의하는 거예요.

#### Competency Question(CQ)이란?

> "이 온톨로지로 어떤 질문에 답할 수 있어야 하는가?"
> → CQ를 먼저 쓰면 **과도한 설계(over-engineering)** 를 방지해요!

#### 예시: "챗봇 사용자 관심사 추적 온톨로지"

```
CQ1. "홍길동 사용자가 최근 1달간 관심을 보인 주제는 무엇인가?"
CQ2. "AWS 관련 주제에 관심 있는 사용자는 누구인가?"
CQ3. "사용자의 관심이 어떻게 변화했는가? (시간 추적)"
CQ4. "특정 주제에 대해 사용자가 몇 번이나 질문했는가?"
CQ5. "어떤 주제들이 함께 자주 등장하는가?"
```

---

### 3️⃣ STEP 2: 개념 모델 설계

#### T-Box 4대 구성요소 설계

| 구성요소 | 설명 | 예시 |
|---|---|---|
| **클래스(Class)** | 개념/범주 정의 | `User`, `Topic`, `Preference`, `Interaction` |
| **계층관계(SubClassOf)** | 상속 관계 | `TechTopic ⊑ Topic`, `AWStopic ⊑ TechTopic` |
| **속성(Property)** | 관계 및 데이터 | `hasInterest`, `mentionedIn`, `occurredAt` |
| **제약조건(Restriction)** | 도메인/범위/개수 | `hasInterest` 범위: `Topic` |

#### 설계 다이어그램

```
┌─────────────────────────────────────────────────────────┐
│                챗봇 관심사 T-Box 설계                     │
│                                                          │
│  User ──hasInterest──▶ Preference                        │
│   │                        │                            │
│   └──participated──▶ Interaction ──aboutTopic──▶ Topic  │
│                            │              │              │
│                     occurredAt      ┌─────▼──────┐       │
│                      (DateTime)     │  TechTopic │       │
│                                     │  AwsTopic  │       │
│                                     │  AITopic   │       │
│                                     └────────────┘       │
└─────────────────────────────────────────────────────────┘
```

---

### 4️⃣ STEP 3: OWL/Turtle 코드로 구현

#### 방법 A: OWL/Turtle 파일 직접 작성

```turtle
# chatbot_ontology.ttl

@prefix owl: <http://www.w3.org/2002/07/owl#> .
@prefix rdf: <http://www.w3.org/1999/02/22-rdf-syntax-ns#> .
@prefix rdfs: <http://www.w3.org/2000/01/rdf-schema#> .
@prefix xsd: <http://www.w3.org/2001/XMLSchema#> .
@prefix chat: <http://chatbot-ontology.com/ontology#> .

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# 1. 클래스 정의 (T-Box: 개념 정의)
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
chat:User a owl:Class ;
    rdfs:label "사용자"@ko ;
    rdfs:comment "챗봇 서비스를 이용하는 사람" .

chat:Topic a owl:Class ;
    rdfs:label "주제"@ko ;
    rdfs:comment "대화에서 언급된 관심 주제" .

# 계층 관계 (SubClassOf)
chat:TechTopic a owl:Class ;
    rdfs:subClassOf chat:Topic ;
    rdfs:label "기술 주제"@ko .

chat:AwsTopic a owl:Class ;
    rdfs:subClassOf chat:TechTopic ;
    rdfs:label "AWS 관련 주제"@ko .

chat:Preference a owl:Class ;
    rdfs:label "선호도"@ko ;
    rdfs:comment "사용자의 관심사 선호 강도" .

chat:Interaction a owl:Class ;
    rdfs:label "대화 인터랙션"@ko .

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# 2. Object Property 정의 (관계)
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
chat:hasInterest a owl:ObjectProperty ;
    rdfs:domain chat:User ;
    rdfs:range chat:Preference ;
    rdfs:label "관심사를 가짐"@ko .

chat:aboutTopic a owl:ObjectProperty ;
    rdfs:domain chat:Interaction ;
    rdfs:range chat:Topic ;
    rdfs:label "주제에 관한"@ko .

chat:participated a owl:ObjectProperty ;
    rdfs:domain chat:User ;
    rdfs:range chat:Interaction ;
    rdfs:label "참여함"@ko .

# Inverse 관계
chat:isTopicOf a owl:ObjectProperty ;
    owl:inverseOf chat:aboutTopic .

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# 3. Datatype Property 정의 (속성값)
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
chat:userName a owl:DatatypeProperty ;
    rdfs:domain chat:User ;
    rdfs:range xsd:string .

chat:strength a owl:DatatypeProperty ;
    rdfs:domain chat:Preference ;
    rdfs:range xsd:float ;
    rdfs:comment "관심 강도 (0.0 ~ 1.0)" .

chat:occurredAt a owl:DatatypeProperty ;
    rdfs:domain chat:Interaction ;
    rdfs:range xsd:dateTime .

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# 4. 제약 조건 (Restriction)
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# 모든 Preference는 반드시 하나의 Topic을 가져야 함
chat:Preference rdfs:subClassOf [
    a owl:Restriction ;
    owl:onProperty chat:aboutTopic ;
    owl:minCardinality 1
] .
```

#### 방법 B: Graphiti Pydantic 모델 

```python
from pydantic import BaseModel, Field
from graphiti_core.nodes import EntityNode
from typing import Optional

# T-Box를 Pydantic 모델로 정의
class User(EntityNode):
    """챗봇 서비스를 이용하는 사용자"""
    user_id: str = Field(description="사용자 고유 ID")
    name: Optional[str] = Field(default=None, description="사용자 이름")

class Topic(EntityNode):
    """대화에서 언급된 관심 주제"""
    category: str = Field(description="주제 카테고리 (tech/lifestyle/finance 등)")
    keywords: list[str] = Field(default=[], description="관련 키워드 목록")

class TechTopic(Topic):  # SubClassOf 관계!
    """기술 관련 주제"""
    tech_domain: Optional[str] = Field(default=None, description="기술 도메인 (AWS/AI/DB 등)")

class Preference(EntityNode):
    """사용자의 관심사 선호도"""
    strength: float = Field(description="관심 강도 0.0~1.0")
    trend: str = Field(description="변화 트렌드 (증가/감소/유지)")

# T-Box를 Graphiti에 등록
from graphiti_core.llm_client.config import LLMConfig

entity_types = {
    "User": User,
    "Topic": Topic,
    "TechTopic": TechTopic,
    "Preference": Preference,
}
```

---

### 5️⃣ STEP 4: 일관성 검사 (Consistency Check)

#### 🔧 도구 1: Protégé + HermiT/Pellet 추론기

```
Protégé 일관성 검사 방법
────────────────────────────────────
① Protégé 실행 → OWL 파일 열기
② Reasoner 메뉴 → HermiT 선택
③ "Start reasoner" 클릭
④ 결과 확인:
   ✅ "Ontology is consistent" → 문제 없음
   ❌ "Ontology is inconsistent" → 오류 위치 확인
```

#### 🔧 도구 2: Python rdflib으로 자동 검사

```python
from rdflib import Graph, OWL, RDF, RDFS
from rdflib.plugins.sparql import prepareQuery

def check_tbox_consistency(ttl_file: str) -> dict:
    """T-Box 기본 일관성 검사"""
    g = Graph()
    g.parse(ttl_file, format="turtle")
    
    results = {
        "classes": [],
        "object_properties": [],
        "datatype_properties": [],
        "subclass_relations": [],
        "issues": []
    }
    
    # 1. 클래스 목록 조회
    classes_query = """
    SELECT ?class ?label WHERE {
        ?class a owl:Class .
        OPTIONAL { ?class rdfs:label ?label . FILTER(lang(?label) = "ko") }
    }
    """
    for row in g.query(classes_query):
        results["classes"].append({
            "uri": str(row.class_),
            "label": str(row.label) if row.label else ""
        })
    
    # 2. SubClassOf 관계 순환 검사
    subclass_query = """
    SELECT ?child ?parent WHERE {
        ?child rdfs:subClassOf ?parent .
        FILTER(?child != ?parent)
    }
    """
    subclass_pairs = []
    for row in g.query(subclass_query):
        subclass_pairs.append((str(row.child), str(row.parent)))
    results["subclass_relations"] = subclass_pairs
    
    # 3. Property Domain/Range 정의 여부 검사
    property_query = """
    SELECT ?prop WHERE {
        ?prop a owl:ObjectProperty .
        FILTER NOT EXISTS { ?prop rdfs:domain ?d }
    }
    """
    for row in g.query(property_query):
        results["issues"].append(f"⚠️ Domain 미정의 property: {row.prop}")
    
    return results

# 실행 예시
result = check_tbox_consistency("chatbot_ontology.ttl")
print(f"클래스 수: {len(result['classes'])}")
print(f"관계 수: {len(result['subclass_relations'])}")
print(f"이슈: {result['issues']}")
```

---

### 6️⃣ STEP 5: 추론 검증 (Reasoning Test)

T-Box에서 정의한 규칙이 **올바르게 추론**되는지 검증해요.

#### 추론 테스트 패턴: 예상 결과 검증

```python
from rdflib import Graph, Namespace, RDF, RDFS, OWL
from rdflib.term import URIRef

CHAT = Namespace("http://chatbot-ontology.com/ontology#")

def test_subclass_inference(g: Graph) -> list[dict]:
    """
    T-Box 추론 테스트:
    TechTopic ⊑ Topic 일 때,
    AwsTopic ⊑ TechTopic 이면 → AwsTopic ⊑ Topic 이어야 함 (이행적 추론)
    """
    tests = []
    
    # 테스트 1: AwsTopic은 TechTopic의 서브클래스인가?
    test1 = {
        "name": "AwsTopic subClassOf TechTopic",
        "expected": True,
        "result": (CHAT.AwsTopic, RDFS.subClassOf, CHAT.TechTopic) in g
    }
    test1["pass"] = test1["result"] == test1["expected"]
    tests.append(test1)
    
    # 테스트 2: Preference는 반드시 Topic을 가져야 하는가?
    restriction_query = """
    SELECT ?cls WHERE {
        ?cls rdfs:subClassOf [
            a owl:Restriction ;
            owl:onProperty chat:aboutTopic
        ]
    }
    """
    # ... 추가 테스트
    
    return tests

# 모든 테스트 실행
def run_all_tbox_tests(ttl_file: str):
    g = Graph()
    g.parse(ttl_file, format="turtle")
    
    test_results = test_subclass_inference(g)
    
    passed = sum(1 for t in test_results if t["pass"])
    total = len(test_results)
    
    print(f"\n📊 T-Box 추론 테스트 결과: {passed}/{total} 통과")
    for test in test_results:
        status = "✅" if test["pass"] else "❌"
        print(f"  {status} {test['name']}")
```

---

### 7️⃣ STEP 6: A-Box를 이용한 통합 시험

T-Box만 단독 테스트가 어렵기 때문에, **실제 인스턴스(A-Box)를 붙여서** 통합 검증해요.

```
T-Box 통합 테스트 구조
─────────────────────────────────────────────────
T-Box (검증 대상)        A-Box (테스트 데이터)
─────────────────  +  ──────────────────────────
클래스 정의           홍길동 : User
속성 정의             AWS주제 : AwsTopic
계층 관계             홍길동 -hasInterest→ AWS관심사
제약 조건             AWS관심사 -strength→ 0.85
                                ↓
                    추론 엔진 실행
                                ↓
               검증: "홍길동 : User", "AWS주제 : Topic" 등
```

#### 통합 테스트 코드

```python
import unittest
from rdflib import Graph, Namespace, RDF, RDFS
from rdflib.term import URIRef, Literal

CHAT = Namespace("http://chatbot-ontology.com/ontology#")
INST = Namespace("http://chatbot-ontology.com/instance#")
XSD  = Namespace("http://www.w3.org/2001/XMLSchema#")

class TBoxIntegrationTest(unittest.TestCase):
    
    def setUp(self):
        """T-Box + 테스트용 A-Box 로드"""
        self.g = Graph()
        # T-Box 로드
        self.g.parse("chatbot_ontology.ttl", format="turtle")
        # 테스트용 A-Box 인스턴스 추가
        self._add_test_instances()
    
    def _add_test_instances(self):
        """테스트용 인스턴스 삽입"""
        g = self.g
        # 사용자 인스턴스
        g.add((INST.kyopark, RDF.type, CHAT.User))
        g.add((INST.kyopark, CHAT.userName, Literal("홍길동")))
        
        # AWS 주제 인스턴스 (AwsTopic은 TechTopic ⊑ Topic)
        g.add((INST.awsNeptune, RDF.type, CHAT.AwsTopic))
        
        # 선호도 인스턴스
        g.add((INST.pref001, RDF.type, CHAT.Preference))
        g.add((INST.pref001, CHAT.strength, Literal(0.85)))
        g.add((INST.pref001, CHAT.aboutTopic, INST.awsNeptune))
        
        # 사용자-선호도 연결
        g.add((INST.kyopark, CHAT.hasInterest, INST.pref001))
    
    # ─── 테스트 케이스 1: 클래스 타입 확인 ───
    def test_user_is_correct_type(self):
        """홍길동는 User 타입이어야 함"""
        result = (INST.kyopark, RDF.type, CHAT.User) in self.g
        self.assertTrue(result, "홍길동가 User 타입이 아님!")
    
    # ─── 테스트 케이스 2: 계층 관계 확인 ───
    def test_awstopic_subclass_of_topic(self):
        """AwsTopic은 TechTopic의 하위 클래스"""
        result = (CHAT.AwsTopic, RDFS.subClassOf, CHAT.TechTopic) in self.g
        self.assertTrue(result, "AwsTopic이 TechTopic의 서브클래스가 아님!")
    
    # ─── 테스트 케이스 3: 속성 domain/range 검증 ───
    def test_hasinterest_domain_is_user(self):
        """hasInterest의 도메인은 User여야 함"""
        result = (CHAT.hasInterest, RDFS.domain, CHAT.User) in self.g
        self.assertTrue(result, "hasInterest의 domain이 User가 아님!")
    
    # ─── 테스트 케이스 4: SPARQL 쿼리로 CQ 검증 ───
    def test_cq1_user_interests(self):
        """CQ1: 홍길동의 관심사 주제를 조회할 수 있어야 함"""
        query = """
        PREFIX chat: <http://chatbot-ontology.com/ontology#>
        PREFIX inst: <http://chatbot-ontology.com/instance#>
        
        SELECT ?topic WHERE {
            inst:kyopark chat:hasInterest ?pref .
            ?pref chat:aboutTopic ?topic .
        }
        """
        results = list(self.g.query(query))
        self.assertGreater(len(results), 0, "관심사 주제 조회 결과가 없음!")
    
    # ─── 테스트 케이스 5: 잘못된 인스턴스 거부 ───
    def test_invalid_strength_value(self):
        """strength는 숫자여야 하며 0~1 사이여야 함"""
        # 잘못된 값 추가
        self.g.add((INST.pref001, CHAT.strength, Literal("강함")))  # 문자열은 잘못됨
        query = """
        PREFIX chat: <http://chatbot-ontology.com/ontology#>
        PREFIX inst: <http://chatbot-ontology.com/instance#>
        
        SELECT ?s WHERE {
            inst:pref001 chat:strength ?s .
            FILTER(isNumeric(?s))
        }
        """
        results = list(self.g.query(query))
        self.assertEqual(len(results), 1, "숫자 strength 값이 1개여야 함")

if __name__ == "__main__":
    unittest.main(verbosity=2)
```

---

### 8️⃣ STEP 7: SWRL 규칙 검증 (고급)

T-Box에 **추론 규칙(SWRL)**을 추가하고 검증하는 방법이에요.

```
SWRL 규칙 예시:
"사용자가 여러 번 AWS 주제에 대해 인터랙션했다면,
 그 사용자는 'AWS 전문 관심 사용자'로 분류"

User(?u) ∧ participated(?u, ?i) ∧ aboutTopic(?i, ?t)
∧ AwsTopic(?t) → hasExpertInterest(?u, ?t)
```

```python
# Python으로 SWRL 규칙 검증
def test_swrl_rule_aws_expert(g: Graph):
    """
    SWRL 규칙: AWS 주제로 3회 이상 인터랙션 → AWS 전문 관심 사용자
    """
    query = """
    PREFIX chat: <http://chatbot-ontology.com/ontology#>
    
    SELECT ?user (COUNT(?interaction) AS ?count)
    WHERE {
        ?user a chat:User .
        ?user chat:participated ?interaction .
        ?interaction chat:aboutTopic ?topic .
        ?topic a chat:AwsTopic .
    }
    GROUP BY ?user
    HAVING (?count >= 3)
    """
    results = list(g.query(query))
    print(f"AWS 전문 관심 사용자: {len(results)}명")
    for row in results:
        print(f"  - {row.user}: {row.count}회 인터랙션")
    return results
```

---

### 9️⃣ T-Box 시험 체크리스트

| 검증 항목 | 방법 | 도구 |
|---|---|---|
| **일관성(Consistency)** | 추론기로 모순 없는지 확인 | HermiT/Pellet, Protégé |
| **완전성(Completeness)** | CQ 목록 모두 SPARQL로 답 가능한지 | rdflib, SPARQL |
| **정확성(Correctness)** | SubClassOf·Domain/Range 정의 검증 | Python unittest |
| **추론 검증(Reasoning)** | 예상 추론 결과가 나오는지 | HermiT, 자동화 테스트 |
| **CQ 충족도** | 각 CQ에 대한 쿼리 결과 존재 여부 | SPARQL 쿼리 실행 |
| **제약 조건** | Cardinality, Domain, Range 위반 없는지 | 추론기 |
| **순환 참조 없음** | SubClassOf 사이클 없는지 | 그래프 탐색 알고리즘 |

---

### 🔟 도구 선택 가이드

| 도구 | 용도 | 비용 |
|---|---|---|
| **Protégé** | GUI 기반 OWL 편집·추론 검사 | 무료 |
| **HermiT** | OWL DL 완전 추론기 (Protégé 내장) | 무료 |
| **Pellet** | HermiT + 규칙 추론 | 무료 |
| **rdflib (Python)** | 코드 기반 자동화 검증 | 무료 |
| **Apache Jena** | Java 기반 RDF 처리·추론 | 무료 |
| **Graphiti (Pydantic)** | AI 에이전트용 T-Box 정의·검증 | 무료 오픈소스 |

---

### 📝 핵심 요약

```
T-Box 설계 및 시험 7단계 요약
─────────────────────────────────────────────────────
1️⃣ CQ 작성        → "어떤 질문에 답해야 하나?"
2️⃣ 개념 모델링    → 클래스·관계·속성·제약 설계
3️⃣ OWL 구현       → Turtle 파일 또는 Pydantic 모델
4️⃣ 일관성 검사    → HermiT/Pellet으로 모순 확인
5️⃣ 추론 검증      → 예상 추론 결과 자동 테스트
6️⃣ A-Box 통합 시험→ 실제 인스턴스 붙여서 CQ 검증
7️⃣ 반복 개선      → 실패한 테스트 기반 수정
```

> 💡 **프로젝트 적용 팁**: Graphiti를 사용하신다면 **Pydantic 모델이 T-Box**예요! Python `unittest`로 엔티티 타입 정의와 관계를 검증하면 충분히 실용적인 T-Box 시험이 가능합니다. 🎯










---
## 2️⃣ OWL (Web Ontology Language)

### 정의
- W3C 표준으로 **"개념(클래스)과 관계를 논리적으로 정의"** 하는 언어
- RDF 위에 올라탄 상위 레이어 (RDF를 확장한 것!)
- OWL 1 → OWL 2 (2009) 현재까지 사용

### OWL의 핵심 구성 요소

```
OWL 구성 요소
├── 클래스 (Class)          → owl:Class
│   └── 서브클래스 관계      → rdfs:subClassOf
├── 오브젝트 프로퍼티        → owl:ObjectProperty  (개체 ↔ 개체 관계)
├── 데이터 프로퍼티          → owl:DatatypeProperty (개체 → 숫자/문자)
└── 제약 조건 (Restriction)
    ├── Domain / Range
    ├── Cardinality (최소/최대 개수)
    └── allValuesFrom / someValuesFrom
```

### 실제 OWL 예시

```turtle
# T-Box: 클래스 정의 (OWL)
:엔지니어  rdfs:subClassOf  :사람 .          # 엔지니어는 사람의 하위 클래스
:근무한다  a                owl:ObjectProperty ;
           rdfs:domain      :사람 ;            # 주어는 반드시 사람
           rdfs:range       :회사 .            # 목적어는 반드시 회사

# A-Box: 실제 인스턴스
:홍길동    a                :엔지니어 ;        # 홍길동는 엔지니어
           :근무한다        :AWS .             # AWS에서 일한다
```

→ 추론 엔진이 자동으로 도출: **홍길동는 사람** ✨

---

## 3️⃣ RDF vs OWL 관계

```
┌─────────────────────────────────────┐
│           OWL (의미론 레이어)         │  ← 클래스·속성·규칙 정의
│  owl:Class, owl:ObjectProperty 등   │
├─────────────────────────────────────┤
│          RDFS (스키마 레이어)         │  ← 기본 상속·타입 정의
│  rdfs:subClassOf, rdfs:label 등     │
├─────────────────────────────────────┤
│           RDF (데이터 레이어)         │  ← 트리플로 모든 것 표현
│  Subject - Predicate - Object       │
└─────────────────────────────────────┘
```

> OWL ⊃ RDFS ⊃ RDF 순으로 **상위 집합** 관계!

---

## 4️⃣ 기술 스택 전체 그림 (시맨틱 웹)

```
질의언어  ────  SPARQL  (RDF를 SQL처럼 쿼리)
온톨로지  ────  OWL     (개념/규칙 정의)
스키마    ────  RDFS    (기본 어휘 정의)
데이터    ────  RDF     (트리플 표현)
저장소    ────  Triplestore (Fuseki, Neptune, Virtuoso)
```

### SPARQL 예시 (SQL과 비교)
```sparql
# "엔지니어인 사람과 그가 근무하는 회사 조회"
SELECT ?사람 ?회사
WHERE {
    ?사람  a          :엔지니어 .
    ?사람  :근무한다  ?회사 .
}
```

---

## 5️⃣ OWL 추론기 종류

| 추론기 | 특징 | 용도 |
|---|---|---|
| **HermiT** | OWL DL 완전 추론, 일관성 검사 | 온톨로지 설계 검증 |
| **Pellet** | HermiT + 규칙 추론 혼합 | 실용적 추론 |
| **OWL RL** | 규칙 기반 경량 추론 | 대용량 데이터 |
| **Jena** | Java 기반, Apache 오픈소스 | 범용 RDF 처리 |

> 위키 문서의 철강 온톨로지에서 **HermiT + Pellet + OWL RL** 세 가지를 조합해 사용하고 있어요! 🔍

---

## 6️⃣ 실무 활용 도구 매핑

| 도구 | RDF/OWL 연관성 |
|---|---|
| **Amazon Neptune** | RDF 트리플스토어 + SPARQL 쿼리 지원 |
| **Apache Jena/Fuseki** | 가장 대중적인 오픈소스 RDF 서버 |
| **Protégé** | OWL 온톨로지 GUI 편집 도구 |
| **rdflib (Python)** | Python에서 RDF 파싱/생성 |
| **Neo4j** | RDF가 아닌 LPG이지만 Neosemantics로 RDF 변환 가능 |
| **Graphiti** | RDF/OWL 아님, 자체 그래프 구조 (더 간편!) |

---

## 7️⃣ RDF/OWL vs 현대 도구 비교

| 구분 | RDF/OWL | Neo4j (LPG) | Graphiti |
|---|---|---|---|
| **표준** | W3C 공식 표준 | 자체 표준 | 오픈소스 |
| **쿼리** | SPARQL | Cypher | Python API |
| **추론** | ✅ 강력한 논리 추론 | ❌ 기본 제공 안 됨 | ❌ |
| **학습 곡선** | 매우 높음 😓 | 중간 | 낮음 😊 |
| **유연성** | 매우 높음 | 높음 | 중간 |
| **실무 채택률** | 학계/연구 중심 | 높음 | AI 에이전트 특화 |

---

## 💡 관심사와 연결하면

```
RDF/OWL 기술 스택
        ↓ (어렵지만 강력)
Amazon Neptune (RDF 트리플스토어)
        ↓ (프로젝트와 연결!)
Bedrock KB GraphRAG ─── Neptune Analytics 사용
Graphiti            ─── Neptune 백엔드 지원
```

> 📌 **핵심 한 줄:**
> RDF는 **"주어-서술어-목적어" 트리플로 모든 지식을 표현하는 방법**이고,
> OWL은 **"그 개념들 사이의 규칙과 계층을 정의하는 언어"** 예요.
> 두 개를 합치면 **추론 가능한 지식 그래프**가 완성됩니다! 🎯



## W3C 관련

W3C 시맨틱 웹 표준 스택
├── RDF  ──── "데이터 표현 방법"     (W3C 1999~)
├── RDFS ──── "기본 어휘/스키마"     (W3C 2004~)
├── OWL  ──── "온톨로지 언어"        (W3C 2004~, OWL2 2009~)
└── SPARQL ── "그래프 쿼리 언어"     (W3C 2008~)
        ↓
Amazon Neptune이 이 모든 표준을 구현!
        ↓
Bedrock KB GraphRAG의 기반 인프라





---

## 🟢 Neo4j 란?

### 한 마디로 요약
> **"세계에서 가장 많이 쓰이는 그래프 데이터베이스"**
> — 데이터를 테이블(행/열) 대신 **노드(Node)와 엣지(Edge)** 로 저장하는 DB

---

## 1️⃣ 기본 정보

| 항목 | 내용 |
|---|---|
| **회사** | Neo4j Inc. (스웨덴/미국) |
| **설립** | 2007년 |
| **라이선스** | Community Edition(오픈소스 GPL) / Enterprise Edition(상용) |
| **GitHub** | 14K+ ⭐ |
| **데이터 모델** | **LPG** (Labeled Property Graph, 레이블 속성 그래프) |
| **쿼리 언어** | **Cypher** (SQL과 유사한 직관적 그래프 쿼리) |
| **사용 기업** | NASA, eBay, Adobe, UBS, 의료/금융/추천 시스템 등 |

---

## 2️⃣ Neo4j의 핵심 개념: LPG (Labeled Property Graph)

RDF의 트리플과 달리, Neo4j는 **노드와 관계에 직접 속성(Properties)을 붙일 수 있어요!**

```
┌─────────────────────────────────────────────────┐
│                  LPG 구조                        │
│                                                  │
│   (홍길동)──[근무한다 {since:2020}]──>(AWS Korea) │
│   라벨:엔지니어                    라벨:회사       │
│   name: "홍길동"                   name: "AWS"   │
│   skills: ["Python","AWS"]        location:"서울" │
└─────────────────────────────────────────────────┘
```

### LPG의 3가지 구성 요소

| 구성 요소 | 설명 | 예시 |
|---|---|---|
| **노드 (Node)** | 개체/인스턴스 | `(홍길동)`, `(AWS Korea)` |
| **라벨 (Label)** | 노드의 타입 분류 | `:엔지니어`, `:회사` |
| **관계 (Relationship)** | 노드 간의 연결 | `-[근무한다]->` |
| **속성 (Property)** | 노드·관계의 키-값 데이터 | `{since: 2020, role: "SA"}` |

---

## 3️⃣ Cypher 쿼리 언어

Neo4j만의 직관적인 그래프 쿼리 언어예요. **ASCII 아트처럼 그래프를 표현**해요!

### 기본 문법 구조
```cypher
-- 노드: (변수명:라벨 {속성})
-- 관계: -[변수명:관계타입 {속성}]->

-- 패턴 매칭 (MATCH = SELECT)
MATCH (p:엔지니어)-[r:근무한다]->(c:회사)
WHERE c.name = "AWS"
RETURN p.name, r.since, c.location
```

### 주요 Cypher 명령어

```cypher
-- 데이터 생성 (CREATE)
CREATE (n:사람 {name: "홍길동", role: "SA"})

-- 데이터 조회 (MATCH + RETURN)
MATCH (n:사람) RETURN n.name

-- 관계 생성
MATCH (a:사람 {name:"홍길동"}), (b:회사 {name:"AWS"})
CREATE (a)-[:근무한다 {since: 2020}]->(b)

-- 경로 탐색 (몇 단계든 연결된 노드 찾기)
MATCH (a)-[:친구*1..3]-(b)  -- 1~3단계 거리의 친구
RETURN a.name, b.name

-- 삭제
MATCH (n:사람 {name:"홍길동"}) DETACH DELETE n
```

### SQL vs Cypher 비교

| SQL | Cypher |
|---|---|
| `SELECT * FROM 사람` | `MATCH (n:사람) RETURN n` |
| `JOIN 회사 ON ...` | `MATCH (n)-[:근무한다]->(c)` |
| `WHERE age > 30` | `WHERE n.age > 30` |
| `INSERT INTO ...` | `CREATE (n:사람 {...})` |

---

## 4️⃣ RDF vs Neo4j LPG 비교

| 구분 | RDF (W3C 표준) | Neo4j LPG |
|---|---|---|
| **데이터 단위** | 트리플 (S-P-O) | 노드 + 관계 + 속성 |
| **관계 속성** | 별도 노드로 표현 필요 (복잡) | 관계에 직접 속성 가능 ✅ |
| **쿼리** | SPARQL | Cypher (더 직관적!) |
| **표준** | W3C 국제 표준 | Neo4j 자체 표준 |
| **추론** | OWL 추론기 지원 | 기본 미지원 (플러그인 필요) |
| **학습 곡선** | 매우 높음 | 낮음 😊 |
| **성능** | 대용량 느림 | 빠른 그래프 순회 ✅ |
| **실무 채택률** | 학계·연구 중심 | 산업 현장 1위 |

---

## 5️⃣ Neo4j의 핵심 강점

### ⚡ 그래프 순회 성능
```
관계형 DB (JOIN 방식):
  테이블 A → JOIN → 테이블 B → JOIN → 테이블 C
  데이터 많을수록 기하급수적으로 느려짐 📉

Neo4j (포인터 방식):
  노드A ─→ 노드B ─→ 노드C
  관계를 포인터로 직접 연결 → 데이터 양과 무관하게 빠름 📈
```

### 🔍 주요 활용 사례
| 분야 | 활용 예시 |
|---|---|
| **추천 시스템** | "이 사람과 비슷한 사람들이 좋아한 상품" |
| **사기 탐지** | 금융 거래 네트워크에서 비정상 패턴 탐지 |
| **지식 그래프** | ChatGPT의 내부 지식 구조, 의료 데이터 |
| **소셜 네트워크** | 친구 추천, 인플루언서 분석 |
| **공급망 관리** | 부품 의존관계, 병목 분석 |
| **사이버보안** | 공격 경로 추적, 취약점 연결 분석 |

---

## 6️⃣ Neo4j 생태계

```
Neo4j 생태계
├── Neo4j Community/Enterprise  ← 핵심 DB
├── Neo4j AuraDB                ← 클라우드 관리형 서비스 (SaaS)
├── Neo4j Browser               ← 웹 기반 GUI 탐색 도구
├── Bloom                       ← 비기술 사용자용 시각화
├── neo4j-driver                ← Python/Java/JS 클라이언트
├── LangChain Neo4j             ← LLM + 그래프 연동
├── neosemantics (n10s)         ← RDF↔LPG 변환 플러그인
└── APOC 라이브러리              ← 고급 그래프 알고리즘
```

---

## 7️⃣ 관심사와 연결

```
Graphiti (AI 에이전트 메모리)
    └─ 백엔드 DB로 Neo4j 사용 ✅
       (또는 FalkorDB / Amazon Neptune)

Graphify (코드/문서 지식 그래프)
    └─ --neo4j-push 로 내보내기 지원 ✅

LLM Graph Builder (neo4j-labs)
    └─ 문서→그래프 변환, Neo4j 고정 ✅

Amazon Neptune
    └─ Neo4j의 AWS 클라우드 대안
       Cypher(openCypher) + SPARQL 둘 다 지원!
```

### Python에서 Neo4j 사용 예시

```python
from neo4j import GraphDatabase

driver = GraphDatabase.driver("bolt://localhost:7687",
                              auth=("neo4j", "password"))

with driver.session() as session:
    # 노드 생성
    session.run("""
        CREATE (p:사람 {name: $name, role: $role})
    """, name="홍길동", role="AWS SA")

    # 관계 조회
    result = session.run("""
        MATCH (p:사람)-[:근무한다]->(c:회사)
        RETURN p.name, c.name
    """)
    for record in result:
        print(record["p.name"], "→", record["c.name"])
```

---

## 📝 핵심 한 줄 정리

> Neo4j는 **"노드·관계·속성으로 데이터를 저장하는 세계 1위 그래프 DB"** 로,
> **Cypher** 라는 직관적 쿼리 언어로 복잡한 관계를 SQL보다 훨씬 쉽게 다룰 수 있어요.
> **Graphiti의 기본 백엔드가 바로 Neo4j** 예요! 🎯

---

더 궁금하신 게 있으시면 말씀해 주세요 😊
- Cypher 쿼리 심화 예제
- Neo4j vs Amazon Neptune 선택 기준
- Graphiti + Neo4j 실제 연동 코드




---

## 💰 Neo4j는 무료인가요?

### 결론: **"무료 옵션이 있다! 하지만 규모에 따라 비용이 상당히 커진다"**

---

## 1️⃣ Neo4j 라이선스/배포 옵션 전체 구조

```
Neo4j 배포 방식
├── ① 셀프호스팅 (Self-managed)
│   ├── Community Edition   ← ✅ 완전 무료 (오픈소스 GPL)
│   └── Enterprise Edition  ← 💰 유료 (연간 계약, ~$20K~200K+)
│
└── ② 클라우드 관리형 (AuraDB)
    ├── AuraDB Free         ← ✅ 무료 (단, 제한 있음)
    ├── AuraDB Professional ← 💰 $65/GB/월
    ├── AuraDB Business Critical ← 💰 $146/GB/월
    └── AuraDB Virtual Dedicated Cloud ← 💰 별도 견적
```

---

## 2️⃣ 각 옵션 상세 비교

### 🆓 무료 옵션들

| 옵션 | 비용 | 제한사항 |
|---|---|---|
| **Community Edition** (셀프호스팅) | **완전 무료** | 클러스터링 ❌, 고급 보안 ❌, 온라인 백업 ❌ |
| **AuraDB Free** (클라우드) | **완전 무료** | 노드 20만 개, 관계 40만 개 제한, 72시간 미사용 시 자동 일시정지, 30일 정지 시 삭제 |

> 📌 **개발/테스트/학습 목적엔 이 두 가지면 충분**

---

### 💰 유료 옵션들

| 옵션 | 가격 | 특징 |
|---|---|---|
| **AuraDB Professional** | $65/GB/월 (최소 1GB) | 14일 무료 체험, 단일 AZ, 일별 백업(7일 보관) |
| **AuraDB Business Critical** | $146/GB/월 (최소 2GB) | 멀티 AZ 고가용성, 99.95% SLA, RBAC, SSO |
| **Enterprise Edition** (셀프호스팅) | 연간 약 $20K~$200K+ | 클러스터링, 고급 보안, 전용 인프라 |

### 💡 AuraDB 실제 월 비용 예시

```
AuraDB Professional 기준:
  ├── 1GB RAM  → $65/월   (소규모 프로젝트)
  ├── 4GB RAM  → ~$260/월
  ├── 8GB RAM  → ~$520/월
  ├── 32GB RAM → ~$2,080/월
  └── 64GB RAM → ~$4,205/월 (대규모)
```

---

## 3️⃣ Computing Power는 많이 필요한가요?

### 결론: **"그래프 DB 자체는 효율적이지만, 규모에 따라 크게 달라진다"**

### Neo4j 최소 사양 (Community Edition 셀프호스팅)

| 환경 | CPU | RAM | 디스크 |
|---|---|---|---|
| **개발/학습** | 2 코어 | **2~4 GB** | 10 GB SSD |
| **소규모 프로덕션** | 4 코어 | **8~16 GB** | 100 GB SSD |
| **중규모 프로덕션** | 8 코어 | **32~64 GB** | 500 GB SSD |
| **대규모 엔터프라이즈** | 16+ 코어 | **128 GB+** | TB급 NVMe |

### ⚡ Neo4j 성능의 핵심 = RAM!

```
Neo4j 성능 공식:
  그래프 데이터를 최대한 RAM에 올려야 빠름!

  그래프 크기 ≤ RAM → 🚀 매우 빠름 (서브초 응답)
  그래프 크기  > RAM → 🐢 디스크 I/O 발생 → 느려짐
```

> **Neo4j는 RAM 중심 DB예요!** 디스크보다 RAM에 투자하는 게 핵심이에요.

---

## 4️⃣ 목적별 추천 구성

| 목적 | 추천 옵션 | 비용 | 사양 |
|---|---|---|---|
| **학습/테스트** | AuraDB Free | **무료** | 클라우드 관리형 |
| **개인 프로젝트** | Community Edition (로컬) | **무료** | RAM 4GB면 충분 |
| **Graphiti 백엔드** | Community Edition (Docker) | **무료** | RAM 4~8GB |
| **소규모 프로덕션** | AuraDB Professional 1~2GB | $65~$130/월 | 클라우드 관리형 |
| **엔터프라이즈** | AuraDB Business Critical | $292/월~ | 고가용성 |

---

## 5️⃣ Docker로 무료로 로컬 실행하기

Graphiti 백엔드로 쓰실 때 가장 간단한 방법이에요!

```bash
# Neo4j Community Edition Docker 실행 (완전 무료!)
docker run \
  --name neo4j \
  -p 7474:7474 \   # Browser UI
  -p 7687:7687 \   # Bolt (드라이버 연결)
  -e NEO4J_AUTH=neo4j/password \
  -v neo4j_data:/data \
  neo4j:5.x-community

# 브라우저에서 http://localhost:7474 접속!
```

**리소스 사용량 (실제 측정치):**
```
유휴 상태:   CPU ~0.1%,  RAM ~300MB
소규모 쿼리: CPU ~5~10%, RAM ~500MB~1GB
중규모 쿼리: CPU ~20~40%, RAM ~2~4GB
```

---

## 6️⃣ Neo4j vs Amazon Neptune 비용 비교


| 항목 | Neo4j AuraDB | Amazon Neptune |
|---|---|---|
| **무료 티어** | ✅ AuraDB Free | ❌ 없음 |
| **최소 비용** | $65/GB/월 | ~$0.10~0.24/시간 (~$72~175/월) |
| **배포 방식** | 멀티 클라우드 (AWS/Azure/GCP) | AWS 전용 |
| **쿼리 언어** | Cypher | openCypher + SPARQL |
| **관리 부담** | 낮음 (완전 관리형) | 낮음 (완전 관리형) |
| **Graphiti 지원** | ✅ 공식 지원 | ✅ 공식 지원 |

---

## 📝 핵심 요약

| 질문 | 답변 |
|---|---|
| **무료인가요?** | Community Edition(셀프호스팅) + AuraDB Free(클라우드) 둘 다 **무료 옵션 있음** ✅ |
| **컴퓨팅 많이 필요?** | 개발용은 **RAM 4GB면 충분** 😊, 프로덕션은 규모에 따라 확장 필요 |
| **추천** | 로컬 테스트 → **Docker Community Edition** (무료), AWS 프로덕션 → **Neptune** (기존 인프라 연동) |

> 💡 **Graphiti + Neo4j 조합으로 로컬 테스트할 때는 비용 0원으로 충분히 구성 가능해요!** 🎉





---

## 🔷 Amazon Neptune Analytics 란?

### 한 마디로 요약
> **"수백억 개의 그래프 관계를 메모리에 올려서 초고속 분석하는 AWS 완전관리형 인메모리 그래프 분석 엔진"**

---

## 1️⃣ Amazon Neptune 전체 서비스 구조

먼저 Neptune이 두 개의 서비스로 구성된다는 걸 이해해야 해요:

```
Amazon Neptune
├── Neptune Database        ← 기존 서비스 (OLTP, 트랜잭션)
│   ├── Gremlin, openCypher, SPARQL 지원
│   └── 소셜 네트워크, 사기 탐지, Customer 360에 최적
│
└── Neptune Analytics       ← 신규 서비스 (OLAP, 분석) ⭐
    ├── openCypher + 벡터 검색 지원
    └── GraphRAG, 그래프 알고리즘, 에이전트 메모리에 최적
```

---

## 2️⃣ Neptune Analytics의 핵심 특징

### ⚡ 핵심 강점: 인메모리(In-Memory) 아키텍처
```
일반 그래프 DB:
  디스크에 저장 → 쿼리 시 읽어옴 → 🐢 상대적으로 느림

Neptune Analytics:
  전체 그래프를 RAM에 로드 → 직접 연산 → 🚀 초고속!
  → 수백억 관계를 수초 내에 분석 가능
```

### 🔑 주요 기능 5가지

| 기능 | 설명 |
|---|---|
| **인메모리 고속 분석** | 수백억(tens of billions) 그래프 관계를 초 단위 분석 |
| **내장 그래프 알고리즘** | PageRank, 커뮤니티 탐지, 최단 경로 등 사전 구축 알고리즘 |
| **네이티브 벡터 검색** | 그래프 순회 + 벡터 유사도 검색 동시 지원 → **GraphRAG 핵심!** |
| **openCypher 쿼리** | Neo4j와 동일한 Cypher 쿼리 언어 사용 |
| **자동 컴퓨팅 프로비저닝** | 그래프 크기에 따라 자동으로 리소스 조정 |

---

## 3️⃣ Neptune Database vs Neptune Analytics 비교

| 구분 | Neptune Database | Neptune Analytics |
|---|---|---|
| **목적** | 트랜잭션(OLTP), 실시간 읽기/쓰기 | 분석(OLAP), 대규모 그래프 분석 |
| **저장 방식** | 디스크 기반 영구 저장 | **인메모리** 고속 처리 |
| **쿼리 언어** | Gremlin, openCypher, SPARQL | openCypher + 벡터 검색 |
| **데이터 모델** | 속성 그래프 + RDF | 속성 그래프 (순회+유사도 최적화) |
| **주요 용도** | 소셜 네트워크, 사기 탐지, Customer 360 | **GraphRAG**, 에이전트 메모리, 그래프 분석 |
| **처리량** | 최대 100,000 쿼리/초 | 수천 분석 쿼리/초 + 수백억 관계 |
| **일시정지** | 지원 안 함 | ✅ 지원 (비용 90% 절감!) |

---

## 4️⃣ GraphRAG 연동

Neptune Analytics가 **Bedrock Knowledge Base GraphRAG의 공식 백엔드**예요!

```
Bedrock GraphRAG 동작 흐름
─────────────────────────────────────────────────────
① 문서(S3) → Bedrock이 엔티티/관계 자동 추출
                        ↓
② Neptune Analytics에 그래프 저장 (노드 + 엣지 + 벡터)
                        ↓
③ 질문 입력 →  벡터 검색(의미 유사도)
               +그래프 순회(관계 탐색) 동시 수행
                        ↓
④ 더 풍부한 컨텍스트로 LLM이 답변 생성 🎯
```

### GraphRAG vs 일반 RAG 차이
```
일반 RAG:
  질문 → 벡터 검색 → "청크 A" 하나만 반환 → 답변

GraphRAG (Neptune Analytics):
  질문 → 벡터 검색 + 그래프 순회
        → "청크 A" + "청크 A와 연결된 B, C, D" 함께 반환
        → 더 정확하고 포괄적인 답변! ✨
```

---

## 5️⃣ 내장 그래프 알고리즘 종류

Neptune Analytics에 기본 제공되는 알고리즘들이에요:

| 카테고리 | 알고리즘 | 활용 사례 |
|---|---|---|
| **중심성** | PageRank, Betweenness Centrality | 핵심 노드 파악, 인플루언서 탐지 |
| **커뮤니티** | Community Detection (Louvain) | 그룹/클러스터 자동 분류 |
| **경로** | Shortest Path, All Paths | 최단 경로, 연결 관계 탐색 |
| **유사도** | Node Similarity, Vector Similarity | 유사 노드 추천, 벡터 검색 |
| **링크 예측** | Triangle Count | 소셜 관계 예측 |

---

## 6️⃣ 비용 구조 (💰)

### 과금 단위: **m-NCU (memory-optimized Neptune Capacity Unit)**
> 1 m-NCU = 1GB 메모리 + 그에 상응하는 컴퓨팅 + 네트워킹

```
Neptune Analytics 요금 (서울 리전 기준, 미국 동부 기준 $0.1098/m-NCU-시간)
───────────────────────────────────────────────
• 실행 중:  ~$0.1098/m-NCU/시간
• 일시정지: ~$0.011/m-NCU/시간 (약 10% 요금) ✅
• 스토리지: 별도 청구 (Neptune Database와 동일)

최소 구성 1 m-NCU 기준:
  월 연속 실행: 1 × $0.1098 × 730시간 ≈ $80/월
  (Bedrock KB GraphRAG 자동 생성 시 AWS가 관리)
```

### 💡 비용 절감 팁
- **일시정지(Pause)** 기능 활용 → 사용 안 할 때 90% 절감!
- Bedrock KB GraphRAG 사용 시 자동 프로비저닝되므로 직접 관리 불필요
- 2026년 3월부터 **Database Savings Plans** 적용 가능

---

## 7️⃣ 데이터 로드 방법

```
Neptune Analytics 데이터 소스
├── Amazon S3           ← CSV, JSON 형태의 그래프 데이터
├── Neptune Database    ← 기존 Neptune DB에서 직접 로드
└── Bedrock KB          ← 자동으로 엔티티/관계 추출 후 저장
```

### Python(boto3)으로 쿼리하기

```python
import boto3

client = boto3.client('neptune-graph', region_name='ap-northeast-2')

# openCypher 쿼리 실행
response = client.execute_query(
    graphIdentifier='my-graph-id',  # KB 콘솔에서 확인
    queryString="""
        MATCH (a)-[r]->(b)
        RETURN a.name, type(r), b.name
        LIMIT 100
    """,
    language='OPEN_CYPHER'
)
print(response['payload'].read())
```

---

## 8️⃣ 아키텍처에서의 위치

```
문서 기반 지식 그래프 (정적)
  Bedrock KB GraphRAG
      └─── Neptune Analytics ← 오늘의 주제! 📍
              ├── 엔티티·관계 자동 저장
              └── 벡터 + 그래프 하이브리드 검색

대화 기반 지식 그래프 (동적)
  Graphiti
      └─── Neptune Analytics (또는 Neo4j)
              ├── Q&A 에피소드 실시간 저장
              └── Bi-temporal 관계 추적
────────────────────────────────────────────────
두 그래프가 같은 Neptune 인프라 위에 병행 구성 가능! ✅
```

---

## 📝 핵심 정리

| 질문 | 답변 |
|---|---|
| 무엇인가? | AWS 완전관리형 **인메모리 그래프 분석 엔진** |
| Neptune DB와 차이? | DB는 OLTP(트랜잭션), Analytics는 **OLAP(분석)** |
| 가장 큰 특징? | **벡터 검색 + 그래프 순회 동시 지원** → GraphRAG에 최적! |
| 관련성 | **Bedrock KB GraphRAG의 공식 백엔드**, Graphiti 지원 |
| 비용? | ~$0.11/m-NCU/시간, **일시정지 시 90% 절감** |

> 💡 한 줄 요약: Neptune Analytics = **"그래프 + 벡터 검색을 동시에 초고속으로!"** — AWS GraphRAG의 심장부예요! 🎯

더 궁금하신 게 있으면 알려주세요 😊
- Neptune Analytics로 Bedrock GraphRAG 조회하는 코드 예제
- Neptune Database vs Neptune Analytics 상세 아키텍처
- Graphiti + Neptune Analytics 연동 방법

### Reference
1. [in-database analytics](https://docs.aws.amazon.com/neptune-analytics/latest/userguide/neptune-analytics-features.html) — Analytical processing performed directly within the Neptune Analytics graph database environment
2. [graph database](https://docs.aws.amazon.com/neptune/latest/userguide/graph-get-started.html) — A database optimized to store and query relationships between data items represented as vertices...
3. [Neptune database](https://docs.aws.amazon.com/neptune-analytics/latest/userguide/neptune-analytics-vs-neptune-database.html) — An existing Amazon Neptune database that can serve as a data source for Neptune Analytics graphs
4. [Getting started with Amazon Neptune](https://docs.aws.amazon.com/neptune/latest/userguide/intro.html) — An end-to-end procedure to create and configure an Amazon Neptune database cluster with VPC netwo...










---

## 🧩 T-Box(Terminological Box)란?

**T-Box**는 온톨로지에서 **"세상이 어떻게 생겼는지"에 대한 규칙과 스키마를 정의하는 계층**입니다. 즉, 개념과 어휘의 구조를 정의하는 부분으로, 온톨로지의 **뼈대(schema)** 역할을 합니다.

> 💡 **비유**: 데이터베이스의 **테이블 스키마(Table Schema)**에 해당합니다. "어떤 종류의 데이터가 존재할 수 있는지"를 정의하는 설계도입니다.

---

## 📐 T-Box의 주요 구성 요소

| 구성 요소 | 설명 | 예시 |
|---|---|---|
| **클래스 정의** | 개념(개체 종류)을 정의 | 사람, 회사, 도시, 엔지니어 |
| **계층 관계 (SubClassOf)** | 클래스 간 상하 관계 정의 | 엔지니어 ⊑ 사람 |
| **속성/관계 정의** | 개체 간 관계 및 데이터 속성 정의 | 근무한다(Object Property), 나이(Datatype Property) |
| **제약 조건** | 관계의 범위·형식 제약 | Domain, Range, Cardinality |

---

## 🔍 T-Box vs A-Box 비교

T-Box를 이해하려면 짝을 이루는 **A-Box**와 함께 보는 것이 좋습니다.

| 구분 | **T-Box** (용어 상자) | **A-Box** (사실 상자) |
|---|---|---|
| **핵심 질문** | "세상이 **어떻게 생겼나**?" (규칙) | "실제로 **무엇이 있나**?" (사실) |
| **역할** | 개념·스키마 정의 | 구체적 인스턴스 데이터 |
| **DB 비유** | 테이블 스키마 | 실제 행(Row) 데이터 |
| **성격** | 안정적, 자주 안 바뀜 | 동적, 지속 추가·수정·삭제 |
| **규모** | 상대적으로 작음 | T-Box보다 수백~수천 배 큼 |
| **OWL/RDF 표현** | `owl:Class`, `rdfs:subClassOf`, `owl:ObjectProperty` | `rdf:type`, 속성값 트리플 |

> 📊 **실무 사례 (철강 제조 온톨로지)**: T-Box는 약 **2,825개** 트리플에 불과했지만, A-Box는 **850,810 라인**으로 훨씬 방대했습니다.

---

## ⚙️ T-Box와 A-Box가 결합된 추론(Inference)

T-Box의 규칙과 A-Box의 사실이 합쳐지면 **명시하지 않은 정보도 자동으로 도출**됩니다.

```
T-Box (규칙):   엔지니어 ⊑ 사람        ← "엔지니어는 사람이다"
A-Box (사실):   홍길동 : 엔지니어       ← "홍길동는 엔지니어다"
─────────────────────────────────────
추론 결과:      홍길동 : 사람          ← 자동 도출! ✨
```

이처럼 추론 엔진은 T-Box를 기반으로 A-Box에 없는 새로운 사실을 자동 생성합니다.

---

## 🛠️ 실무 도구별 T-Box 매핑


| 도구 | T-Box (스키마) | A-Box (인스턴스) |
|---|---|---|
| **RDF/OWL** | `owl:Class`, `owl:ObjectProperty` 정의 | 트리플 인스턴스 |
| **Neo4j** | 노드 라벨·관계 타입 스키마 | 실제 노드·엣지 |
| **Graphiti** | Pydantic 커스텀 엔티티 타입 (Preference, Intent, Topic) | `add_episode()`로 추출된 실제 엔티티·관계 |
| **Bedrock KB GraphRAG** | FM이 추론하는 엔티티/관계 스키마 | Neptune Analytics에 저장된 노드·엣지 |

---

## 💬 챗봇 관심사 추적에의 적용 (프로젝트 관점)

**챗봇 Q&A 관심사 추적 시스템**에 적용하면:

1. **T-Box 설계**: Graphiti에서 `Preference`, `Topic`, `Intent` 타입을 Pydantic 모델로 정의 → *관심사의 "종류" 스키마*
2. **A-Box 채우기**: 챗봇 Q&A 로그를 `add_episode()`로 입력 → *실제 관심사 노드 축적*
3. **운영 전략**: **T-Box(스키마)는 안정적으로 유지**하고, **A-Box(실제 사실)만 지속 업데이트** → 시간에 따른 관심사 변화를 효율적으로 추적 ⏱️


---





## 🔍 Graphify에는 T-Box / A-Box가 있나요?

**결론부터 말씀드리면: "있다" — 단, OWL/RDF 방식이 아닌 자체 방식으로 암묵적으로 존재합니다!**

---

## 📐 Graphify의 구조 분석

Graphify는 공식적으로 T-Box/A-Box 용어를 사용하지 않지만, **내부 구조를 보면 그 역할을 하는 계층이 분리**되어 있어요:

| 온톨로지 개념 | Graphify에서의 대응 | 설명 |
|---|---|---|
| **T-Box (스키마/규칙)** | **엣지 타입 정의** (`calls`, `imports`, `inherits`, `mixes_in`, `contains`) | "어떤 관계 종류가 있는지" 미리 정의 |
| **A-Box (인스턴스/사실)** | **`graph.json`의 실제 노드·엣지** | "실제로 어떤 파일이 어떤 함수를 호출하는지" 구체적 사실 |
| **신뢰도 태그** | `EXTRACTED` / `INFERRED` / `AMBIGUOUS` | A-Box 사실의 출처와 확신도 표기 (Graphify 고유 기능!) |

```
T-Box 역할 (Graphify에 내장된 엣지 타입 "규칙")
  └─ calls, imports, inherits, mixes_in, contains, documents ...

A-Box 역할 (graph.json에 저장되는 실제 데이터)
  └─ auth.py  --[calls]--> db.connect()    [EXTRACTED]
  └─ UserModel --[inherits]--> BaseModel   [EXTRACTED]  
  └─ config.py --[used_by]--> api_server   [INFERRED]
```

---

## 🆚 엄밀한 T-Box/A-Box vs Graphify 비교

| 구분 | 정통 OWL 온톨로지 | Graphify |
|---|---|---|
| **T-Box 명시성** | ✅ OWL 파일로 명시적 선언 | ⚠️ 코드에 하드코딩(암묵적) |
| **T-Box 수정** | 자유롭게 클래스/관계 추가 가능 | 엣지 타입은 Graphify 버전업으로만 변경 |
| **A-Box 저장** | 트리플스토어(RDF), Neptune 등 | `graph.json` (JSON 파일) |
| **추론(Inference)** | HermiT, Pellet 등 OWL 추론기 | INFERRED 태그(LLM 기반 추론) |
| **쿼리 언어** | SPARQL | `graphify query/path/explain` CLI |
| **커스텀 온톨로지** | ✅ 완전 자유 | ❌ 사용자 정의 불가 |

---

## 🤔 Graphify에서 T-Box/A-Box가 꼭 필요한가요?

**챗봇 Q&A → 사용자 관심사 그래프에 맞게 생각해 보면:**

### ✅ T-Box/A-Box가 **필요하지 않은** 경우
> Graphify를 **코드/문서 그래프 탐색** 용도로만 쓸 때
- Graphify 내장 엣지 타입(calls, imports 등)으로 충분
- 코드베이스 구조 파악, 영향도 분석 등은 별도 온톨로지 불필요
- `graphify query "이 모듈에 의존하는 건?"` 같은 질문에는 현재 구조로 OK

### ⚠️ T-Box/A-Box가 **필요한** 경우
> **도메인 커스텀 온톨로지**가 필요한 경우
- 사용자 관심사 유형(Preference, Topic, Intent)을 **직접 정의**하고 싶을 때
- 관심사 간 계층 관계(예: `AWS관심사 ⊑ IT관심사`) 를 추론에 활용하고 싶을 때
- **Graphify로는 불가** → Graphiti(Pydantic 모델), OWL/RDF 도구 필요!

---

## 🏗️ 목적에 맞는 T-Box 필요 여부 판단표

```
목적                              Graphify만으로 충분?   T-Box/A-Box 필요?
────────────────────────────────────────────────────────────────
코드 구조 이해, 의존 분석            ✅ 충분                불필요
문서/PDF → 개념 그래프 추출          ✅ 충분                불필요
챗봇 Q&A → 관심사 분석              ⚠️ 배치처리 가능        도움이 됨
관심사 유형 직접 정의 (커스텀)        ❌ 불가                반드시 필요
시간 축 변화 추적 (Bi-temporal)     ❌ 불가                필요 (Graphiti!)
의미론적 추론 (A ⊑ B → 자동도출)    ❌ 불가                반드시 필요
```

---

## 💡 결론 요약

| | Graphify | Graphiti | OWL 온톨로지 |
|---|---|---|---|
| **T-Box 존재** | 암묵적(내장) | Pydantic 모델로 명시 | OWL 파일로 완전 명시 |
| **A-Box 존재** | graph.json | Neo4j/Neptune 노드·엣지 | 트리플스토어 |
| **커스텀 스키마** | ❌ | ✅ | ✅ |
| **OWL 추론** | ❌ | ❌ | ✅ |
| **사용 난이도** | 매우 쉬움 | 중간 | 어려움 |
| **Q&A 관심사 추적 적합성** | 배치용 보조 | **⭐ 1순위** | 과도하게 복잡 |

> 📌 **핵심 한 줄 정리:**  
> Graphify는 **T-Box/A-Box 개념을 암묵적으로 내장**하고 있지만, **커스텀 도메인 온톨로지 + 시간 추적**이 필요한 경우엔 **Graphiti의 Pydantic 기반 명시적 T-Box**가 훨씬 더 적합합니다! 🎯

---






