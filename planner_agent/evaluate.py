from planner_agent.runner import runner, session, APP_NAME, USER_ID, SESSION_ID

from google.genai import types # For creating message Content/Parts

import pandas as pd

import json

EXCEL_PATH = 'data/input/evaluate_dataset_example.xlsx'
OUTPUT_PATH = 'data/output/evaluate_results.xlsx' # 저장될 경로

async def call_agent_async(query: str, runner, user_id, session_id):
  """Sends a query to the agent and prints the final response."""
  print(f"\n>>> User Query: {query}")

  # Prepare the user's message in ADK format
  content = types.Content(role='user', parts=[types.Part(text=query)])

  final_response_text = "Agent did not produce a final response." # Default

  # Key Concept: run_async executes the agent logic and yields Events.
  # We iterate through events to find the final answer.
  async for event in runner.run_async(user_id=user_id, session_id=session_id, new_message=content):
      # You can uncomment the line below to see *all* events during execution
      # print(f"  [Event] Author: {event.author}, Type: {type(event).__name__}, Final: {event.is_final_response()}, Content: {event.content}")

      # Key Concept: is_final_response() marks the concluding message for the turn.
      if event.is_final_response():
          if event.content and event.content.parts:
             # Assuming text response in the first part
             final_response_text = event.content.parts[0].text
          elif event.actions and event.actions.escalate: # Handle potential errors/escalations
             final_response_text = f"Agent escalated: {event.error_message or 'No specific message.'}"
          # Add more checks here if needed (e.g., specific error codes)
          break # Stop processing events once the final response is found

  print(f"<<< Agent Response: {final_response_text}")
  return final_response_text

def check_match(row):
    # 결과 값을 저장할 기본 딕셔너리
    res = {
        'is_order_match': False,
        'is_unit_count_match': False,
        'is_query_match': False
    }

    try:
        # 1. 데이터 추출 및 파싱
        res_text = str(row['agent_answer']) # 위에서 df['agent_answer']로 저장했으므로 컬럼명 확인
        ans_text = str(row['answer_result'])

        clean_res = res_text.replace('```json', '').replace('```', '').strip()
        clean_ans = ans_text.replace('```json', '').replace('```', '').strip()
        
        res_data = json.loads(clean_res)
        ans_data = json.loads(clean_ans)

        # --- [조건 1] Order 및 Type 검증 ---
        def get_ordered_types(data):
            order = data.get('order', [])
            sub_queries = {sq.get('id'): sq.get('type') for sq in data.get('sub_query', [])}
            return [sub_queries.get(order_id) for order_id in order]

        if get_ordered_types(res_data) == get_ordered_types(ans_data):
            res['is_order_match'] = True

        # --- [조건 2 & 3] Data Units 검증 ---
        res_sub_queries = {sq.get('id'): sq for sq in res_data.get('sub_query', [])}
        ans_sub_queries = {sq.get('id'): sq for sq in ans_data.get('sub_query', [])}

        unit_count_flag = True
        query_match_flag = True

        # 정답셋의 sub_query 기준으로 에이전트 결과 비교
        for set_id, ans_sq in ans_sub_queries.items():
            res_sq = res_sub_queries.get(set_id)
            if not res_sq: # 에이전트가 해당 SET ID를 생성하지 못한 경우
                unit_count_flag = False
                query_match_flag = False
                continue

            ans_units = {u.get('id'): u.get('query') for u in ans_sq.get('data_units', [])}
            res_units = {u.get('id'): u.get('query') for u in res_sq.get('data_units', [])}

            # [조건 2] data_unit ID 개수 비교
            if len(ans_units) != len(res_units):
                unit_count_flag = False

            # [조건 3] 각 ID별 Query 내용 비교
            for unit_id, ans_query in ans_units.items():
                res_query = res_units.get(unit_id)
                if res_query != ans_query:
                    query_match_flag = False

        res['is_unit_count_match'] = unit_count_flag
        res['is_query_match'] = query_match_flag

    except Exception as e:
        print(f"Error during validation at row {row.name}: {e}")
        
    return pd.Series(res) # 핵심: 여러 컬럼으로 반환하기 위해 Series 사용

async def run_conversation(): # 인자 path가 필요 없다면 제거
    df = pd.read_excel(EXCEL_PATH)

    results = []
    for idx, row in df.iterrows():
        response = await call_agent_async(
            query=row['query'],
            runner=runner,
            user_id=USER_ID,
            session_id=SESSION_ID
        )
        results.append(response)
    
    # 1. 에이전트 답변 먼저 저장
    df['agent_answer'] = results

    # 2. 검증 수행 (apply 결과로 생성된 3개 컬럼을 기존 df에 결합)
    validation_df = df.apply(check_match, axis=1)
    df = pd.concat([df, validation_df], axis=1)

    # 3. 엑셀 저장
    df.to_excel(OUTPUT_PATH, index=False)
    print(f"\n✅ 검증 결과(3개 컬럼)가 포함된 파일이 {OUTPUT_PATH}에 저장되었습니다.")
    
    
async def run_conversation(path):
    df = pd.read_excel(EXCEL_PATH)

    results = []
    
    for idx, row in df.iterrows():
        response = await call_agent_async(query = row['query'],
                                runner=runner,
                                user_id=USER_ID,
                                session_id=SESSION_ID)
        results.append(response)
    
    df['agent_answer'] = results

    df['is_correct_type'] = df.apply(check_match, axis=1)

    df.to_excel(OUTPUT_PATH, index=False)
    print(f"\n✅ 모든 결과가 {OUTPUT_PATH}에 저장되었습니다.")

import asyncio

if __name__ == "__main__": # Ensures this runs only when script is executed directly
    print("Executing using 'asyncio.run()' (for standard Python scripts)...")
    try:
        # This creates an event loop, runs your async function, and closes the loop.
        asyncio.run(run_conversation())
    except Exception as e:
        print(f"An error occurred: {e}")
