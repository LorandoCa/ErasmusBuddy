#!/usr/bin/env python
import json
import asyncio
import os
from typing import List, Dict
from pydantic import BaseModel#, Field
#from crewai import LLM
from crewai.flow.flow import Flow, listen, start


#---------------IMPORTED--------------------
from Flow_functions import pedir_input, run_bureaucracy, run_finances # should be later defined as a tool
import json
#--------------------------------------


# Define our global variables
SECTION_RUNNERS = {
    "bureaucracy": run_bureaucracy, # Add later the feedback crew
    "finances": run_finances
}
MAX_CONCURRENT_CREWS = 2
MAX_ROUNDS = 3 


# Define our flow state
class GuideCreatorState(BaseModel):
    personal_info: Dict[str, str] = {}
    sections: List[str] = ["bureaucracy"] #"Finance", "Housing", "Commute" add them when you have the correspondent agents
    sections_content: Dict[str, str] = {}

class GuideCreatorFlow(Flow[GuideCreatorState]):
    """Flow for creating a personalized checklist/information guide for Erasmus Students"""

    @start()
    def get_user_input(self):
        """Get input from the user about the guide topic and audience"""
        print("\n=== Create Your Personalized Erasmus Guide ===\n")

        #------------GETTING USER INPUTS----------------------------------------------

        info = self.state.personal_info

        info["origin_country"] = pedir_input("Enter your origin country: ")

        while True:
            info["destination_country"] = pedir_input("Enter your destination country: ")
            if info["destination_country"].lower() != info["origin_country"].lower():
                break
            print("Destination country must be different from origin country.")

        info["origin_university"] = pedir_input("Enter your origin university: ")
        info["destination_university"] = pedir_input("Enter your destination university: ")
        info["semester"] = pedir_input("Enter your semester (e.g., Fall 2024): ")
        #Insert HERE another necessary input information for the Erasmus guide
        #-------------------------------------------------------------------------------
    
        print(f"\nCreating a guide for a student from {info['origin_country']} going to {info['destination_country']}...\n")
        return self.state


    @listen(get_user_input)
    async def write_and_compile_guide(self, state):
        print("Writing guide sections and compiling...")

        with open("crews_config.json", encoding="utf-8") as f:
            crews_config = json.load(f)

        semaphore = asyncio.Semaphore(MAX_CONCURRENT_CREWS)
        completed: list[str] = []          # sections with a concrete (non-question) answer
        extra_inputs: dict[str, dict] = {} # per-section answers collected from the user

        async def run_section(section: str):
            runner = SECTION_RUNNERS.get(section.lower())
            if runner is None:
                raise ValueError(f"No runner registered for section {section!r}")
            async with semaphore:
                print(f"Processing section: {section}")
                return await runner(
                    self.state.personal_info, crews_config, extra_inputs.get(section) # This extra_inputs, injects in the the crew a set of answers from that previous reasonning
                )

        for round_number in range(1, MAX_ROUNDS + 1):
            pending = [s for s in state.sections if s not in completed]
            if not pending:
                break

            print(f"\n--- Round {round_number}: {pending} ---")
            results = await asyncio.gather(
                *(run_section(s) for s in pending),
                return_exceptions=True,
            )

            asked_questions = {}  # section -> list of questions, for this round only

            for section, outcome in zip(pending, results):
                if isinstance(outcome, Exception):
                    print(f"Section failed: {section} -> {outcome}")
                    completed.append(section)  # do not retry a crash forever
                    continue

                questions = extract_questions(section, outcome) # Define an agent responsible for colecting those questions
                if questions:
                    asked_questions[section] = questions
                else:
                    self.state.sections_content[section] = outcome.raw
                    completed.append(section)
                    print(f"Section completed: {section}")

            if not asked_questions:
                break

            # Sequential on purpose: prompts from different crews must not interleave
            for section, questions in asked_questions.items():
                extra_inputs[section] = collect_user_answers(section, questions) # Define a function that will be responsible for collecting answers
                # IMPORTANT: Concat the question with the answer
        else:
            print(f"Reached MAX_ROUNDS ({MAX_ROUNDS}) with unfinished sections: "
                f"{[s for s in state.sections if s not in completed]}")




        guide_content = "# Your Personalized Erasmus Guide\n\n"
        for section in state.sections:
            guide_content += f"\n\n{self.state.sections_content.get(section, '')}\n\n"

        os.makedirs("output", exist_ok=True)
        with open("output/complete_guide.md", "w", encoding="utf-8") as f:
            f.write(guide_content)

        print("\nComplete guide compiled and saved to output/complete_guide.md")
        return self.state

# For finances, housing, commute case, we will need a different approach
# The crew for finances returns a structured output for entertainment and groceries. Use the housing e commute value to complete the section
# It would be good if commute e housing came structured too, so it can be easier to have our disired layout


    @listen(write_and_compile_guide)
    def feedback_loop(self, state):
        """Recieve users questions/complains and apply them"""

        correction = input("Is there any section that is not on your expectations? Y/N: ").strip().upper()

        section = ""
        if correction == 'Y':
            sections = list(self.state.sections_content.keys())

            print("\nAvailable sections:")
            for i, nome in enumerate(sections, start=1):
                print(f"  {i}. {nome}")

            while True:
                escolha = input("\nWhich section do you want to correct? (number or name): ").strip()

                # Escolha por número
                if escolha.isdigit() and 1 <= int(escolha) <= len(sections):
                    section = sections[int(escolha) - 1]
                    break

                # Escolha por nome (ignora maiúsculas/minúsculas)
                correspondencia = next((s for s in sections if s.lower() == escolha.lower()), None)
                if correspondencia:
                    section = correspondencia
                    break

                print("Invalid choice. Please type a number from the list or the section name.")


        return
        

def kickoff():
    """Run the guide creator flow"""
    GuideCreatorFlow().kickoff()
    print("\n=== Flow Complete ===")
    print("Your comprehensive guide is ready in the output directory.")
    print("Open output/complete_guide.md to view it.")

def plot():
    """Generate a visualization of the flow"""
    flow = GuideCreatorFlow()
    flow.plot("guide_creator_flow")
    print("Flow visualization saved to guide_creator_flow.html")

if __name__ == "__main__":
    kickoff()