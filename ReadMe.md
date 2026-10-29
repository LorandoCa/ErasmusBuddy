# Flow Documentation – Erasmus Guide Creator (CrewAI)

Technical documentation for the team, based on `main.py`, `content_crew.py`, `Flow_functions.py`, `models.py` and `crews_config.json`. The crews' and agents' `.jsonc` files were not analysed, so the internal behaviour of each crew is described only by what the flow code assumes.

## 1. Overview

The `GuideCreatorFlow` flow generates a personalised Markdown guide for Erasmus students. The process is:

1. It asks the user, via the terminal, for their personal and academic details (origin and destination country and university, semester).
2. For each section of the guide (currently only `bureaucracy`), it runs the corresponding crew with the inputs that crew needs.
3. It merges the results of all sections and saves the guide to `output/complete_guide.md`.
4. It asks the user whether any section fell short of their expectations (feedback loop, **still incomplete**, see section 9).

The flow is built on `crewai.flow.flow.Flow`, with a state typed via Pydantic and three steps chained with `@start` and `@listen`.

## 2. Important files

| File | Responsibility |
| --- | --- |
| `main.py` | Defines the state (`GuideCreatorState`), the flow (`GuideCreatorFlow`) and the entry points `kickoff()` and `plot()`. |
| `content_crew.py` | Loads and runs the crews from `.jsonc` files (`load_crew`). Exposes one `kickoff_*` function per crew. |
| `crews_config.json` | Declares, per section, the required input fields (`required_fields`) of each crew. |
| `Flow_functions.py` | The `pedir_input` function, which validates the text entered in the terminal. |
| `models.py` | Pydantic models for structured output (`CostEstimate`). |

In `main.py` the crew import comes from `guide_creator_flow.crews.content_crew.content_crew`, meaning `content_crew.py` lives inside the `guide_creator_flow` package, and the crews are located under `agents/<section>/...` next to that file.

## 3. Execution flow diagram
``
```
@start get_user_input
   |   asks for inputs, validates them, fills state.personal_info
   v
@listen write_and_compile_guide
   |   reads crews_config.json
   |   runs iterative rounds (up to MAX_ROUNDS = 3):
   |     |-- runs pending sections concurrently (asyncio.gather) using SECTION_RUNNERS
   |     |-- checks outcomes with extract_questions(section, outcome)
   |     |-- IF questions present:
   |     |     collects user answers sequentially (collect_user_answers)
   |     |     injects answers into extra_inputs for the next round
   |     '-- ELSE (no questions):
   |           saves outcome.raw to state.sections_content
   |           marks section as completed
   |   compiles and saves output/complete_guide.md
   v
@listen feedback_loop
       asks Y/N, picks the section to correct
       (the correction itself is not implemented yet)

```
## 4. State model

```python
class GuideCreatorState(BaseModel):
    personal_info: Dict[str, str] = {}
    sections: List[str] = ["bureaucracy"]
    sections_content: Dict[str, str] = {}
```

| Field | Type | Description |
| --- | --- | --- |
| `personal_info` | `Dict[str, str]` | The user's answers. Keys used: `origin_country`, `destination_country`, `origin_university`, `destination_university`, `semester`. |
| `sections` | `List[str]` | Sections to generate, in order. Only `bureaucracy` by default. A comment in the code lists `Finance`, `Housing` and `Commute` as future ones. |
| `sections_content` | `Dict[str, str]` | Markdown text returned by each crew (`result.raw`), indexed by section name. |

**How it evolves through the flow:** `get_user_input` fills `personal_info`; `write_and_compile_guide` fills `sections_content`; `feedback_loop` only reads `sections_content` to list the sections.

## 5. Description of each step

### 5.1 `get_user_input` (`@start`)

Uses `pedir_input` to ask in the terminal for the following fields: origin country, destination country, origin university, destination university and semester (example in the prompt: `Fall 2024`).

There is one extra validation: the destination country must differ from the origin country (compared case-insensitively). If they are the same, a message is shown and the destination country is asked for again. This message is in Portuguese, while the prompts are in English.

The method returns `self.state`, which the next step receives as an argument.

A comment in the code indicates that this is where any new inputs required for the guide should be added.

### 5.2 `write_and_compile_guide` (`@listen(get_user_input)`)

1. **Initialization & Concurrency Setup:** 
   - Reads `crews_config.json`.
   - Initializes a concurrency semaphore (`MAX_CONCURRENT_CREWS = 2`) and tracking structures (`completed` list and `extra_inputs` dictionary).

