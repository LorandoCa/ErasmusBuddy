#!/usr/bin/env python
import json
import os
from typing import List, Dict
from pydantic import BaseModel, Field
from crewai import LLM
from crewai.flow.flow import Flow, listen, start
from guide_creator_flow.crews.content_crew.content_crew import kickoff_bureaucracy_crew # ADD THE OTHERS CREW HERE


#---------------IMPORTED--------------------
from Flow_functions import pedir_input
import json
#--------------------------------------


# Define our global variables
CREWS = {
    "bureaucracy": kickoff_bureaucracy_crew
}


# Define our flow state
class GuideCreatorState(BaseModel):
    personal_info: Dict[str, str] = {}
    sections: List[str] = ["bureaucracy"] #"Finance", "Housing", "Commute" add them when you have the correspondent agents
    sections_content: Dict[str, str] = {}

"""O orchestrator vai ter que fazer uma especie de @start parecido com essa para pedir as informações iniciais"""
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
            print("O país de destino tem de ser diferente do país de origem.")

        info["origin_university"] = pedir_input("Enter your origin university: ")
        info["destination_university"] = pedir_input("Enter your destination university: ")
        info["semester"] = pedir_input("Enter your semester (e.g., Fall 2024): ")
        #Insert HERE another necessary input information for the Erasmus guide
        #-------------------------------------------------------------------------------
    
        print(f"\nCreating a guide for a student from {info['origin_country']} going to {info['destination_country']}...\n")
        return self.state


    @listen(get_user_input)
    def write_and_compile_guide(self, state):
        """Write all sections and compile the guide"""
        print("Writing guide sections and compiling...")

        completed_sections = []
        CREWS_CONFIG = {}
        with open("crews_config.json", encoding="utf-8") as f:
            CREWS_CONFIG = json.load(f)

        # Process sections one by one to maintain context flow
        for section in state.sections:
            print(f"Processing section: {section}")

            section_inputs = CREWS_CONFIG.get(section.lower())
            required_fields = section_inputs.get("required_fields", [])

            # Constrói o dicionário só com os campos que a crew precisa
            inputs = {
                campo: self.state.personal_info.get(campo)
                for campo in required_fields
            }

            # ------------------The first the crew is runeed---------------------------------
            # Run the content crew for this section
            result = CREWS.get(section.lower())(inputs=inputs) 
            # Make shore every section response comes with a title
            #---------------------------------------------------------------------------------
            

            #Consider a set of questions that could be returned by a crew ??????????????

            # Store the content
            self.state.sections_content[section] = result.raw
            completed_sections.append(section)
            print(f"Section completed: {section}")


        # Compile the final guide
        guide_content = f"# Your Personalized Erasmus Guide\n\n"

        # Add each section in order
        for section in state.sections:
            section_content = self.state.sections_content.get(section, "")
            guide_content += f"\n\n{section_content}\n\n"

        # Save the guide
        with open("output/complete_guide.md", "w") as f:
            f.write(guide_content)

        print("\nComplete guide compiled and saved to output/complete_guide.md")
        return self.state



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

# Add two more agent for crew. One that will be responsible for recieving the complain 
# and write a good correction request and redirect it to the corection_agent. 
# Not to the first search_agent because we would have to add more points in that agent goal 
# and at same time, add more placeholders in the description. Having a big context for an agent with
# a free LLM model wont work


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