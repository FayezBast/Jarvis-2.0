import os
import json
from datetime import datetime

from google.genai import types

HISTORY_DIR = ".agent_history"
MAX_HISTORY_FILES = 50

schema_save_conversation = types.FunctionDeclaration(
    name="save_conversation",
    description="Saves the current conversation with a name for later reference",
    parameters=types.Schema(
        type=types.Type.OBJECT,
        properties={
            "name": types.Schema(
                type=types.Type.STRING,
                description="A short name/title for this conversation",
            ),
            "summary": types.Schema(
                type=types.Type.STRING,
                description="A brief summary of what was accomplished",
            ),
        },
        required=["name"],
    ),
)

schema_list_conversations = types.FunctionDeclaration(
    name="list_conversations",
    description="Lists all saved conversations",
    parameters=types.Schema(
        type=types.Type.OBJECT,
        properties={},
    ),
)

schema_load_conversation = types.FunctionDeclaration(
    name="load_conversation",
    description="Loads a previously saved conversation by its ID",
    parameters=types.Schema(
        type=types.Type.OBJECT,
        properties={
            "conversation_id": types.Schema(
                type=types.Type.STRING,
                description="The ID of the conversation to load",
            ),
        },
        required=["conversation_id"],
    ),
)


def _get_history_dir(working_directory):
    history_dir = os.path.join(os.path.abspath(working_directory), HISTORY_DIR)
    os.makedirs(history_dir, exist_ok=True)
    return history_dir


def save_conversation(working_directory, name, summary=None, messages=None):
    """
    Note: This function needs messages passed from the main loop.
    For now, it creates a placeholder that can be enhanced.
    """
    try:
        history_dir = _get_history_dir(working_directory)
        
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        conversation_id = f"{timestamp}_{name.lower().replace(' ', '_')[:30]}"
        
        conversation_data = {
            "id": conversation_id,
            "name": name,
            "summary": summary or "No summary provided",
            "created_at": datetime.now().isoformat(),
            "messages": messages or [],
        }
        
        filepath = os.path.join(history_dir, f"{conversation_id}.json")
        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(conversation_data, f, indent=2, default=str)
        
        return f'Conversation saved as "{name}" (ID: {conversation_id})'
    except Exception as e:
        return f"Error saving conversation: {e}"


def list_conversations(working_directory):
    try:
        history_dir = _get_history_dir(working_directory)
        
        conversations = []
        for filename in os.listdir(history_dir):
            if filename.endswith(".json"):
                filepath = os.path.join(history_dir, filename)
                try:
                    with open(filepath, "r", encoding="utf-8") as f:
                        data = json.load(f)
                        conversations.append({
                            "id": data.get("id", filename[:-5]),
                            "name": data.get("name", "Unnamed"),
                            "summary": data.get("summary", ""),
                            "created_at": data.get("created_at", "Unknown"),
                        })
                except (json.JSONDecodeError, IOError):
                    continue
        
        if not conversations:
            return "No saved conversations found"
        
        # Sort by creation date (newest first)
        conversations.sort(key=lambda x: x["created_at"], reverse=True)
        
        result = f"Found {len(conversations)} saved conversations:\n\n"
        for conv in conversations[:20]:  # Show max 20
            result += f"- [{conv['id']}] {conv['name']}\n"
            result += f"  Created: {conv['created_at']}\n"
            if conv['summary']:
                result += f"  Summary: {conv['summary'][:100]}...\n" if len(conv['summary']) > 100 else f"  Summary: {conv['summary']}\n"
            result += "\n"
        
        return result
    except Exception as e:
        return f"Error listing conversations: {e}"


def load_conversation(working_directory, conversation_id):
    try:
        history_dir = _get_history_dir(working_directory)
        filepath = os.path.join(history_dir, f"{conversation_id}.json")
        
        if not os.path.exists(filepath):
            return f'Conversation "{conversation_id}" not found'
        
        with open(filepath, "r", encoding="utf-8") as f:
            data = json.load(f)
        
        result = f"Conversation: {data.get('name', 'Unnamed')}\n"
        result += f"Created: {data.get('created_at', 'Unknown')}\n"
        result += f"Summary: {data.get('summary', 'No summary')}\n\n"
        
        messages = data.get("messages", [])
        if messages:
            result += f"Messages ({len(messages)}):\n"
            for i, msg in enumerate(messages[-10:], 1):  # Show last 10 messages
                role = msg.get("role", "unknown")
                content = str(msg.get("content", ""))[:200]
                result += f"{i}. [{role}]: {content}...\n" if len(content) >= 200 else f"{i}. [{role}]: {content}\n"
        
        return result
    except Exception as e:
        return f"Error loading conversation: {e}"