2. **Iterative Execution Loop (Up to `MAX_ROUNDS = 3`):**
   - Filters `state.sections` to identify pending sections.
   - Executes pending sections concurrently using `asyncio.gather` and `SECTION_RUNNERS.get(section.lower())`. Each runner receives `personal_info`, `crews_config`, and any section-specific `extra_inputs` collected from previous rounds.
   - **Outcome Evaluation:**
     - **Exception / Crash:** Logs the error and marks the section as completed to avoid infinite retries.
     - **Question Check:** Invokes `extract_questions(section, outcome)` to inspect the crew's output.
     - **No Questions:** Saves `outcome.raw` into `state.sections_content[section]` and marks the section as completed.
     - **Questions Asked:** Stores the questions to prompt the user.
   - **User Input Collection:** If questions were raised, sequentially prompts the user via `collect_user_answers(section, questions)` (to prevent overlapping terminal prompts) and stores the answers in `extra_inputs[section]` for the next round.
   - If no questions are raised during a round or all sections are completed, the loop breaks early.

3. **Guide Compilation & Export:**
   - Compiles the final guide starting with `# Your Personalized Erasmus Guide`, followed by the Markdown content of each section in the order defined by `state.sections`.
   - Ensures the output directory exists using `os.makedirs("output", exist_ok=True)`.
   - Writes the compiled guide to `output/complete_guide.md` using UTF-8 encoding and returns `self.state`.
### 5.3 `feedback_loop` (`@listen(write_and_compile_guide)`)

Asks `Y/N` whether any section fell short of expectations. If the answer is `Y`, it lists the sections present in `sections_content` and asks the user to pick one, by number or by name (case-insensitive), repeating until the choice is valid.

After that the method ends with a bare `return` and does nothing else: it does not ask for a description of the problem, does not call any correction crew and does not update the guide. It is yet to be implemented.

## 6. Crews and agents

### 6.1 Crew registry

There are two registry levels that must be kept in sync:

- `CREWS` in `main.py`: maps the section name to the function to call. It contains `bureaucracy` and `finances`.
- `CREW_FILES` in `content_crew.py`: maps the crew name to the `.jsonc` file that defines it.

| Crew | Function | `.jsonc` file (relative to `agents/`) | Required fields |
| --- | --- | --- | --- |
| `bureaucracy` | `kickoff_bureaucracy_crew` | `bureaucracy/Report_crew/crew_bureaucracy.jsonc` | `origin_country`, `destination_country`, `origin_university`, `destination_university`, `semester` |
| `bureaucracy_repair` | `kickoff_bureaucracy_crew_repair` | `bureaucracy/Feedback_crew/crew_bureaucracy_repair.jsonc` | `user_request`, `section`, `section_content` |
| `finances` | `kickoff_finances_crew` | `finances/finances_crew.jsonc` | `city`, `country` |

### 6.2 How a section runner / crew is executed

Execution is handled asynchronously through **Section Runners** mapped in `SECTION_RUNNERS` (imported from `Flow_functions.py`), rather than calling crew functions directly from the flow:

1. **Runner Lookup:** In `write_and_compile_guide`, the flow retrieves the corresponding runner function using `SECTION_RUNNERS.get(section.lower())` (e.g., `run_bureaucracy`, `run_finances`).
2. **Runner Function Signature:** Each runner function is an `async` function accepting three parameters:
   `runner(personal_info, crews_config, extra_inputs)`
3. **Input Assembly & Injection:**
   * Reads the required fields for the section from `crews_config.json`.
   * Maps base inputs from `personal_info`.
   * Injects any section-specific `extra_inputs` (answers collected from the user during previous iteration rounds).
4. **Crew Execution (`kickoff_crew`):**
   * The runner calls its specific crew kickoff function (e.g., `kickoff_bureaucracy_crew`), which delegates to `kickoff_crew(crew_name, inputs)` in `content_crew.py`.
   * `kickoff_crew` validates that `crew_name` exists in `CREW_FILES`, loads the crew using `load_crew(crew_path, agents_dir=crew_path.parent)`, and executes `crew.kickoff(inputs={**default_inputs, **inputs})`.
5. **Outcome Return:** The runner returns the crew's outcome back to `write_and_compile_guide` for question extraction (`extract_questions`) or saving to `state.sections_content`.

### 6.3 Structured output model

`models.py` defines `CostEstimate`, with `average_monthly`, `low` and `high` (values in euros, as plain numbers) and `sources` (a list of URLs). In the files analysed this model is neither imported nor used. From context (comments about the finances crew returning structured output) it is probably meant for the `finances` crew, but this should be confirmed in the `.jsonc` files.

### 6.4 Input validation: `pedir_input`

The function in `Flow_functions.py` repeats the question until the value is valid. It normalises the text (strips leading and trailing whitespace and collapses repeated spaces) and rejects:

- empty values;
- values shorter than 2 characters (`min_len`) or longer than 100 (`max_len`), both configurable;
- values with characters outside the allowed pattern: letters (including accented ones), digits, space, `.`, `,`, `'`, `(`, `)` and `-`.

