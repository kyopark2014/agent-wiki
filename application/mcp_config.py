import logging
import sys
import utils
import os
import json
import boto3

logging.basicConfig(
    level=logging.INFO,  # Default to INFO level
    format='%(filename)s:%(lineno)d | %(message)s',
    handlers=[
        logging.StreamHandler(sys.stderr)
    ]
)
logger = logging.getLogger("mcp-config")

script_dir = os.path.dirname(os.path.abspath(__file__))
config_path = os.path.join(script_dir, "config.json")

config = utils.load_config()
logger.info(f"config: {config}")

region = config["region"] if "region" in config else "us-west-2"
projectName = config["projectName"] if "projectName" in config else "mcp"
workingDir = os.path.dirname(os.path.abspath(__file__))

parent_dir = os.path.dirname(workingDir)
contents_dir = os.path.join(parent_dir, "contents")
logger.info(f"workingDir: {workingDir}")
logger.info(f"contents_dir: {contents_dir}")

mcp_user_config = {}    

def get_secret_value(secret_name):
    session = boto3.Session()
    client = session.client('secretsmanager', region_name=region)
    
    try:
        response = client.get_secret_value(SecretId=secret_name)
        return response['SecretString']
    except client.exceptions.ResourceNotFoundException:
        logger.info(f"Secret not found, creating new secret: {secret_name}")
        try:
            # Create secret value with bearer_key 
            secret_value = {
                "key": secret_name,
                "value": "need to update"
            }
            
            # Convert to JSON string
            secret_string = json.dumps(secret_value)

            client.create_secret(
                Name=secret_name,
                SecretString=secret_string,  
                Description=f"secret key and token for {secret_name}"
            )
            logger.info(f"Secret created: {secret_name}. Please update it with the actual value.")
            return None
        except Exception as create_error:
            logger.error(f"Failed to create secret: {create_error}")
            return None
    except Exception as e:
        logger.error(f"Error getting secret value: {e}")
        return None

def load_config(mcp_type):
    if mcp_type == "aws documentation":
        mcp_type = "aws_documentation"    
    
    if mcp_type == "aws_documentation":
        return {
            "mcpServers": {
                "awslabs.aws-documentation-mcp-server": {
                    "command": "uvx",
                    "args": ["awslabs.aws-documentation-mcp-server@latest"],
                    "env": {
                        "FASTMCP_LOG_LEVEL": "ERROR"
                    }
                }
            }
        }
        
    elif mcp_type == "drawio":
        return {
            "mcpServers": {
                "drawio": {
                "command": "npx",
                "args": ["@drawio/mcp"]
                }
            }
        }

    elif mcp_type == "aws-drawio":
        return {
            "mcpServers": {
                "drawio": {
                "command": "npx",
                "args": [
                    "-y",
                    "https://github.com/aws-samples/sample-drawio-mcp/releases/latest/download/drawio-mcp-server-latest.tgz",
                    "--no-cache"
                ],
                "type": "stdio"
                }
            }
        }

    elif mcp_type == "web_fetch":
        return {
            "mcpServers": {
                "web_fetch": {
                    "command": "npx",
                    "args": ["-y", "mcp-server-fetch-typescript"]
                }
            }
        }
    
    elif mcp_type == "obsidian":
        # create folder if not exists
        if not os.path.exists(os.path.expanduser("~/Documents/memo")):
            os.makedirs(os.path.expanduser("~/Documents/memo"))
            
        return {
            "mcpServers": {
                "obsidian": {
                    "command": "npx",
                    "args": ["-y", "obsidian-mcp", os.path.expanduser("~/Documents/memo")]
                }
            }
        }
    
    elif mcp_type == "사용자 설정":
        return mcp_user_config

def load_selected_config(mcp_servers: dict):
    logger.info(f"mcp_servers: {mcp_servers}")
    
    loaded_config = {}
    for server in mcp_servers:
        config = load_config(server)
        if config:
            loaded_config.update(config["mcpServers"])
    return {
        "mcpServers": loaded_config
    }
