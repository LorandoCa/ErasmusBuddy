#!/usr/bin/env python
import json
import asyncio
import os
from typing import List, Dict
from pydantic import BaseModel#, Field
#from crewai import LLM
from crewai.flow.flow import Flow, listen, start


#---------------IMPORTED--------------------
try:
    from guide_creator_flow.Flow_functions import (
        pedir_input,
        run_bureaucracy,
        run_finances,
        run_commute,
        run_housing,
        extract_questions,
        collect_user_answers,
        extract_content,
    )
except ImportError:
    from Flow_functions import (
        pedir_input,
        run_bureaucracy,
        run_finances,
        run_commute,
        run_housing,
        extract_questions,
        collect_user_answers,
        extract_content,
    )
import json
#--------------------------------------


# Define our global variables
SECTION_RUNNERS = {
    "bureaucracy": run_bureaucracy, # Add later the feedback crew
    "finances": run_finances,
    "commute": run_commute,
    "housing": run_housing,
}
MAX_CONCURRENT_CREWS = 2
MAX_ROUNDS = 3 


USE_PERSONA = True

TEST_PERSONA = {
    "origin_country": "Spain",
    "destination_country": "Portugal",
    "origin_university": "Universidad Complutense de Madrid",
    "origin_city": "Madrid",
    "destination_city": "coimbra",
    "destination_university": "Univerisidade de Coimbra",
    "semester": "Fall 2026",
}



# Define our flow state
class GuideCreatorState(BaseModel):
    personal_info: Dict[str, str] = {}
    student_answers: Dict[str, Dict[str, str]] = {} # section -> question -> answer
    sections: List[str] = ["bureaucracy", "commute", "housing", ]
    sections_content: Dict[str, str] = {}

class GuideCreatorFlow(Flow[GuideCreatorState]):
    """Flow for creating a personalized checklist/information guide for Erasmus Students"""

    @start()
    def get_user_input(self):
        """Get input from the user about the guide topic and audience"""
        print("\n=== Create Your Personalized Erasmus Guide ===\n")

        info = self.state.personal_info

        if USE_PERSONA:
            info.update(TEST_PERSONA)
            print("Using test persona:")
            for k, v in info.items():
                print(f"  {k}: {v}")
            return self.state

        # ------------ GETTING USER INPUTS ------------
        info["origin_country"] = pedir_input("Enter your origin country: ")

        while True:
            info["destination_country"] = pedir_input("Enter your destination country: ")
            if info["destination_country"].lower() != info["origin_country"].lower():
                break
            print("Destination country must be different from origin country.")

        info["origin_university"] = pedir_input("Enter your origin university: ")
        info["origin_city"] = pedir_input("Enter your origin city: ")
        info["destination_city"] = pedir_input("Enter your destination city: ")
        info["destination_university"] = pedir_input("Enter your destination university: ")
        info["semester"] = pedir_input("Enter your semester (e.g., Fall 2024): ")
    
        print(f"\nCreating a guide for a student from {info['origin_country']} going to {info['destination_country']}...\n")
        return self.state


    @listen(get_user_input)
    async def write_and_compile_guide(self, state):
        print("Writing guide sections and compiling...")

        config_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "crews_config.json")
        if not os.path.exists(config_path):
            config_path = "crews_config.json"

        with open(config_path, encoding="utf-8") as f:
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
            pending = [s for s in self.state.sections if s not in completed]
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

                print("Going to extract questions\n\n")
                questions = extract_questions(section, outcome) # Define an agent responsible for colecting those questions and make some sanitization
                if questions:
                    asked_questions[section] = questions
                else:
                    self.state.sections_content[section] = extract_content(
                        section, outcome, self.state.personal_info
                    )
                    completed.append(section)
                    print(f"Section completed: {section}")

            if not asked_questions:
                break

            # Sequential on purpose: prompts from different crews must not interleave
            for section, questions in asked_questions.items():
                extra_inputs.setdefault(section, {}).update(collect_user_answers(section, questions))
                # IMPORTANT: Concat the question with the answer
                # collect_user_answers tem de devolver um dict com a pergunta e a resposta, para que possamos concatenar e enviar de volta para o crew
        else:
            print(f"Reached MAX_ROUNDS ({MAX_ROUNDS}) with unfinished sections: "
                f"{[s for s in self.state.sections if s not in completed]}")

            # Make shure the result is saved even if we reach the max rounds, so we can have a partial guide


        guide_content = "# Your Personalized Erasmus Guide\n\n"
        for section in self.state.sections:
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
        """Receive users questions/complaints and apply them via repair crew"""
        try:
            from guide_creator_flow.crews.content_crew.content_crew import kickoff_bureaucracy_crew_repair
        except ImportError:
            from crews.content_crew.content_crew import kickoff_bureaucracy_crew_repair

        correction = input("Is there any section that is not on your expectations? Y/N: ").strip().upper()

        if correction == 'Y':
            sections = list(self.state.sections_content.keys())

            if not sections:
                print("No sections available to correct.")
                return self.state

            print("\nAvailable sections:")
            for i, nome in enumerate(sections, start=1):
                print(f"  {i}. {nome}")

            section = ""
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

            user_complaint = input(f"\nWhat would you like to improve or correct in section '{section}'?\n> ").strip()
            if user_complaint:
                print(f"\nApplying corrections to section '{section}'...")
                repair_inputs = {
                    "section": section,
                    "section_content": self.state.sections_content.get(section, ""),
                    "user_request": user_complaint,
                }
                repair_outcome = kickoff_bureaucracy_crew_repair(repair_inputs)
                corrected_text = getattr(repair_outcome, "raw", str(repair_outcome))
                if corrected_text:
                    self.state.sections_content[section] = corrected_text

                    # Recompilar o guia completo com a secção corrigida
                    guide_content = "# Your Personalized Erasmus Guide\n\n"
                    for s in self.state.sections:
                        guide_content += f"\n\n{self.state.sections_content.get(s, '')}\n\n"

                    with open("output/complete_guide.md", "w", encoding="utf-8") as f:
                        f.write(guide_content)
                    print(f"\nSection '{section}' successfully updated and saved in output/complete_guide.md!")

        return self.state
        

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