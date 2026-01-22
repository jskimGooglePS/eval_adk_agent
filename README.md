# eval_adk_agent
eval_adk_agent_automation

## 환경 정보
```
pip install pandas
pip install openpyxl
pip install google-genai
pip install google-adk
pip install "google-adk[eval]"
pip install python-box
pip freeze > requirements.txt
```

## 환경 세팅(Quick Start)
```bash
cd eval_adk_agent
python3 -m venv .venv
source .venv/bin/activate

pip install -r requirements.txt
```
### 파일 실행

```bash
python3 -m eval_adk_agent
```

## 실행 방법

### input 데이터 파일 위치
- data/input/evaluate_dataset_example.xlsx

#### input 엑셀 필수 컬럼
- query: str
- answer_result: json

### output 데이터 파일 위치
- data/output/evaluate_results.xlsx

#### output 엑셀 필수 컬럼
- query: str
- answer_result: json
- agent_result: json
    * agent result 생성 결과
- is_type_match: bool
    * type 일치 여부 판단
- is_unit_count_match: bool
    * unit의 수 일치 여부 판단
- is_query_similarity: bool
    * 모든 query의 유사도가 0.5보다 클때 True
- query_similarity_score: list[str]
    * 모든 query의 유사도 리스트
    * is_unit_count_match수가 불일치할 경우 []
