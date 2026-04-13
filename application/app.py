import streamlit as st 
import utils
import chat
import json
import mcp_config 
import logging
import sys
import os
import asyncio
import langgraph_agent
import skill

logging.basicConfig(
    level=logging.INFO,  # Default to INFO level
    format='%(filename)s:%(lineno)d | %(message)s',
    handlers=[
        logging.StreamHandler(sys.stderr)
    ]
)
logger = logging.getLogger("streamlit")

WORKING_DIR = os.path.dirname(os.path.abspath(__file__))
SKILLS_DIR = os.path.join(WORKING_DIR, "skills")
ARTIFACTS_DIR = os.path.join(WORKING_DIR, "artifacts")

config = utils.load_config()
sharing_url = config.get("sharing_url")

os.environ["DEV"] = "true"  # Skip user confirmation of get_user_input

# title
st.set_page_config(page_title='agent-wiki', page_icon=None, layout="centered", initial_sidebar_state="auto", menu_items=None)

mode_descriptions = {
    "일상적인 대화": [
        "대화이력을 바탕으로 챗봇과 일상의 대화를 편안히 즐길수 있습니다."
    ],
    "Agent": [
        "SKILL과 MCP를 활용한 Agent를 이용합니다. 왼쪽 메뉴에서 필요한 MCP를 선택하세요."
    ],
    "Agent (Chat)": [
        "SKILL과 MCP를 활용한 Agent를 이용합니다. 채팅 히스토리를 이용해 interative한 대화를 즐길 수 있습니다."
    ],
    "QA Agent": [
        "RAG를 이용해 얻은 정보로 Test Case를 생성합니다."
    ],
    "이미지 분석": [
        "이미지를 선택하여 멀티모달을 이용하여 분석합니다."
    ]
}

