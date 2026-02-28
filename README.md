# 🤖 Jarvis-2.0

**A Local-First AI Assistant That Acts, Not Just Chats**

Jarvis-2.0 is an open-source, local-first AI agent that can automate tasks, manage files, execute code, and interact with your development environment. Unlike traditional chatbots, Jarvis is designed to **take action** on your behalf.

## ✨ Key Features

- 🏠 **Local-First**: Runs on your own hardware. Your data stays local.
- 🔧 **Agent, Not Chatbot**: Uses tools to actually do things, not just talk about them
- 🔌 **Pluggable AI Backend**: Works with Gemini (more coming soon)
- 🛡️ **Safe by Design**: Sandboxed file operations, blocked dangerous commands
- 📦 **Extensible Tool System**: Easy to add new capabilities

## 🚀 Quick Start

### 1. Clone the Repository

```bash
git clone https://github.com/FayezBast/Jarvis-2.0.git
cd Jarvis-2.0
```

### 2. Create Virtual Environment

```bash
python -m venv .venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate
```

### 3. Install Dependencies

```bash
pip install google-genai python-dotenv
```

### 4. Configure API Key

```bash
cp .env.example .env
# Edit .env and add your GEMINI_API_KEY
```

Get your API key from: https://aistudio.google.com/app/apikey

### 5. Run Jarvis

```bash
# Interactive mode
python main.py --interactive

# Single command
python main.py "List all Python files in this directory"
```

## 🎯 How It Works

Jarvis operates in an **agent loop**:

```
THINK → DECIDE → ACT → OBSERVE → RESPOND
```

1. **THINK**: Jarvis analyzes your request
2. **DECIDE**: Chooses to respond directly or use a tool
3. **ACT**: Executes the chosen tool
4. **OBSERVE**: Processes the result
5. **RESPOND**: Provides the final answer

## 🛠️ Available Tools

### File Operations
| Tool | Description |
|------|-------------|
| `get_files_info` | List directory contents |
| `get_file_content` | Read file contents |
| `write_file` | Create or modify files |
| `delete_file` | Remove files |
| `search_files` | Search for patterns (like grep) |

### Shell & Execution
| Tool | Description |
|------|-------------|
| `shell_command` | Execute shell commands (safely) |
| `run_python_file` | Run Python scripts |

### Git Operations
| Tool | Description |
|------|-------------|
| `git_status` | Show repository status |
| `git_diff` | Show file changes |
| `git_log` | View commit history |
| `git_commit` | Create commits |
| `git_branch` | Manage branches |

### Web
| Tool | Description |
|------|-------------|
| `fetch_url` | Fetch content from URLs |

### Memory
| Tool | Description |
|------|-------------|
| `save_memory` | Store persistent key-value data |
| `get_memory` | Retrieve stored data |
| `delete_memory` | Remove stored data |

## 📁 Project Structure

```
Jarvis-2.0/
├── main.py              # Entry point
├── config.py            # Configuration management
├── prompts.py           # System prompts
├── core/
│   └── agent.py         # Agent loop implementation
├── tools/
│   ├── base.py          # Base tool class
│   ├── registry.py      # Tool auto-discovery
│   ├── dispatcher.py    # Safe tool execution
│   └── builtin/         # Built-in tools
│       ├── file_tools.py
│       ├── shell_tools.py
│       ├── git_tools.py
│       ├── memory_tools.py
│       └── web_tools.py
└── functions/           # Legacy tools (deprecated)
```

## 🔧 Adding New Tools

1. Create a new file in `tools/builtin/`:

```python
from tools.base import BaseTool, ToolArg, ToolResult

class MyNewTool(BaseTool):
    TOOL_NAME = "my_tool"
    TOOL_DESCRIPTION = "What my tool does"
    TOOL_ARGS = [
        ToolArg(
            name="param1",
            type="string",
            description="Description of param1",
            required=True,
        ),
    ]
    
    def run(self, param1: str, **kwargs) -> ToolResult:
        # Your logic here
        return ToolResult(ok=True, tool=self.TOOL_NAME, result={"data": "..."})
```

2. The tool is **automatically discovered** on next run!

## 💡 Example Sessions

### Exploring a Codebase
```
You: What files are in this project?
Jarvis: → get_files_info
        I found 12 files including main.py, config.py, and a tools/ directory...

You: Show me the main entry point
Jarvis: → get_file_content
        Here's main.py: [contents]
```

### Automating Tasks
```
You: Create a hello.py that prints "Hello World" and run it
Jarvis: → write_file
        → run_python_file
        Done! I created hello.py and ran it. Output: "Hello World"
```

### Git Workflow
```
You: What changes have I made?
Jarvis: → git_status
        → git_diff
        You have modified 3 files: config.py, main.py, and README.md...

You: Commit these with message "Update configuration"
Jarvis: → git_commit
        Committed: "Update configuration" (abc1234)
```

## ⚙️ Configuration

All settings are in `.env`:

```bash
# Required
GEMINI_API_KEY=your_key_here

# Optional
MODEL_NAME=gemini-2.5-flash
TEMPERATURE=0.0
MAX_ITERATIONS=20
VERBOSE=false
DRY_RUN=false
```

## 🔒 Security

Jarvis is designed with safety in mind:

- ✅ All file operations are sandboxed to the working directory
- ✅ Dangerous commands (rm, sudo, etc.) are blocked
- ✅ No eval/exec of arbitrary code
- ✅ Dry-run mode for testing destructive operations
- ✅ All data stays local (no cloud storage)

## 🗺️ Roadmap

- [ ] **Voice Interface** (STT/TTS)
- [ ] **GUI** (Web or Desktop)
- [ ] **Scheduler** (Background tasks)
- [ ] **Long-term Memory** (Vector DB)
- [ ] **More AI Backends** (Ollama, OpenAI, Anthropic)
- [ ] **Plugin System** (Third-party tools)

## 🤝 Contributing

Contributions are welcome! Please:

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Submit a pull request

## 📄 License

MIT License - see LICENSE file for details.

---

Built with ❤️ for the local-first AI community.
