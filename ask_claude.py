import os
import sys
import boto3
from botocore.config import Config
from dotenv import load_dotenv
from langchain_aws import ChatBedrockConverse
from langchain_core.messages import HumanMessage

load_dotenv()

def ask_claude(prompt):
    model_id = os.getenv("BEDROCK_MODEL_ID", "us.anthropic.claude-opus-4-5-20251101-v1:0")
    region = os.getenv("AWS_DEFAULT_REGION", "us-east-1")
    
    # Configure an explicit client with a high timeout because UI generation takes time
    config = Config(read_timeout=600, retries={'max_attempts': 1})
    client = boto3.client("bedrock-runtime", region_name=region, config=config)
    
    llm = ChatBedrockConverse(
        client=client,
        model=model_id,
        temperature=0.7,
    )
    
    print(f"Sending prompt to {model_id} via Bedrock...", file=sys.stderr)
    response = llm.invoke([HumanMessage(content=prompt)])
    return response.content

if __name__ == "__main__":
    prompt = sys.argv[1] if len(sys.argv) > 1 else sys.stdin.read()
    if not prompt.strip():
        print("Please provide a prompt.", file=sys.stderr)
        sys.exit(1)
    
    print(ask_claude(prompt))