agentType = 'langgraph'
with st.sidebar:
    st.title("🔮 Menu")
    
    st.markdown(
        "Amazon Bedrock을 이용해 다양한 형태의 대화를 구현합니다." 
        "여기에서는 SKILL과 MCP를 이용해 agent의 기능을 확장합니다." 
        "주요 코드는 LangGraph를 이용해 구현되었습니다.\n"
        "상세한 코드는 [Github](https://github.com/kyopark2014/agent-wiki)을 참조하세요."
    )

    st.subheader("🐱 대화 형태")
    
    # radio selection
    mode = st.radio(
        label="원하는 대화 형태를 선택하세요. ",options=["일상적인 대화", "Agent", "Agent (Chat)", "이미지 분석"], index=2
    )   
    st.info(mode_descriptions[mode][0])
    
    # mcp selection    
    mcp_options = [
        "aws documentation", 
        "drawio",
        "aws-drawio",
        "web_fetch",
        "obsidian",
        "browser-use",
        "korea_weather",
        "사용자 설정"
    ]    
    if mode=='Agent' or mode=='Agent (Chat)':
        # Skill Config JSON input
        st.subheader("⚙️ Skill Config")

        skill_selections = {}
        default_skill_selections = config.get("default_skills") or ["graphify"]
        logger.info(f"default_skill_selections: {default_skill_selections}")
        with st.expander("Skill 옵션 선택", expanded=True):
            available_skill_info = skill.available_skill_info("base")
            for s in available_skill_info:
                default_value = s["name"] in default_skill_selections
                skill_selections[s["name"]] = st.checkbox(s["name"], key=f"skill_{s['name']}", value=default_value, help=s["description"], disabled=False)
    
        selected_skills = [name for name, is_selected in skill_selections.items() if is_selected]
        logger.info(f"selected_skills: {selected_skills}")

        if selected_skills != config.get("default_skills"):
            config["default_skills"] = selected_skills
            with open(utils.config_path, "w", encoding="utf-8") as f:
                json.dump(config, f, ensure_ascii=False, indent=4)

        # MCP Config JSON input
        st.subheader("⚙️ MCP Config")

        # Change radio to checkbox        
        mcp_selections = {}
        default_selections = ["web_fetch"]
        
        with st.expander("MCP 옵션 선택", expanded=True):
            for option in mcp_options:
                default_value = option in default_selections
                mcp_selections[option] = st.checkbox(option, key=f"mcp_{option}", value=default_value)
                
        if mcp_selections["사용자 설정"]:
            mcp = {}
            try:
                with open("user_defined_mcp.json", "r", encoding="utf-8") as f:
                    mcp = json.load(f)
                    logger.info(f"loaded user defined mcp: {mcp}")
            except FileNotFoundError:
                logger.info("user_defined_mcp.json not found")
                pass
            
            mcp_json_str = json.dumps(mcp, ensure_ascii=False, indent=2) if mcp else ""
            
            mcp_info = st.text_area(
                "MCP 설정을 JSON 형식으로 입력하세요",
                value=mcp_json_str,
                height=150
            )
            logger.info(f"mcp_info: {mcp_info}")

            if mcp_info:
                try:
                    mcp_config.mcp_user_config = json.loads(mcp_info)
                    logger.info(f"mcp_user_config: {mcp_config.mcp_user_config}")                    
                    st.success("JSON 설정이 성공적으로 로드되었습니다.")                    
                except json.JSONDecodeError as e:
                    st.error(f"JSON 파싱 오류: {str(e)}")
                    st.error("올바른 JSON 형식으로 입력해주세요.")
                    logger.error(f"JSON 파싱 오류: {str(e)}")
                    mcp_config.mcp_user_config = {}
            else:
                mcp_config.mcp_user_config = {}
                
            with open("user_defined_mcp.json", "w", encoding="utf-8") as f:
                json.dump(mcp_config.mcp_user_config, f, ensure_ascii=False, indent=4)
            logger.info("save to user_defined_mcp.json")
        
        mcp_servers = [server for server, is_selected in mcp_selections.items() if is_selected]

    else:
        mcp_servers = []

    # model selection box
    modelName = st.selectbox(
        '🖊️ 사용 모델을 선택하세요',
        (
            "Claude 4.6 Sonnet",
            "Claude 4.6 Opus",
            "Claude 4.5 Haiku",
            "Claude 4.5 Sonnet",
            "Claude 4.5 Opus",  
            "Claude 4 Opus", 
            "Claude 4 Sonnet", 
            "Claude 3.7 Sonnet", 
            "Claude 3.5 Sonnet", 
            "Claude 3.0 Sonnet", 
            "Claude 3.5 Haiku", 
            "OpenAI OSS 120B",
            "OpenAI OSS 20B",
            "Nova 2 Lite",
            "Nova Premier", 
            "Nova Pro", 
            "Nova Lite", 
            "Nova Micro",       
        ), index=0
    )

    # skill checkbox
    select_skillMode = st.checkbox('Skill Mode', value=True)
    skillMode = 'Enable' if select_skillMode else 'Disable'    

    # debug checkbox
    select_debugMode = st.checkbox('Debug Mode', value=True)
    debugMode = 'Enable' if select_debugMode else 'Disable'
    #print('debugMode: ', debugMode)

    # extended thinking of claude 3.7 sonnet
    reasoningMode = "Disable"
    if mode == "일상적인 대화":
        select_reasoning = st.checkbox('Reasoning', value=False)
        reasoningMode = 'Enable' if select_reasoning else 'Disable'
        # logger.info(f"reasoningMode: {reasoningMode}")

    uploaded_file = None
    if mode=='이미지 분석':
        st.subheader("🌇 이미지 업로드")
        uploaded_file = st.file_uploader("이미지 분석을 위한 파일을 선택합니다.", type=["png", "jpg", "jpeg"])

    chat.update(modelName, debugMode, reasoningMode, skillMode)    

    st.success(f"Connected to {modelName}", icon="💚")
    clear_button = st.button("대화 초기화", key="clear")
    # logger.info(f"clear_button: {clear_button}")

st.title('🔮 '+ mode)

if clear_button==True:    
    chat.map_chain = dict() 
    chat.checkpointers = dict() 
    chat.memorystores = dict() 
    chat.initiate()

# Preview the uploaded image in the sidebar
file_name = ""
file_bytes = None
state_of_code_interpreter = False
if uploaded_file is not None and clear_button==False:
    logger.info(f"uploaded_file.name: {uploaded_file.name}")
    if uploaded_file.name:
        logger.info(f"csv type? {uploaded_file.name.lower().endswith(('.csv'))}")

    if uploaded_file and uploaded_file.name and not mode == '이미지 분석':
        chat.initiate()

        if debugMode=='Enable':
            status = '선택한 파일을 업로드합니다.'
            logger.info(f"status: {status}")
            st.info(status)

        file_name = uploaded_file.name
        logger.info(f"uploading... file_name: {file_name}")
        file_url = chat.upload_to_s3(uploaded_file.getvalue(), file_name)
        logger.info(f"file_url: {file_url}")

        import utils
        utils.sync_data_source()  # sync uploaded files
            
        status = f'선택한 "{file_name}"의 내용을 요약합니다.'
        if debugMode=='Enable':
            logger.info(f"status: {status}")
            st.info(status)
    
        msg = chat.get_summary_of_uploaded_file(file_name, st)
        st.session_state.messages.append({"role": "assistant", "content": f"선택한 문서({file_name})를 요약하면 아래와 같습니다.\n\n{msg}"})    
        logger.info(f"msg: {msg}")

        st.write(msg)

    if uploaded_file and clear_button==False and mode == '이미지 분석':
        st.image(uploaded_file, caption="이미지 미리보기", use_container_width=True)

        file_name = uploaded_file.name
        file_bytes = uploaded_file.getvalue()

