from langchain_core.messages import SystemMessage,HumanMessage,AIMessage
from langgraph.graph import StateGraph,START,END
from pydantic import Field
from typing import Annotated,TypedDict
from langgraph.types import Command
from schemas import *
from langchain_groq import ChatGroq
from dotenv import load_dotenv
import subprocess # for executor
#from langgraph.store.memory import InMemoryStore
#from langgraph.checkpoint.memory import MemorySaver
import sqlite3
from langgraph.checkpoint.sqlite import SqliteSaver


import os
load_dotenv()


llm=ChatGroq(model='openai/gpt-oss-120b')
llm2=ChatGroq(model="qwen/qwen3.6-27b",model_kwargs={"reasoning_effort":'none'}) # because the model is a resoning model it writes between <think> 'response' <think> so when in code u invoke it in code the model will also write thi <think> tag a d it is a string with no variable defined for it 

#Nodes


class state(TypedDict):
        user_request: str                              # original user prompt
        plan: ProjectPlan                               # Planner node output
        architecture: ArchitectOutput                   # Architect node output
        project_path: str                               # folder path where files get written
    
        current_file_index: int                         # which file in build_order we're on
        generated_files: dict[str, str]                 # filename -> generated code (text)
        execution_results: dict[str, ExecutionResult]    # filename -> execution outcome
        retry_counts: dict[str, int]                     # filename -> number of retries so far
    



PLANNER_SYSTEM_PROMPT="""You are a senior software architect responsible for creating
high-level project plans from natural language requests.
 
Your responsibilities:
1. Determine the app_type: web_app, cli_tool, api, or script -- based on what the user
   is actually asking for, not assumptions.
2. Choose the MINIMAL but complete tech_stack needed. Do not over-engineer -- if the
   user asks for a simple calculator, do not add a database or authentication.
3. List core_features as concrete, implementable actions a developer could directly
   build -- e.g. "Add button that sums two number inputs", NOT vague goals like
   "good user experience".
4. Capture any constraints explicitly stated or clearly implied by the user
   (e.g. "must run in browser", "no external libraries", "keep it under 3 files").
5. Write a one-paragraph description summarizing the app's purpose clearly.
 
Be precise. Avoid scope creep -- only include what the user actually asked for.
Do not invent features the user did not request.
"""
 

def Planner(state:state) -> dict :
        plannerr_llm = llm.with_structured_output(ProjectPlan) 

        result=plannerr_llm.invoke([SystemMessage(content=PLANNER_SYSTEM_PROMPT),HumanMessage(content=f"user_request : {state['user_request']}")])
        
        return {'plan':result}




from langgraph.types import interrupt

#In Python, model_dump() is a built-in method in Pydantic V2 used to convert a data model into a standard Python dictionary (dict)

def HITL_ApprovePlan(state: state) -> dict: # human in the loop after we get our plan
    plan = state['plan']

    user_decision = interrupt({
        "message": "Here is the project plan. Approve or provide edits.",
        "plan": plan.model_dump()
    })

    # user_decision comes back from frontend when resumed
    if user_decision.get("approved"):
        return {}  # no state change, just continue
    else:
        # user gave edits as plain text -> feed back into plan as a note
        return {"plan": plan.model_copy(update={"constraints": plan.constraints + [user_decision.get("edits", "")]})}



 
ARCHITECT_SYSTEM_PROMPT = """You are a senior software architect responsible for breaking
a high-level project plan into specific, file-level engineering tasks.
 
Your responsibilities:
1. Based on the given plan (app_type, tech_stack, core_features), decide the COMPLETE
   list of files needed -- no more, no fewer than necessary.
2. For each file, specify:
   - file_type: backend, frontend, config, or test
   - purpose: one clear sentence describing its responsibility
   - key_functions: named functions/classes it must define (if applicable)
   - depends_on: other filenames it imports from or relies on
3. Produce a build_order: a list of filenames in the correct sequence, ensuring that
   any file another file depends on is built BEFORE it.
4. Keep the file count minimal -- do not split things into unnecessary extra files.
   For a simple app, 2-4 files is often enough.
 
Be precise about function names and dependencies -- this is what keeps the generated
code consistent when multiple files are written separately.
"""

 


