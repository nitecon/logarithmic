# MCP Server User Guide

## What is the MCP Server?

Logarithmic includes a built-in **Model Context Protocol (MCP) server** that allows AI assistants like Claude Desktop to directly access and analyze your log files. This means you can ask Claude questions about your logs, search for patterns, debug issues, and get intelligent insights—all without leaving your conversation with the AI.

## Why Use MCP with Logarithmic?

### 🤖 **AI-Powered Log Analysis**
Instead of manually searching through logs, ask Claude:
- "What errors occurred in the last hour?"
- "Find all database connection failures"
- "Summarize the main issues in my application logs"

### 🔍 **Intelligent Search**
Claude can search across all your logs simultaneously and provide context-aware results, understanding patterns and relationships that might be hard to spot manually.

### 🐛 **Faster Debugging**
Describe a problem to Claude and let it analyze your logs to find the root cause, suggest fixes, or identify related issues.

### 📊 **Log Insights**
Ask Claude to analyze trends, count occurrences, or extract specific information from your logs without writing scripts.

## How It Works

When you enable the MCP server in Logarithmic:

1. **Logarithmic starts an HTTP server** in the background (default: `http://127.0.0.1:3000`)
2. **The server monitors all your tracked logs** in real-time
3. **Claude Desktop connects** to this server via HTTP/SSE (Server-Sent Events)
4. **You ask Claude questions** about your logs in natural language
5. **Claude uses the MCP protocol** to list, search, and read your log files
6. **You get intelligent answers** based on the actual content of your logs

The MCP server runs locally on your computer alongside the GUI, so your logs never leave your machine unless you explicitly configure remote access. You can continue using Logarithmic normally while the MCP server is running.

## Getting Started

### Step 1: Enable the MCP Server

1. Open Logarithmic
2. Go to the **⚙️ Settings** tab
3. Scroll down to the **MCP Server** section
4. Check **Enable MCP Server**
5. (Optional) Adjust the port if 3000 is already in use
6. **Restart Logarithmic** for the changes to take effect

### Step 2: Add Your Logs

Make sure you've added the log files you want to analyze in the main Logarithmic window. The MCP server will automatically make these available to Claude.

### Step 3: Configure Claude Desktop

See the [MCP Quick Start Guide](MCP_QUICKSTART.md) for detailed Claude Desktop configuration instructions.

### Step 4: Start Chatting!

Once configured, you can ask Claude questions like:
- "List all my tracked logs"
- "Search for 'ERROR' in all logs"
- "Show me the application-server log"
- "What warnings appeared in the last 100 lines?"

## What Can Claude Do with Your Logs?

When connected to Logarithmic's MCP server, Claude can:

### 📋 List Your Logs
Claude can see all the log files you're tracking and their descriptions.

**Example**: "What logs are available?"

### 📖 Read Log Content
Claude can retrieve and read the full content of any tracked log file.

**Example**: "Show me the application server log"

### 🔍 Search Across Logs
Claude can search for specific patterns across all your logs at once.

**Example**: "Search for 'database timeout' in all logs"

**Example**: "Find all ERROR messages"

### 🧠 Analyze and Summarize
Claude can analyze log content to find patterns, count occurrences, or provide summaries.

**Example**: "What are the most common errors in my logs?"

**Example**: "Summarize what happened between 2pm and 3pm"

## Making Logs More Understandable

### Adding Log Metadata

By default, logs are identified by their full file path (e.g., `C:/logs/app.log`). You can make them more readable to Claude by adding custom IDs and descriptions.

**To add metadata**, edit your session file at:
- **Windows**: `%USERPROFILE%\.logarithmic\sessions\default.json`
- **macOS/Linux**: `~/.logarithmic/sessions/default.json`

Add a `log_metadata` section:

```json
{
  "log_metadata": {
    "C:/logs/app.log": {
      "id": "application-server",
      "description": "Main application server log"
    },
    "C:/logs/error.log": {
      "id": "error-log",
      "description": "Application error log"
    }
  }
}
```