# Initialize chat history
if "messages" not in st.session_state:
    st.session_state.messages = []
    st.session_state.greetings = False

# Display chat messages from history on app rerun
def display_chat_messages() -> None:
    """Print message history
    @returns None
    """
    for message in st.session_state.messages:
        with st.chat_message(message["role"]):
            if "images" in message:                
                for url in message["images"]:
                    logger.info(f"url: {url}")

                    file_name = url[url.rfind('/')+1:]
                    st.image(url, caption=file_name, use_container_width=True)
            st.markdown(message["content"])

display_chat_messages()

def show_references(reference_docs):
    if debugMode == "Enable" and reference_docs:
        with st.expander(f"답변에서 참조한 {len(reference_docs)}개의 문서입니다."):
            for i, doc in enumerate(reference_docs):
                st.markdown(f"**{doc.metadata['name']}**: {doc.page_content}")
                st.markdown("---")

# Greet user
if not st.session_state.greetings:
    with st.chat_message("assistant"):
        intro = "아마존 베드락을 이용하여 주셔서 감사합니다. 편안한 대화를 즐기실수 있으며, 파일을 업로드하면 요약을 할 수 있습니다."
        st.markdown(intro)
        # Add assistant response to chat history
        st.session_state.messages.append({"role": "assistant", "content": intro})
        st.session_state.greetings = True

if clear_button or "messages" not in st.session_state:
    st.session_state.messages = []        
    uploaded_file = None
    
    st.session_state.greetings = False
    chat.clear_chat_history()
    st.rerun()    

# Always show the chat input
if prompt := st.chat_input("메시지를 입력하세요."):
    with st.chat_message("user"):  # display user message in chat message container
        st.markdown(prompt)

    st.session_state.messages.append({"role": "user", "content": prompt})  # add user message to chat history
    prompt = prompt.replace('"', "").replace("'", "")
    logger.info(f"prompt: {prompt}")

    with st.chat_message("assistant"):
        if mode == '일상적인 대화':
            stream = chat.general_conversation(prompt)            
            response = st.write_stream(stream)
            logger.info(f"response: {response}")
            st.session_state.messages.append({"role": "assistant", "content": response})

            chat.save_chat_history(prompt, response)

        elif mode == 'Agent' or mode == 'Agent (Chat)':            
            sessionState = ""
            if mode == 'Agent':
                history_mode = "Disable"
            else:
                history_mode = "Enable"

            with st.status("thinking...", expanded=True, state="running") as status:
                containers = {
                    "tools": st.empty(),
                    "status": st.empty(),
                    "notification": [st.empty() for _ in range(500)]
                }

                response, artifacts = asyncio.run(langgraph_agent.run_langgraph_agent(
                    query=prompt, 
                    mcp_servers=mcp_servers, 
                    history_mode=history_mode, 
                    containers=containers))

            st.session_state.messages.append({
                "role": "assistant", 
                "content": response,
                "artifacts": artifacts if artifacts else []
            })

            for url in artifacts:
                logger.info(f"url: {url}")
                file_name = url[url.rfind('/')+1:]
                st.image(url, caption=file_name, use_container_width=True)
                
        elif mode == "이미지 분석":
            if uploaded_file is None or uploaded_file == "":
                st.error("파일을 먼저 업로드하세요.")
                st.stop()

            else:
                if modelName == "Claude 3.5 Haiku":
                    st.error("Claude 3.5 Haiku은 이미지를 지원하지 않습니다. 다른 모델을 선택해주세요.")
                else:
                    with st.status("thinking...", expanded=True, state="running") as status:
                        summary = chat.summarize_image(file_bytes, prompt, st)
                        st.write(summary)

                        st.session_state.messages.append({"role": "assistant", "content": summary})

def main():
    """Entry point for the application."""
    # This function is used as an entry point when running as a package
    # The code above is already running the Streamlit app
    pass


if __name__ == "__main__":
    # This is already handled by Streamlit
    pass
