
from pydantic import BaseModel, Field
from typing import Literal, Optional
 
 
class ProjectPlan(BaseModel): # for the planner 
    project_name: str = Field(..., description="Short, filesystem-safe project name using underscores, e.g. 'calculator_app'.")

    description: str = Field(..., description="One-paragraph summary of what the app does and its core purpose.")

    app_type: Literal["web_app", "cli_tool", "api", "script"] = Field(..., description="The category of application being built; determines file structure conventions.")

    tech_stack: list[str] = Field(..., min_length=1, description="Languages/frameworks needed, e.g. ['Python', 'Flask', 'HTML/CSS'].")

    core_features: list[str] = Field(..., min_length=1, max_length=8,description="Concrete, implementable features the app must support -- not vague goals.")


    constraints: list[str] = Field(default_factory=list,description="Explicit limitations or requirements from the user's request, e.g. 'no external libraries'.")
 
 
class FileTask(BaseModel): # this is for the file means see every file should have this all properties and like this in the architecture we have the list of files 
    filename: str = Field(..., description="Relative file path to create, e.g. 'app.py' or 'templates/index.html'.")

    file_type: Literal["backend", "frontend", "config", "test"] = Field(..., description="Role of this file in the project; guides the Coder agent's generation approach.")

    purpose: str = Field(..., description="One-sentence description of what this specific file is responsible for.")

    key_functions: list[str] = Field(default_factory=list,description="Named functions/classes this file must define, e.g. ['add(a, b)', 'subtract(a, b)'].")
    
    depends_on: list[str] = Field(default_factory=list,description="Other filenames this file imports from or relies on -- used to keep imports consistent across files.")
 

class ArchitectOutput(BaseModel):
    files: list[FileTask] = Field(..., min_length=1, description="Complete list of files needed to fulfill the project plan.") # list of files and every file is the pydantic object of the schema {File}


    build_order: list[str] = Field( ...,description="Filenames in the order they must be generated, so dependencies exist before files that import them.")
 
 
class ExecutionResult(BaseModel):
    filename: str

    success: bool = Field(..., description="Whether the file executed/imported without errors.")

    error_message: Optional[str] = Field(default=None, description="Full error traceback if execution failed, else null.")


    error_type: Optional[Literal["syntax", "import", "runtime", "logic"]] = Field(default=None, description="Category of failure -- helps the Fixer node target its correction.")