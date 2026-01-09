# 📄 사내문서 RAG

## 문서 처리·청킹 전략 설계 및 데이터 분포 분석 보고서

---

## 1. 개요

본 문서는 사내문서 RAG 프로젝트에서

**PDF/XLSX 문서 수집 → 품질 판별 → 청킹 전략 적용 → Elasticsearch 색인**까지의 파이프라인 설계와

실제 색인 결과를 기반으로 한 **문서 유형 분포 분석 결과**를 정리한 보고서이다.

본 단계의 목적은 다음과 같다.

- 사내문서 특성에 맞는 **청킹 전략 정합성 확보**
- 색인된 데이터의 **구조적 의미 혼선 제거**
- 실제 문서 분포를 기반으로 **향후 RAG 검색 튜닝 방향 도출**

---

## 2. 전체 파이프라인 구조

### 2.1 처리 흐름 요약

1. **PDF/XLSX 로컬 수집**
2. **PDF 페이지 단위 품질 판별**
    - image-heavy / low-text / fragmented-text 판별
    - 텍스트 충분 시 image-heavy 단독 스킵 금지
3. **문서 프로파일 산출**
    - 평균 텍스트 길이
    - 짧은 줄 비율
    - kept 페이지 비율
4. **청킹 프로파일 선택**
    - 문서 성격에 따라 chunk_size / overlap 결정
5. **청킹**
    - RecursiveCharacterTextSplitter 기반
6. **Elasticsearch 색인**
    - 벡터 + 메타데이터 저장

---

## 3. 청킹 전략 설계 원칙

### 3.1 청킹 알고리즘 vs 청킹 프로파일 분리

본 프로젝트에서는 다음 원칙을 채택하였다.

| 구분 | 의미 |
| --- | --- |
| **chunk_strategy** | 실제 청킹 알고리즘 |
| **chunk_profile** | 문서 성격에 따른 파라미터 선택 결과 |

### 적용 이유

- 현재 모든 문서는 **RecursiveCharacterTextSplitter**로 청킹됨
- 문서마다 달라지는 것은 알고리즘이 아니라 **chunk_size / overlap**
- 따라서 문서 성격(`fragmented_text` 등)을 `chunk_strategy`에 저장하면 의미 혼선 발생

### 최종 설계

```
chunk_strategy = "character_recursive"  (고정)
chunk_profile  = 문서 성격 라벨

```

---

## 4. Chunk Profile 정의

### 4.1 PDF 문서용 프로파일

### ① continuous_text

- **의미**: 연속 문장 위주의 규정/계약/정책 문서
- **선택 조건**
    - kept_ratio ≥ 0.75
    - avg_text_len ≥ 900
    - short_line_ratio ≤ 0.35
- **청킹 파라미터**
    - chunk_size = 1200
    - chunk_overlap = 150

---

### ② fragmented_text

- **의미**: 슬라이드형·박스형 텍스트 중심 문서
- **선택 조건**
    - avg_text_len < 550 **또는**
    - short_line_ratio ≥ 0.55
- **청킹 파라미터**
    - chunk_size = 700
    - chunk_overlap = 220

---

### ③ mixed_default

- **의미**: 연속 텍스트와 조각 텍스트가 혼합된 일반 문서
- **청킹 파라미터**
    - chunk_size = 1000
    - chunk_overlap = 180

---

### 4.2 XLSX 문서용 프로파일

| 프로파일 | 조건 | chunk_size | overlap |
| --- | --- | --- | --- |
| xlsx_large | 전체 텍스트 ≥ 200,000 | 1300 | 180 |
| xlsx_default | 중간 규모 | 1000 | 180 |
| xlsx_small | 전체 텍스트 ≤ 30,000 | 800 | 150 |

---

## 5. Elasticsearch 인덱스 구조

### 5.1 핵심 메타 필드

| 필드명 | 의미 |
| --- | --- |
| pdf_id | 문서 ID |
| page_no | 원본 페이지 번호 |
| chunk_id | 문서 내 chunk 순번 |
| chunk_strategy | 청킹 알고리즘 (`character_recursive`) |
| chunk_profile | 문서 성격 라벨 |
| chunk_profile_reason | 프로파일 선택 근거 |
| chunk_size / overlap | 적용된 청킹 파라미터 |

---

## 6. 실제 색인 데이터 분포 분석

### 6.1 chunk_profile 분포 결과

| chunk_profile | 문서 수 | 비율 |
| --- | --- | --- |
| fragmented_text | 444 | 약 73% |
| mixed_default | 108 | 약 18% |
| continuous_text | 60 | 약 10% |
| xlsx_small | 4 | 미미 |

