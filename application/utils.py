import logging
import sys
import json
import traceback
import boto3
import os

logging.basicConfig(
    level=logging.INFO,  # Default to INFO level
    format='%(filename)s:%(lineno)d | %(message)s',
    handlers=[
        logging.StreamHandler(sys.stderr)
    ]
)
logger = logging.getLogger("utils")

aws_access_key = os.environ.get('AWS_ACCESS_KEY_ID')
aws_secret_key = os.environ.get('AWS_SECRET_ACCESS_KEY')
aws_session_token = os.environ.get('AWS_SESSION_TOKEN')

workingDir = os.path.dirname(os.path.abspath(__file__))
config_path = os.path.join(workingDir, "config.json")
favorite_tools_path = os.path.join(os.path.dirname(config_path), "favorite_tools.json")
    
def load_config():
    config = None

    try: 
        with open(config_path, "r", encoding="utf-8") as f:
            config = json.load(f)
    except Exception as e:
        logger.error(f"Error loading config: {e}")
        config = {}

        projectName = "agent-wiki"
        session = boto3.Session()
        region = session.region_name
        config['region'] = region
        config['projectName'] = projectName
        
        sts = boto3.client("sts")
        response = sts.get_caller_identity()
        accountId = response["Account"]
        config['accountId'] = accountId
        
        with open(config_path, "w", encoding="utf-8") as f:
            json.dump(config, f, indent=2)    
    return config



def load_favorite_tools() -> dict[str, list[str]]:
    """Load favorite tool defaults for initial selections."""
    fallback = {"MCP": [], "SKILL": []}
    try:
        with open(favorite_tools_path, "r", encoding="utf-8") as f:
            data = json.load(f)
    except FileNotFoundError:
        logger.warning("favorite_tools.json not found: %s", favorite_tools_path)
        return fallback
    except Exception as e:
        logger.warning("Failed to load favorite_tools.json: %s", e)
        return fallback

    if not isinstance(data, dict):
        return fallback

    favorites: dict[str, list[str]] = {}
    for key in ("MCP", "SKILL"):
        values = data.get(key, [])
        if isinstance(values, list):
            favorites[key] = [v for v in values if isinstance(v, str) and v.strip()]
        else:
            favorites[key] = []
    return favorites


def save_favorite_tools(
    *, skills: list[str] | None = None, mcp_servers: list[str] | None = None
) -> dict[str, list[str]]:
    """Persist favorite tool defaults in favorite_tools.json."""
    favorites = load_favorite_tools()
    if skills is not None:
        favorites["SKILL"] = [v for v in skills if isinstance(v, str) and v.strip()]
    if mcp_servers is not None:
        favorites["MCP"] = [v for v in mcp_servers if isinstance(v, str) and v.strip()]

    with open(favorite_tools_path, "w", encoding="utf-8") as f:
        json.dump(favorites, f, ensure_ascii=False, indent=2)
    return favorites


def get_initial_tool_defaults() -> tuple[list[str], list[str]]:
    """Return initial skill/MCP defaults from favorite_tools.json."""
    favorite_tools = load_favorite_tools()
    default_skills = favorite_tools.get("SKILL") or []
    default_mcp_servers = favorite_tools.get("MCP") or []
    return default_skills, default_mcp_servers

config = load_config()

accountId = config.get('accountId')
if not accountId:
    sts = boto3.client("sts")
    response = sts.get_caller_identity()
    accountId = response["Account"]
    config['accountId'] = accountId
    with open(config_path, "w", encoding="utf-8") as f:
        json.dump(config, f, indent=2)

bedrock_region = config.get('region', 'us-west-2')
logger.info(f"bedrock_region: {bedrock_region}")
projectName = config.get('projectName', 'mop')
logger.info(f"projectName: {projectName}")

def get_contents_type(file_name):
    if file_name.lower().endswith((".jpg", ".jpeg")):
        content_type = "image/jpeg"
    elif file_name.lower().endswith((".pdf")):
        content_type = "application/pdf"
    elif file_name.lower().endswith((".txt")):
        content_type = "text/plain"
    elif file_name.lower().endswith((".csv")):
        content_type = "text/csv"
    elif file_name.lower().endswith((".ppt", ".pptx")):
        content_type = "application/vnd.ms-powerpoint"
    elif file_name.lower().endswith((".doc", ".docx")):
        content_type = "application/msword"
    elif file_name.lower().endswith((".xls")):
        content_type = "application/vnd.ms-excel"
    elif file_name.lower().endswith((".py")):
        content_type = "text/x-python"
    elif file_name.lower().endswith((".js")):
        content_type = "application/javascript"
    elif file_name.lower().endswith((".md")):
        content_type = "text/markdown"
    elif file_name.lower().endswith((".png")):
        content_type = "image/png"
    else:
        content_type = "no info"    
    return content_type

