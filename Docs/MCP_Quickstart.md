# MCP Server Quick Start Guide

## What You'll Need

- **Logarithmic** installed and running
- **Claude Desktop** app installed ([Download here](https://claude.ai/download))
- **5 minutes** to set everything up

That's it! Let's get started.

## Step 1: Enable MCP in Logarithmic

1. **Open Logarithmic**

2. **Go to Settings**
   - Click the **⚙️ Settings** tab at the top

3. **Enable MCP Server**
   - Scroll down to the **MCP Server** section
   - Check the box next to **Enable MCP Server**
   - Leave the default settings (Address: `127.0.0.1`, Port: `3000`) unless you know you need to change them

4. **Restart Logarithmic**
   - Close and reopen the application
   - The MCP server will now start automatically

✅ **You should see a message in the console**: "MCP server started on 127.0.0.1:3000"

## Step 2: Add Your Log Files

1. **Add logs in Logarithmic**
   - In the main window, enter the path to a log file
   - Click **Add Log**
   - Repeat for all logs you want to analyze

2. **Verify logs are tracked**
   - You should see your logs listed in the **📄 Logs** tab
   - The MCP server will automatically make these available to Claude

💡 **Tip**: You can add friendly names to your logs later (see [MCP Details Guide](MCP_Details.md#making-logs-more-understandable))

## Step 3: Configure Claude Desktop

### Find Your Config File

Locate your Claude Desktop configuration file:

- **Windows**: `%APPDATA%\Claude\claude_desktop_config.json`
- **macOS**: `~/Library/Application Support/Claude/claude_desktop_config.json`
- **Linux**: `~/.config/Claude/claude_desktop_config.json`

💡 **Tip**: On Windows, press `Win+R`, type `%APPDATA%\Claude`, and press Enter to open the folder.

### Edit the Config File

1. **Open the file** in a text editor (Notepad, VS Code, etc.)

2. **Add the Logarithmic MCP server**:

```json
{
  "mcpServers": {
    "logarithmic": {
      "url": "http://127.0.0.1:3000/sse",
      "transport": "sse"
    }
  }
}
```

3. **Save the file**

4. **Restart Claude Desktop**

⚠️ **Important**: If the file already has content, make sure to merge the `mcpServers` section properly. The file must be valid JSON.

### Verify It's Working

1. Open Claude Desktop
2. Start a new conversation
3. Look for a small indicator showing MCP servers are connected
4. Ask Claude: "List all available logs"

If everything is set up correctly, Claude will show you the logs that Logarithmic is tracking!

## Step 4: Start Using It!

### Try These Example Questions

Once everything is set up, you can ask Claude:

#### 📋 **List Your Logs**
"What logs are available?"

"List all my tracked logs"

#### 🔍 **Search for Issues**
"Search for 'ERROR' in all logs"

"Find all database connection failures"

"Show me warnings from the last hour"

#### 📖 **Read Specific Logs**
"Show me the application server log"

"What's in the error log?"

#### 🧠 **Analyze and Debug**
"What are the most common errors?"

"Summarize what happened between 2pm and 3pm"

"Why did the application crash?"

"Are there any patterns in these errors?"

### How Claude Accesses Your Logs

Claude can use three main capabilities:

1. **List logs** - See what log files you're tracking
2. **Read logs** - Get the full content of any log file
3. **Search logs** - Find specific patterns across all logs

You don't need to know the technical details—just ask Claude in natural language!

## Troubleshooting

### "No logs available" in Claude

**Check these things**:
- ✅ Did you add log files in Logarithmic?
- ✅ Did you enable MCP server in Settings?
- ✅ Did you restart Logarithmic after enabling?
- ✅ Is Claude Desktop configured correctly?

### MCP Server Won't Start

**Port already in use?**
1. Go to Logarithmic → Settings → MCP Server
2. Change port from `3000` to `8080` (or another number)
3. Restart Logarithmic
4. Update your Claude Desktop config to use the new port

**Check the console**:
- When you start Logarithmic, you should see: "MCP server started on 127.0.0.1:3000"
- If you see an error, read the message—it usually tells you what's wrong

### Claude Can't Find My Logs

**Make sure logs are tracked**:
- Open Logarithmic
- Check the **📄 Logs** tab
- Your log files should be listed there
- If not, add them using the input box at the top

### Claude Desktop Not Connecting

**Check your config file**:
1. Make sure the JSON is valid (use a JSON validator online if unsure)
2. Verify the file path is correct
3. Make sure you saved the file after editing
4. Restart Claude Desktop after changing the config

## Tips for Best Results

### 💡 Give Your Logs Friendly Names

Instead of asking Claude about `C:/logs/app.log`, you can set up friendly names like "application-server" or "error-log". See the [MCP Details Guide](MCP_Details.md#making-logs-more-understandable) for how to do this.

### 💡 Be Specific with Questions

Better: "Search for database errors in the last 100 lines"

Less specific: "Are there errors?"

### 💡 Use Follow-Up Questions

Claude remembers the context of your conversation, so you can ask follow-up questions:

1. "Search for 'timeout' in all logs"
2. "Show me the context around the first one"
3. "What happened right before that?"

### 💡 Ask for Analysis

Don't just search—ask Claude to analyze:
- "What patterns do you see in these errors?"
- "Which errors are most critical?"
- "Can you explain what caused this issue?"

## What's Next?

### Learn More

- **[MCP Details Guide](MCP_Details.md)** - Learn about all the features, example conversations, and advanced configuration
- **[Main README](../README.md)** - Learn more about Logarithmic's other features

### Start Exploring

Now that you're set up:
1. Try the example questions above
2. Experiment with different types of queries
3. Use Claude to help debug real issues
4. Share your experience and help improve the docs!

### Need Help?

If something isn't working:
1. Check the Troubleshooting section above
2. Review the console output when starting Logarithmic
3. Make sure all steps were followed correctly
4. Try the simplest test first: "List all logs"

---

**Happy log analyzing! 🎉**