---

### 6.2 분포 해석

- **사내문서의 대부분은 슬라이드형·조각 텍스트 구조**
- 규정/계약서형 문서는 상대적으로 소수
- 본 프로젝트는 **fragmented_text 대응 성능이 전체 RAG 성능을 좌우**

이는 실제 기업 내부 문서 구성(PPT, 설명자료, 안내 슬라이드 중심)과도 일치한다.

---

## 7. 설계 타당성 평가

### 긍정적 신호

- image-heavy 페이지 스킵 완화 정책으로 **의미 있는 텍스트 손실 최소화**
- fragmented_text 비중이 높음에도 **chunk_overlap 확장 전략이 적절히 작동**
- 청킹 알고리즘과 문서 프로파일 의미 분리로 **확장 가능성 확보**

### 현재 단계 결론

> 본 단계는 “데이터 준비 + 구조 설계 + 분포 검증”이 완료된 상태이며,
> 
> 
> 추가적인 청킹 재설계 없이 검색 단계로 진입 가능하다.
> 

---

## 8. 다음 단계 제안

### 우선 적용 후보

1. **chunk_profile 기반 검색 파라미터 분기**
    - fragmented_text → top_k 증가
2. **동일 문서 내 인접 chunk 묶음 전략**
3. **continuous_text 대상 BM25 가중 하이브리드 검색**

---

## 9. 요약

- 청킹 전략과 문서 성격을 분리함으로써 **의미 정합성 확보**
- 실제 색인 데이터 분포를 통해 **사내문서 특성 명확화**
- 현 구조는 **RAG 검색 튜닝으로 바로 확장 가능한 안정 상태**

# 사내문서 RAG 프로젝트 (PDF) 구축 보고서

## 0. 문서 정보

- 문서명: 사내문서 RAG 프로젝트 – PDF 인덱싱/검색/근거 검증 구축 보고서
- 작성일: 2026-01-08
- 작성자: 김수연
- 버전: v1.0
- 시스템 구성: FastAPI + Elasticsearch(Vector) + Embeddings + PDF 렌더링(근거)

---

## 1. 목적 및 배경

### 1.1 목적

사내 PDF 문서(규정, 매뉴얼 등)를 대상으로 자연어 질의에 대해:

1. **근거 기반 답변 생성(RAG)**
2. 답변의 근거를 **PDF 페이지 단위로 즉시 검증(UI)**
    
    할 수 있는 관리자용 콘솔을 구현한다.
    

### 1.2 배경/문제 정의

- PDF는 텍스트/표/이미지 혼합 구조로 인해 단순全文 LLM 투입 시 비용/지연이 크고 근거 추적이 어려움
- 이미지 비중이 높은 문서(슬라이드형 PDF)에서 텍스트 추출 품질 판정이 과도 스킵되는 문제 발생
- 운영 관점에서 “어떤 문서가 어떤 기준으로 스킵/청킹/인덱싱되었는지” 추적 가능한 로그 필요

---

## 2. 범위 및 비범위

### 2.1 범위(In Scope)

- PDF 폴더 ingest 및 Elasticsearch 벡터 인덱싱
- 페이지 단위 텍스트 추출 및 **품질 판별(keep/skip)a**
- 문서 프로파일 기반 **청킹 전략 자동 선택**
- 벡터 검색 기반 Top-K 근거 추출 + 답변 생성
- 근거 페이지 이미지 렌더링(`/pdf/page-image`) 및 UI 표시

### 2.2 비범위(Out of Scope)

- OCR 기반 이미지 텍스트 복원(현재는 text-only 추출 중심)
- 권한/ACL 기반 문서 접근 제어(추후)
- 문서 버전 관리/증분 업데이트 정책 고도화(추후)

---

## 3. 전체 아키텍처 개요

### 3.1 구성 요소

- **FastAPI**
    - `/pdf/ingest`, `/pdf/ingest-folder`: 문서 ingest 및 색인 트리거
    - `/pdf/ask`: 질의 → 검색 → 답변/근거 반환
    - `/pdf/page-image`: 근거 페이지 이미지 렌더링(PNG)
    - StaticFiles: `/files/pdfs/{filename}` 원본 PDF 제공
- **Elasticsearch**
    - PDF 청크 문서 저장 인덱스: `settings.PDF_INDEX`
    - vector 필드에 임베딩 저장, KNN 검색 수행