def architecture(state:state):
        archi_llm=llm.with_structured_output(ArchitectOutput)

        plan=state['plan']
        

        result=archi_llm.invoke([SystemMessage(content=ARCHITECT_SYSTEM_PROMPT), HumanMessage(content=f"Project plan:\n {plan.model_dump_json(indent=2)}")])

        return{'architecture': result}



CODER_SYSTEM_PROMPT = """You are a senior software engineer writing ONE file at a time
for a larger project. Write clean, complete, working code for the requested file only.

Rules:
- Only output the raw code for this file -- no explanations, no markdown fences.
- Use the exact function/class names specified in key_functions.
- If this file depends on other files, use the exact function names and signatures
  shown in their already-generated code, so imports work correctly.
- Write production-quality code: no placeholders, no "TODO", fully working logic.
"""

def Coder(state: state) -> dict:
    current_file = state['architecture'].files[state['current_file_index']] # the current file the files will be written one by one 
    dependency_code = "\n\n".join(
        f"# {dep} (already written):\n{state['generated_files'].get(dep, '')}"
        for dep in current_file.depends_on
    )

    messages = [
        SystemMessage(content=CODER_SYSTEM_PROMPT),
        HumanMessage(content=f"""
File to write: {current_file.filename}
Purpose: {current_file.purpose}
Required functions: {current_file.key_functions}

Dependency code available:
{dependency_code or 'None'}
""")
    ]

    result = llm2.invoke(messages)   # plain invoke, no schema -- raw text  
    code = result.content

    file_path = f"{state['project_path']}/{current_file.filename}" # so the generated file or code it is stored in the current file and this is the path 

    print(f"Trying to write to: {file_path}") 
    os.makedirs(os.path.dirname(file_path), exist_ok=True)


    
    
    with open(file_path, 'w',encoding='utf-8')as f: # writing the code gen by the codeer 
        f.write(code) 

    updated_files = {**state['generated_files'], current_file.filename: code} # updating the current file with the written code
    return {"generated_files": updated_files} 
        


import subprocess   

def Executor(state: state) -> dict:# it will run the generated file or code 
    current_file = state['architecture'].files[state['current_file_index']] # the current file stored in the state 
    file_path = f"{state['project_path']}/{current_file.filename}" # the path of the current file 

    outcome = subprocess.run(  #this subprocess library will run the file  
    ["python", file_path],
    input="1\n70\n3\n",
    capture_output=True, 
    text=True,
    timeout=10
)

    if outcome.returncode == 0:    
        result = ExecutionResult(filename=current_file.filename, success=True) # if the code is error free and runs without errors in code 
    else:
        result = ExecutionResult(
            filename=current_file.filename,
            success=False,
            error_message=outcome.stderr
        )

    return {"execution_results": {**state['execution_results'], current_file.filename: result}}
        

# condtional edge helping function after executoe this function will decide 
#def route_after_execution(state: state) -> str:
#    current_file = state['architecture'].files[state['current_file_index']]
#    result = state['execution_results'][current_file.filename]
#    retries_done = state['retry_counts'].get(current_file.filename, 0)
#    if result.success:
#        return "move_to_next_file"
#    elif retries_done < 3:          #maximun retries 
#        return "fixer"
#    else:
#        return "give_up"

# below is the updated code for conditional edge the problem was the current_file was not incrementing means this file work is done and move to the next file 
    
def route_after_execution(state: state) -> str: # the router function from here it will go to either fixer packager or move to the next file(if the code has no error)
    current_file = state['architecture'].files[state['current_file_index']]
    result = state['execution_results'][current_file.filename] # we are passing the current created file to the executor node to execute it that node will say if the code is perfect or any error came if any error comes it will return false else true if there is no error 
    retries_done = state['retry_counts'].get(current_file.filename, 0) # max retries is 3 if we never set the max retries the agent may be generated the code infinitely

    if result.success: # router type decision
        if state['current_file_index'] + 1 < len(state['architecture'].files): 
            return "move_to_next_file"
        return "done"  # all files finished
    elif retries_done < 3:
        return "fixer"
    else:
        return "give_up"
    