Now when you ask Claude "Show me the application-server log", it will know exactly which file you mean!

## Example Conversations with Claude

Here are some real-world examples of how you might use Claude with your logs:

### Debugging a Production Issue

**You**: "Search for 'connection refused' in all logs"

**Claude**: *Searches and finds 3 occurrences in the application-server log*

**You**: "Show me the context around those errors"

**Claude**: *Displays the relevant log sections*

**You**: "What happened right before the first connection error?"

**Claude**: *Analyzes the log and identifies the sequence of events*

### Monitoring Application Health

**You**: "Are there any errors in my logs from the last hour?"

**Claude**: *Searches recent logs and reports findings*

**You**: "How many times did the database timeout occur?"

**Claude**: *Counts occurrences and provides the number*

### Understanding Log Patterns

**You**: "What are the most common warnings in my application logs?"

**Claude**: *Analyzes the log and summarizes warning patterns*

**You**: "Show me an example of each warning type"

**Claude**: *Provides representative examples*

## Troubleshooting

### Claude says "No logs available"

**Solution**: Make sure you've:
1. Added log files in the main Logarithmic window
2. Enabled the MCP server in Settings
3. Restarted Logarithmic after enabling MCP
4. Configured Claude Desktop correctly (see [Quick Start](MCP_QUICKSTART.md))

### MCP Server Won't Start

**Check the port**: The default port 3000 might be in use. Try:
1. Go to Settings → MCP Server
2. Change the port to something else (e.g., 8080)
3. Restart Logarithmic
4. Update your Claude Desktop config with the new port

**Check the console**: When you start Logarithmic, look for MCP-related messages in the console output.

### Claude Can't Find a Specific Log

**Use the correct ID**: If you've added metadata, use the custom ID (e.g., "application-server") instead of the file path.

**Check it's tracked**: Make sure the log file is actually added in Logarithmic's main window.

### Logs Are Empty or Outdated

**Restart Logarithmic**: The MCP server captures logs when it starts. If you added logs after starting, restart the application.

**Check file permissions**: Make sure Logarithmic can read the log files.

## Security and Privacy

### Local by Default

By default, the MCP server only accepts connections from your local computer (`127.0.0.1`). Your logs never leave your machine.

### Remote Access (Advanced)

If you need to access logs from another computer, you can change the binding address to `0.0.0.0` in Settings. 

⚠️ **Warning**: This exposes your logs to your network. Only do this on trusted networks and consider the security implications.

### What Data is Shared?

When Claude accesses your logs through MCP:
- **Log content** is sent to Claude (Anthropic) for analysis
- This is the same as if you copy-pasted log content into Claude
- Standard Claude privacy policies apply
- Logs are not stored by the MCP server beyond what's in Logarithmic's memory

## Advanced Configuration

### Custom Port

If port 3000 conflicts with another application:

1. Go to Settings → MCP Server
2. Change the port number (e.g., 8080, 9000)
3. Restart Logarithmic
4. Update your Claude Desktop config to use the new port

### Multiple Sessions

Each Logarithmic session can have its own MCP configuration. Switch sessions to work with different sets of logs.

## Getting Help

If you encounter issues:

1. **Check the Quick Start**: [MCP_QUICKSTART.md](MCP_QUICKSTART.md) has step-by-step setup instructions
2. **Review console output**: Logarithmic prints helpful messages about MCP server status
3. **Verify Claude config**: Make sure your Claude Desktop configuration is correct
4. **Test basic functionality**: Try "List all logs" first to verify the connection works

## What's Next?

Once you have MCP working:

- Experiment with different types of questions to Claude
- Add metadata to make your logs more descriptive
- Try analyzing logs from multiple sources simultaneously
- Use Claude to help write log analysis scripts or queries

The MCP server makes your logs accessible to AI, opening up new possibilities for log analysis, debugging, and monitoring!