- **Embedding 모델**
    - `app.core.embeddings.embed_texts()`에서 텍스트 리스트를 임베딩 벡터로 변환
    - (실제 모델명/차원은 settings 또는 embeddings.py 기준으로 기록)
- **프론트(UI)**
    - 질문 입력 → 답변 표시
    - 근거 리스트 선택 → 페이지 이미지 표시(검증)
    - 새 탭으로 원본 PDF 특정 페이지 열기

---

## 4. 데이터 흐름 (Pipeline) 상세

### 4.1 Ingest 파이프라인: PDF → Page Text → Chunk → Embedding → ES

### Step 1) PDF 페이지 텍스트 추출

- 모듈: `app/pdf/pdf_loader.py`
- 출력: 페이지별 텍스트 + 요약 통계
- 품질 판별: 이미지 비율, 텍스트 길이 등 기반으로 KEEP/SKIP 결정
- 로그: `logs/skip_pages.jsonl`에 스킵 사유 기록

### Step 2) 문서 프로파일 생성

- 모듈: `app/pdf/profile.py` → `build_doc_profile()`
- 목적: 문서 특성(텍스트 밀도/짧은 라인 비율/스킵 비율 등)을 수치화하여 전략 선택 근거로 사용

### Step 3) 청킹 전략 자동 선택

- 모듈: `app/pdf/strategy.py`
- 함수:
    - `choose_chunk_strategy(profile)`
    - `append_strategy_log(logs/chunk_strategy.jsonl, ...)`
- 결과: `strategy.name`, `chunk_size`, `chunk_overlap`, `reason`

### Step 4) KEEP 페이지 청킹

- 모듈: `app/pdf/chunker.py` → `chunk_pages()`
- 입력: `(page_no, text)` list
- 출력: `Chunk` list
    - `Chunk.page_no` 유지 (근거 페이지 추적 핵심)

### Step 5) ES 색인

- 모듈: `app/pdf/index_service.py` → `index_pdf_chunks()`
- 내부:
    - `texts = [c.text for c in chunks]`
    - `vectors = embed_texts(texts)`
    - bulk index into `settings.PDF_INDEX`

---

### 4.2 Query 파이프라인: Question → Vector Search → 근거 Top-K → Answer + Sources

- 엔드포인트: `POST /pdf/ask`
- 모듈: `app/pdf/rag_service.py` → `answer_pdf_question()`
- 반환: `answer` + `sources[]`
    - `pdf_id`, `pdf_path`, `page_no`, `chunk_id`, (snippet 등)
    - `pdf_url`, `viewer_url`, `page_image_url`

> 근거 검증 UI는 sources[]의 viewer_url(원본 PDF) 또는 page_image_url(렌더링 이미지)을 사용해 즉시 확인 가능
> 

---

## 5. 청킹(Chunking) 기법 및 고려사항

### 5.1 청킹 방식

- 대상: **KEEP 처리된 페이지의 텍스트만**
- 청킹 알고리즘: `RecursiveCharacterTextSplitter` 기반(구현체는 chunker.py 내부)
- 메타 유지:
    - `page_no`를 chunk 메타로 유지하여 “근거=페이지” 트레이싱 가능
    - `chunk_id`는 청크 단위 식별

### 5.2 고려사항(품질/정확도/운영)

- **이미지 비중이 높아도 텍스트가 충분하면 KEEP** (정책 수정)
- `image_area_ratio` 단독으로 스킵하지 않고,
    - 텍스트 길이(`low_text`) 등과 **결합 판단**
    - 텍스트 충분 시 KEEP override
- 목적: 슬라이드/배경 이미지 PDF에서 “실제 텍스트가 있는데도 스킵되는 문제” 방지

---

## 6. 인덱싱 변수(메타데이터) 정의 및 의미

### 6.1 ES 문서 ID 설계

- `_id = f"{pdf_id}:{chunk_id}"`
- 의미:
    - 동일 문서 내 chunk 유일성 확보
    - 재색인 시 동일 chunk 교체 가능

### 6.2 ES `_source` 필드 정의 (현재 구현 기준)

