from planner_agent.runner import runner, session, APP_NAME, USER_ID, SESSION_ID

from google.genai import types # For creating message Content/Parts

import pandas as pd
import asyncio
from google import genai

import numpy as np
import json
import os 

import yaml
from box import Box

conf_url = 'config.yaml'
with open(conf_url, 'r') as f:
    config_yaml = yaml.load(f, Loader=yaml.FullLoader)
    config = Box(config_yaml)

os.environ["GOOGLE_GENAI_USE_VERTEXAI"]=config.google_genai_use_vertexai
os.environ["GOOGLE_CLOUD_PROJECT"]=config.google_cloud_project
os.environ["GOOGLE_CLOUD_LOCATION"]=config.google_cloud_location

EXCEL_PATH = config.excel_path
OUTPUT_PATH = config.output_path
EMBEDDING_MODEL: str = config.embedding_model

client = genai.Client()

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
        'is_type_match': False,
        'is_unit_count_match': False,
        'is_query_similarity': False,
        'query_similarity_score': []
    }

    try:
        # 1. 데이터 추출 및 파싱
        res_text = str(row['agent_result']) # 위에서 df['agent_answer']로 저장했으므로 컬럼명 확인
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
            res['is_type_match'] = True

        # --- [조건 2] Data Units 검증 ---
        # 이 부분 Unit의 이름이 다를 수 있어 유의 필요
        res_sq_list = res_data.get('sub_query', [])
        ans_sq_list = ans_data.get('sub_query', [])

        res_query_list = [res_sq_query.get("query") for res_sq in res_sq_list for res_sq_query in res_sq.get("data_units",[]) ]
        ans_query_list = [ans_sq_query.get("query") for ans_sq in ans_sq_list for ans_sq_query in ans_sq.get("data_units",[]) ]

        def cosine_similarity(v1, v2):
            dot_product = np.dot(v1, v2)
            norm_v1 = np.linalg.norm(v1)
            norm_v2 = np.linalg.norm(v2)
            if norm_v1 == 0 or norm_v2 == 0:
                return 0.0
            return round(float(dot_product / (norm_v1 * norm_v2)),2)

        if (len(res_sq_list) == len(ans_sq_list)) & (len(res_query_list) == len(ans_query_list)):
            res['is_unit_count_match'] = True

            all_contents = res_query_list + ans_query_list

            response = client.models.embed_content(
                model=EMBEDDING_MODEL,
                contents=all_contents,
                config=types.EmbedContentConfig(task_type="SEMANTIC_SIMILARITY"),
            )        

            all_embeddings = [e.values for e in response.embeddings]

            split_index = len(res_query_list)

            emb_res_list = all_embeddings[:split_index]
            emb_ans_list = all_embeddings[split_index:]
            score_list = [cosine_similarity(emb_res, emb_ans) for emb_res, emb_ans in zip(emb_res_list,emb_ans_list)]
            if all(s > 0.5 for s in score_list): 
                res['is_query_similarity'] = True

            res['query_similarity_score'] = str(score_list)

    except Exception as e:
        print(f"Error during validation at row {row.name}: {e}")
        
    return pd.Series(res) # 핵심: 여러 컬럼으로 반환하기 위해 Series 사용

async def run_conversation(input_path, output_path): # 인자 path가 필요 없다면 제거
    df = pd.read_excel(input_path)

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
    df['agent_result'] = results

    # 2. 검증 수행 (apply 결과로 생성된 3개 컬럼을 기존 df에 결합)
    validation_df = df.apply(check_match, axis=1)
    df = pd.concat([df, validation_df], axis=1)

    # 3. 엑셀 저장
    df.to_excel(output_path, index=False)
    print(f"\n✅ 검증 결과(3개 컬럼)가 포함된 파일이 {output_path}에 저장되었습니다.")

if __name__ == "__main__": # Ensures this runs only when script is executed directly
    print("Executing using 'asyncio.run()' (for standard Python scripts)...")
    try:
        # This creates an event loop, runs your async function, and closes the loop.
        asyncio.run(run_conversation(EXCEL_PATH, OUTPUT_PATH))
    except Exception as e:
        print(f"An error occurred: {e}")
