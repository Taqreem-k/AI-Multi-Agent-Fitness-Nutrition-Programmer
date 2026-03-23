import os
import streamlit as st
from dotenv import load_dotenv
from typing import TypedDict, Annotated, List, Optional
from pydantic import BaseModel, Field

from langgraph.graph import StateGraph,START, END
from langgraph.graph.message import add_messages
from langchain_core.messages import HumanMessage
from langchain_core.prompts import ChatPromptTemplate
from langchain_google_genai import ChatGoogleGenerativeAI


st.set_page_config(page_title="AI Fitness & Nutrition Pro", layout = "centered")

# Initiating LLM
load_dotenv()
llm = ChatGoogleGenerativeAI(model="gemini-2.5-flash")


# Defining GraphState
class AgentState(TypedDict):
    messages: Annotated[List, add_messages]
    user_profile: str
    equipment_available: List[str]
    workout_routine: str
    nutrition_plan: str
    supplement_protocol: str
    final_report: str


# Definin Pydantic schema
class UserIntakeData(BaseModel):
    age: Optional[int] = Field(description="The user's age in years.")
    weight: Optional[str] = Field(description="The user's weight, including units.")
    goals: str = Field(description="The primary fitness goal.")
    experience_level: str=Field(description="Fitness experience level(e.g., Beginner, Advanced).")
    equipment_available: List[str] = Field(description="List of available workout equipment or gym type.")


# Defining PromptTemplates
input_prompt = ChatPromptTemplate.from_messages([
    ("system", "You are an expert fitness intake assessor. Extract the user's biometrics, goals, experience and equipment from their message. If a metric is missing, leave it null, but infer experience and equipment from context if possible. YOU MUST OPUTPU IN STRICT JSON FORMAT."),
    ("human", "{user_text}")
])

workout_prompt = ChatPromptTemplate.from_messages([
    ("system", "You are an elite fitness programmer. Design a multi-week workout split tailored strictly to the user's experience level. CRITICAL: You must ONLY prescribe exercises that use the available equipment ."),
    ("human", "Profile: {profile}\nAvailable Equipment: {equipment}\n\nProvide the weekly split, exercises, sets and reps.")
])

nutrition_prompt = ChatPromptTemplate.from_messages([
    ("system", "You are a sports nutritionist. Analyze the user's profile and their newly assigned workout routine. Recommend a daily calorie target, a macronutrient slip, and a specific supplement protocol(e.g., whey timing, creatine phasing)."),
    ("human", "Profile: {profile}\nWorkout Routine: {routine}\n\nProvide the nutrition plan and supplement protocol")
])

formatter_prompt = ChatPromptTemplate.from_messages([
    ("system", "You are an professional document formatter. Compile the provided fitness data into a highly readable, motivating, and clean Markdown report. Use headers, bullet points, and bold text effectively."),
    ("human", "Profile: {profile}\n\nRoutine:\n {routine}\n\nNutrition & Supplements:\n{nutrition}")
])


# Defining User Profile
def input_user_profile(state: AgentState) -> AgentState:
    messages = state.get("messages",[])
    user_input = messages[-1].content

    structured_llm = llm.with_structured_output(UserIntakeData, method = "json_mode")

    chain = input_prompt | structured_llm
    extracted_data = chain.invoke({"user_text": user_input})

    profile_string = f"Age: {extracted_data.age}. Weight: {extracted_data.weight}, Goal: {extracted_data.goals}, Experience: {extracted_data.experience_level}"

    return {
        "user_profile": profile_string,
        "equipment_available": extracted_data.equipment_available
    }


# Defining Workout Routine
def input_workout_routine(state: AgentState) -> AgentState:
    profile = state.get("user_profile")
    equipment = state.get("equipment_available")

    chain = workout_prompt | llm
    response = chain.invoke({"profile": profile, "equipment": equipment})

    return {
        "workout_routine": response.content,
    }


# Defining Nutrition Plan
def input_nutrition_plan(state: AgentState) -> AgentState:
    profile = state.get("user_profile")
    routine = state.get("workout_routine")

    chain = nutrition_prompt | llm
    response = chain.invoke({"profile": profile, "routine": routine})

    return {
        "nutrition_plan": response.content,
        "supplement_protocol": "Integrated within the nutrition plan above."
    }


# Defining Final Report
def input_final_report(state: AgentState) -> AgentState:
    profile = state.get("user_profile")
    routine = state.get("workout_routine")
    nutrition = state.get("nutrition_plan")

    chain = formatter_prompt | llm
    response = chain.invoke({"profile": profile, "routine": routine, "nutrition": nutrition})

    return {
        "final_report": response.content
    }


# Defining Workflow
workflow = StateGraph(AgentState)

workflow.add_node("intake", input_user_profile)
workflow.add_node("routine", input_workout_routine)
workflow.add_node("nutrition", input_nutrition_plan)
workflow.add_node("report", input_final_report)

workflow.set_entry_point("intake")

workflow.add_edge("intake","routine")
workflow.add_edge("routine","nutrition")
workflow.add_edge("nutrition","report")
workflow.add_edge("report", END)


# Compiling application
app = workflow.compile()

st.title("AI Multi-Agent Fitness Programmer")
st.write("Tell me your age, weight, goals, experience level, and available gym equipment:\n")

with st.form("user_input_form"):
    user_text= st.text_area(
        "Enter your details: ",
        placeholder = "E.g., I am 21 years old, currently at 75kg, and my main goal is to build lean muscle. I've been consistently working out for over two years now and I already use creatine, I have access to a fully equipped commercial gym.",
        height=150
    )
    submit_button = st.form_submit_button("Generate Plan")


# Defining Execution Logic
if submit_button and user_text:
    with st.status("Initializing AI Agents...", expanded=True) as status:

        initial_state = {
            "messages": [HumanMessage(content=user_text)],
            "user_profile": "",
            "workout_routine": "",
            "nutrition_plan": "",
            "final_report": ""
        }

        for output in app.stream(initial_state):
            for key, value in output.items():
                if key == "intake":
                    st.write("Intake Assessor: Profile analyzed and structured.")
                elif key == "routine":
                    st.write("Routine Architect: Workout split generated.")
                elif key == "nutrition":
                    st.write("Nutritionist: Diet and supplement protocols calculated.")
                elif key == "report":
                    st.write("Formatter: Compiling final markdown document.")
                    final_markdown = value["final_report"]

        status.update(label="Plan Complete!", state ="complete", expanded = False)
        st.success("Your personalized program is ready!")
        st.markdown(final_markdown)