def move_to_next_file(state: state) -> dict: # as soon as one file is generated and if if it is error free and the executor ran it then we move to the next file
    return {"current_file_index": state["current_file_index"] + 1}
    


def Fixer(state: state) -> dict: # when the code is wrong or any error occur then this fixer node will fix it this node will look at the current file arror and try to fix it the max retry is 3 
    current_file = state['architecture'].files[state['current_file_index']]
    error = state['execution_results'][current_file.filename].error_message
    broken_code = state['generated_files'][current_file.filename]

    messages = [
        SystemMessage(content=CODER_SYSTEM_PROMPT),
        HumanMessage(content=f"""
    This code for {current_file.filename} failed with this error:
    {error}

    Broken code:
    {broken_code}

    Fix it and return the corrected full file.
    """)
    ]

    result = llm2.invoke(messages)
    fixed_code = result.content

    file_path = f"{state['project_path']}/{current_file.filename}"
    with open(file_path,'w', encoding="utf-8") as f:
        f.write(fixed_code)

    updated_files = {**state['generated_files'], current_file.filename: fixed_code}
    retries = {**state['retry_counts'], current_file.filename: state['retry_counts'].get(current_file.filename, 0) + 1}
    return {"generated_files": updated_files, "retry_counts": retries}


config={'configurable':{'thread_id':'thread_1'}}
import shutil # to make a zip

def Packager(state: state) -> dict: # for combining the files and making zip
    shutil.make_archive(state['project_path'], 'zip', state['project_path'])
    return {}


os.makedirs("./generated_projects/test1", exist_ok=True) # the path of the folder here all this generated file will be saved according to user and no of files 

graph = StateGraph(state)

graph.add_node("planner", Planner)
graph.add_node("hitl", HITL_ApprovePlan)
graph.add_node("architect", architecture)
graph.add_node("coder", Coder)
graph.add_node("executor", Executor)
graph.add_node("fixer", Fixer)
graph.add_node("packager", Packager)
graph.add_node("move_to_next_file",move_to_next_file)

graph.add_edge(START, "planner")
graph.add_edge("planner", "hitl")
graph.add_edge("hitl", "architect")

graph.add_edge("architect", "coder")
graph.add_edge("coder", "executor")

graph.add_conditional_edges(
    "executor",
    route_after_execution,
    {
        "move_to_next_file": "move_to_next_file",
        'done':'packager',
        "fixer": "fixer",
        "give_up": "packager"
    }
)
graph.add_edge("fixer", "executor")
graph.add_edge('move_to_next_file' , 'coder')
graph.add_edge("packager", END)


#what is check same thead exactly mean

#SQLite has a safety rule by default: a database connection can only be used by the same thread (the same "worker") that created it. If a different thread tries to use that same connection, SQLite normally raises an error — because SQLite wasn't originally designed to safely handle multiple threads touching the same connection at once (risk of data corruption if two threads write at the same time).
#check_same_thread=False tells SQLite: "turn off that safety check, allow other threads to use this connection too."
checkpoint=SqliteSaver(conn=sqlite3.connect(database="coder_db",check_same_thread=False))
app = graph.compile(checkpointer=checkpoint)


if __name__ == "__main__":
    test_config = {'configurable': {'thread_id': 'manual_test'}}

    result = app.invoke({
        "user_request": "Build a simple Python script that adds two numbers",
        "project_path": "./generated_projects/manual_test",
        "current_file_index": 0,
        "generated_files": {},
        "execution_results": {},
        "retry_counts": {}
    }, config=test_config)

    print("PAUSED AT:", result)
    print("STREAMING RESUME")
    for step in app.stream(Command(resume={"approved": True}), config=test_config):
        print(step)
        print("---")