| 필드 | 타입 | 의미 |
| --- | --- | --- |
| pdf_id | string | 문서 식별자(보통 파일명 기반) |
| pdf_path | string | 원본 PDF 경로(로컬) |
| page_no | int | 0-based 페이지 번호 |
| chunk_id | int | 문서 내 청크 식별자 |
| text | string | 청크 텍스트 |
| vector | float[] | 임베딩 벡터 |
| source_type | string | “pdf” (데이터 타입) |
| extract_method | string | “text_only” (추출 방식) |
| pages_total | int | 총 페이지 수 |
| pages_kept | int | 인덱싱 대상 페이지 수 |
| pages_skipped | int | 스킵 페이지 수 |
| chunk_strategy | string | 선택된 전략 이름 |
| chunk_size | int | 청킹 크기 |
| chunk_overlap | int | 청킹 오버랩 |
| chunk_strategy_reason | string | 전략 선택 사유(로그 및 설명용) |

> 주: 위 meta는 ingest 시 extra_meta로 삽입됨
> 

---

## 7. 사용 모델 및 파라미터

### 7.1 임베딩 모델

- 위치: `app/core/embeddings.py`의 `embed_texts()`
- 기록해야 할 항목(운영 표준 권장):
    - 모델명 (예: text-embedding-xxx)
    - 벡터 차원(dim)
    - 정규화 여부(normalize)
    - 배치 크기/타임아웃
    - 모델 버전 및 변경 이력

### 7.2 LLM(답변 생성) 체인

- 위치: `app/pdf/rag_service.py` 내
- 구성(현재 구현 관점에서의 표준 기술 방식):
    1. Retriever: ES KNN 검색으로 Top-K chunk 선정
    2. Context Builder: chunk 텍스트 + 메타(page_no/pdf_id) 묶어 컨텍스트 구성
    3. Generator: LLM에 질의 + 컨텍스트 투입하여 답변 생성
    4. Output: answer + sources(근거)

> 실제 프롬프트/모델명/temperature/top_p 등은 rag_service 구현 기준으로 표에 기록하는 것을 권장
> 

---

## 8. 근거 검증 UI 동작 방식

### 8.1 UI 데이터 계약(Contract)

`/pdf/ask` 응답의 `sources[]`에 아래 필드가 포함되어야 함:

- `pdf_url`: `/files/pdfs/{encoded}.pdf`
- `viewer_url`: `{pdf_url}#page={page_no+1}`
- `page_image_url`: `/pdf/page-image?file={encoded}.pdf&page_no={page_no}&zoom=2`

### 8.2 페이지 이미지 렌더링 엔드포인트

- `GET /pdf/page-image`
- 내부 동작:
    - `file` 파라미터 decode
    - `data/pdfs`에서 파일 locate
    - PyMuPDF로 page_no 렌더링 후 PNG 반환

---

## 9. 결과(현재까지 성과)

### 9.1 기능 구현 결과

- 폴더 ingest 가능(`/pdf/ingest-folder`)
- 스킵판별 로그 + 청킹 전략 로그 저장
- ES에 페이지 기반 청크 인덱싱 완료
- 질의 응답 + 근거 리스트 반환(`/pdf/ask`)
- 근거 페이지 이미지 렌더링 및 UI 표시(`/pdf/page-image` + 프론트)

### 9.2 품질 이슈 및 개선 반영

- 이슈: 이미지 비율이 1.0으로 계산되며 텍스트가 있는데도 과도 스킵
- 조치: 이미지 비율 단독 스킵 금지 + 텍스트 길이 결합 판단 + 텍스트 충분 시 KEEP override

---

## 10. 운영 표준(권장) 체크리스트

### 10.1 인덱싱/모델 변경 시 필수 기록

- Embedding 모델명/버전/차원 변경 이력
- chunk_size / overlap 변경 이력 및 성능 영향
- skip 정책 변경 이력
- 인덱스 매핑/ANN 파라미터 변경 이력

### 10.2 로그/추적성(Traceability)

- `skip_pages.jsonl` : 페이지 스킵 사유
- `chunk_strategy.jsonl` : 문서별 전략 및 사유
- (권장) query 로그: 질문, top_k, 선택 근거, latency, token usage 등

---

## 11. 리스크 및 한계

- OCR 미적용 문서(스캔본/이미지 PDF)는 text-only 추출에서 누락 가능
- 동일 파일명(서브폴더) 충돌 가능성: 현재는 basename 기반 file param 처리
- 페이지 이미지 렌더링 비용: 대용량 요청 시 캐싱 필요

---

## 12. 향후 개선 계획(Backlog)

- (우선) `page-image` 결과 캐싱 (file+page_no+zoom 키)
- (우선) 스캔 PDF에 OCR 옵션 제공(선택적, 비용 제어)
- (중기) 접근제어/권한 기반 문서 필터링
- (중기) 인덱스 증분 업데이트 및 문서 버전 관리
- (중기) 표/구조 추출 강화(테이블 파싱)