The error messages are in Portuguese, and a note in the file (`TRANSLATE DO ENGLISH`) reminds the team that they need to be translated into English.

### 7. How to Add a New Section or Crew (Feature)

Follow these 6 steps to add and integrate a new feature into the flow:

#### Step 1: Create Crew and Agent Files

Create the crew configuration file (`.jsonc`) and its corresponding agent files inside the appropriate directory in `agents/`:

Plaintext

```
agents/<section_name>/
├── crew_<section_name>.jsonc
└── agents_<section_name>.jsonc
```

_(Note: Agent files must reside in the same directory as the crew file)._

#### Step 2: Register in `content_crew.py`

Add the path of the `.jsonc` file to the `CREW_FILES` dictionary:

Python

```
CREW_FILES = {
    "bureaucracy": AGENTS_DIR / "bureaucracy/Report_crew/crew_bureaucracy.jsonc",
    "<section_name>": AGENTS_DIR / "<section_name>/crew_<section_name>.jsonc",
}
```

Create the helper function at the bottom of `content_crew.py`:

Python

```
def kickoff_<section_name>_crew(inputs: dict):
    return kickoff_crew("<section_name>", inputs)
```

#### Step 3: Implement the Runner in `Flow_functions.py`

Create an asynchronous runner function (`run_<section_name>`) configured to receive the three flow parameters: `personal_info`, `crews_config`, and `extra_inputs`.

Python

```
async def run_<section_name>(personal_info: dict, crews_config: dict, extra_inputs: dict = None):
    config = crews_config.get("<section_name>", {})
    required_fields = config.get("required_fields", [])
    
    # Map base inputs from personal_info
    inputs = {k: personal_info.get(k) for k in required_fields if k in personal_info}
    
    # Inject answers collected from previous clarification rounds
    if extra_inputs:
        inputs.update(extra_inputs)
        
    return kickoff_<section_name>_crew(inputs=inputs)
```

#### Step 4: Register the Runner in `main.py`

Import the runner and add the corresponding entry to the global `SECTION_RUNNERS` dictionary:

Python

```
from Flow_functions import run_bureaucracy, run_finances, run_<section_name>

SECTION_RUNNERS = {
    "bureaucracy": run_bureaucracy,
    "finances": run_finances,
    "<section_name>": run_<section_name>,
}
```

#### Step 5: Update `crews_config.json`

Specify the required input fields demanded by the new section:

JSON

```
{
  "bureaucracy": {
    "required_fields": ["origin_country", "destination_country", "origin_university", "destination_university", "semester"]
  },
  "<section_name>": {
    "required_fields": ["field_1", "field_2"]
  }
}
```

#### Step 6: Update State and Prompts in `main.py`

- Ensure all variables declared in `required_fields` are requested from the user during the `@start() def get_user_input(self)` step and saved into `self.state.personal_info`.
    
- Add the section identifier to the list of active sections in the `GuideCreatorState` class:
    

Python

```
class GuideCreatorState(BaseModel):
    personal_info: Dict[str, str] = {}
    sections: List[str] = ["bureaucracy", "<section_name>"]
    sections_content: Dict[str, str] = {}
```

## 8. Points of attention and identified improvements

**Issues that can cause runtime errors**

- **`finances` section without inputs:** it requires `city` and `country`, but `get_user_input` does not collect those fields. If the section is enabled, the crew receives `None` for those values (`personal_info.get(campo)`).
- **Section with no entry in `crews_config.json`:** `CREWS_CONFIG.get(section.lower())` returns `None` and the next line (`.get("required_fields")`) fails with an `AttributeError`. The same happens if the section is not in `CREWS` (calling `None(...)`).
- **Missing `output/` folder:** writing the file fails. Suggestion: `os.makedirs("output", exist_ok=True)`.
- **Writing without an encoding:** `open("output/complete_guide.md", "w")` does not set `encoding="utf-8"`, unlike the JSON read. On Windows, accented characters can cause an error.
- **Relative paths:** `crews_config.json` and `output/` depend on the directory the program is run from.

**Incomplete functionality**

- **`feedback_loop`:** it only collects the chosen section. It still needs to ask for the user's complaint, call the `bureaucracy_repair` crew (which is already registered in `CREW_FILES` but not in `CREWS`) and rewrite the guide. The idea noted in the code is to use two new agents: one that receives the complaint and writes a good correction request, and another (`correction_agent`) that applies the correction, instead of overloading the original search agent, especially with free models that have a limited context.
- **Sections yet to be implemented:** `Finance`, `Housing` and `Commute`. The notes indicate that finances returns structured output (entertainment and groceries) and that it would be useful for Housing and Commute to do the same, so the final layout can be controlled.
- **Section titles:** there is a note about making sure every crew response comes with a title, which currently depends on the crew's prompt.
