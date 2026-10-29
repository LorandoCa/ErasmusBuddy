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

```
@start  get_user_input
   |   asks for inputs, validates them, fills state.personal_info
   v
@listen write_and_compile_guide
   |   for each section in state.sections:
   |     reads crews_config.json -> required_fields
   |     builds inputs from personal_info
   |     CREWS[section](inputs) -> result.raw -> state.sections_content
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

1. Reads `crews_config.json`.
2. For each section in `state.sections` (sequentially, not in parallel):
   - gets the section's configuration with `CREWS_CONFIG.get(section.lower())`;
   - builds the `inputs` dictionary with only the fields listed in `required_fields`, reading them from `personal_info`;
   - calls the crew's function through the global `CREWS` dictionary (`CREWS.get(section.lower())(inputs=inputs)`);
   - stores `result.raw` in `state.sections_content[section]`.
3. Compiles the guide: the title `# Your Personalized Erasmus Guide` followed by the content of each section, in the order of `state.sections`.
4. Saves it to `output/complete_guide.md` and returns the state.

### 5.3 `feedback_loop` (`@listen(write_and_compile_guide)`)

Asks `Y/N` whether any section fell short of expectations. If the answer is `Y`, it lists the sections present in `sections_content` and asks the user to pick one, by number or by name (case-insensitive), repeating until the choice is valid.

After that the method ends with a bare `return` and does nothing else: it does not ask for a description of the problem, does not call any correction crew and does not update the guide. It is yet to be implemented.

### 5.4 Entry points

- `kickoff()` creates the flow, runs `GuideCreatorFlow().kickoff()` and prints closing messages.
- `plot()` generates the flow visualisation with `flow.plot("guide_creator_flow")`, which the printed message says is an HTML file.
- Running `python main.py` runs `kickoff()`.

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

### 6.2 How a crew is run

`kickoff_crew(crew_name, inputs)` in `content_crew.py`:

1. Checks that `crew_name` exists in `CREW_FILES`; otherwise it raises a `ValueError` listing the available options.
2. Loads the crew with `load_crew(crew_path, agents_dir=crew_path.parent)`, meaning the agent files must be in the same folder as the crew's `.jsonc`. The function returns the crew and some `default_inputs`.
3. Runs `crew.kickoff(inputs={**default_inputs, **inputs})`. The inputs passed by the flow take precedence over the default values.

Each crew has a convenience function (`kickoff_bureaucracy_crew`, `kickoff_bureaucracy_crew_repair`, `kickoff_finances_crew`) that simply calls `kickoff_crew` with the right name.

### 6.3 Structured output model

`models.py` defines `CostEstimate`, with `average_monthly`, `low` and `high` (values in euros, as plain numbers) and `sources` (a list of URLs). In the files analysed this model is neither imported nor used. From context (comments about the finances crew returning structured output) it is probably meant for the `finances` crew, but this should be confirmed in the `.jsonc` files.

### 6.4 Input validation: `pedir_input`

The function in `Flow_functions.py` repeats the question until the value is valid. It normalises the text (strips leading and trailing whitespace and collapses repeated spaces) and rejects:

- empty values;
- values shorter than 2 characters (`min_len`) or longer than 100 (`max_len`), both configurable;
- values with characters outside the allowed pattern: letters (including accented ones), digits, space, `.`, `,`, `'`, `(`, `)` and `-`.

The error messages are in Portuguese, and a note in the file (`TRANSLATE DO ENGLISH`) reminds the team that they need to be translated into English.

## 8. How to add a new section or crew

1. Create the crew's `.jsonc` (and its agents) under `agents/<section>/`.
2. Register the file in `CREW_FILES` and create the `kickoff_<section>_crew` function in `content_crew.py`.
3. Import that function in `main.py` and add it to the `CREWS` dictionary.
4. Add the entry to `crews_config.json` with its `required_fields`.
5. Make sure every `required_field` is collected in `get_user_input`, and add the section to `state.sections`.

## 9. Points of attention and identified improvements

**Issues that can cause runtime errors**

- **`finances` section without inputs:** it requires `city` and `country`, but `get_user_input` does not collect those fields. If the section is enabled, the crew receives `None` for those values (`personal_info.get(campo)`).
- **Section with no entry in `crews_config.json`:** `CREWS_CONFIG.get(section.lower())` returns `None` and the next line (`.get("required_fields")`) fails with an `AttributeError`. The same happens if the section is not in `CREWS` (calling `None(...)`).
- **Missing `output/` folder:** writing the file fails. Suggestion: `os.makedirs("output", exist_ok=True)`.
- **Writing without an encoding:** `open("output/complete_guide.md", "w")` does not set `encoding="utf-8"`, unlike the JSON read. On Windows, accented characters can cause an error.
- **Relative paths:** `crews_config.json` and `output/` depend on the directory the program is run from.

**Incomplete functionality**

- **`feedback_loop`:** it only collects the chosen section. It still needs to ask for the user's complaint, call the `bureaucracy_repair` crew (which is already registered in `CREW_FILES` but not in `CREWS`) and rewrite the guide. The idea noted in the code is to use two new agents: one that receives the complaint and writes a good correction request, and another (`correction_agent`) that applies the correction, instead of overloading the original search agent, especially with free models that have a limited context.
- **Sections yet to be implemented:** `Finance`, `Housing` and `Commute`. The notes indicate that finances returns structured output (entertainment and groceries) and that it would be useful for Housing and Commute to do the same, so the final layout can be controlled.
- **Parallel execution:** the code has a note about running the sections in parallel, but the current loop is sequential.
- **Section titles:** there is a note about making sure every crew response comes with a title, which currently depends on the crew's prompt.
