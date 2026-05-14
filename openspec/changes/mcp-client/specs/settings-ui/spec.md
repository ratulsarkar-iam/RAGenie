# Spec: settings-ui

## Purpose

A dedicated **MCP Servers** settings page in the React frontend that mirrors the UX of Claude Desktop's MCP server config panel: a list of configured servers with live status, a form editor for add/edit, a tool browser, and JSON import/export compatible with `claude_desktop_config.json`.

## New Files

| File | Role |
|------|------|
| `frontend/src/api/mcpClientApi.ts` | Typed API client for `/api/mcp-servers/*` |
| `frontend/src/components/MCPServersPage.tsx` | Main settings page (list + editor) |
| `frontend/src/components/MCPServerEditor.tsx` | Add/edit form panel |
| `frontend/src/components/MCPToolBrowser.tsx` | Discovered tools accordion |
| `frontend/src/components/MCPImportExportModal.tsx` | JSON paste/copy modal |

## Modified Files

| File | Change |
|------|--------|
| `frontend/src/App.tsx` | Add "MCP Servers" route and navigation item |

---

## API Client (`mcpClientApi.ts`)

```typescript
export interface ServerConfig { ... }     // mirrors backend Pydantic model
export interface ServerStatus { ... }
export interface ToolDefinition { ... }
export interface ServerWithStatus { config: ServerConfig; status: ServerStatus; tools: ToolDefinition[] }

export const mcpClientApi = {
  listServers():                Promise<ServerWithStatus[]>
  createServer(data):           Promise<ServerWithStatus>
  getServer(id):                Promise<ServerWithStatus>
  updateServer(id, patch):      Promise<ServerWithStatus>
  deleteServer(id):             Promise<void>
  connectServer(id):            Promise<ServerStatus>
  disconnectServer(id):         Promise<ServerStatus>
  listServerTools(id):          Promise<ToolDefinition[]>
  testServer(id):               Promise<TestResult>
  importServers(json, connectNow): Promise<ImportResult>
  exportServers():              Promise<object>
}
```

---

## MCPServersPage Layout

```
┌─────────────────────────────────────────────────────────────────────────┐
│  MCP Servers                                [+ Add Server] [Import JSON] │
│  ─────────────────────────────────────────────────────────────────────── │
│                                                                         │
│  ┌───────────────────────────┐  ┌────────────────────────────────────┐  │
│  │  filesystem               │  │  Edit: filesystem                  │  │
│  │  stdio  ● Connected  8 🔧 │  │                                    │  │
│  │                           │  │  Name        [filesystem         ] │  │
│  │  github                   │  │  Transport   [stdio ▼            ] │  │
│  │  stdio  ⚠ Error           │  │  Command     [npx               ] │  │
│  │                           │  │  Args        [-y] [@mcp/server-fs]│  │
│  │  my-remote                │  │              [/Users/me/Documents ]│  │
│  │  sse    ○ Disconnected    │  │  Env Vars    [+ Add variable     ] │  │
│  │                           │  │  Enabled     [✅                 ] │  │
│  └───────────────────────────┘  │                                    │  │
│                                 │  [Connect] [Disconnect] [Test]     │  │
│                                 │  [Save Changes]  [Delete Server]   │  │
│                                 │                                    │  │
│                                 │  ── Tools (8) ──────────────────── │  │
│                                 │  📎 read_file                      │  │
│                                 │     Read file at given path        │  │
│                                 │  📎 write_file                     │  │
│                                 │     Write content to a file        │  │
│                                 │  📎 list_directory  ···            │  │
│                                 └────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────────────────┘
```

### Status Badge Colors
- `connected` → green dot `●`
- `connecting` → yellow spinner
- `error` → amber `⚠` + tooltip with `error_message`
- `disconnected` → grey `○`

### Polling
- `GET /api/mcp-servers` polled every **10 seconds** to refresh status badges and tool counts.
- On user-triggered actions (connect, disconnect, save), refresh immediately.

---

## MCPServerEditor Component

### Transport Toggle Behaviour
- When `transport = "stdio"`:
  - Show: **Command**, **Args** (tag input), **Env Vars** (key-value pairs)
  - Hide: **URL**
- When `transport = "sse"`:
  - Show: **URL**
  - Hide: **Command**, **Args**, **Env Vars**

### Args Tag Input
- Each arg is a chip/tag; press Enter or comma to add; click × to remove.
- Raw value stored as `string[]`.

### Env Vars Key-Value Editor
- Rows of `[key input]` `[value input]` `[× remove]`
- `[+ Add variable]` appends a new row.
- Values are masked (password field) by default; eye icon to reveal.

### Test Connection Button
- Calls `testServer(id)` (for existing servers) or shows a tooltip "Save first to test".
- Shows a temporary result banner: ✅ `8 tools found` or ❌ `Connection failed: <error>`.

### Validation (client-side)
- `name` required, non-empty.
- `transport = stdio` → `command` required.
- `transport = sse` → `url` required, must start with `http://` or `https://`.

---

## MCPToolBrowser Component

```
── Tools (8) [Refresh] ──────────────────────────────────
▸ 📎 read_file
    Read the contents of a file at the given path
    Input: { path: string (required) }

▸ 📎 write_file
    Write content to a file at the given path
    Input: { path: string (required), content: string (required) }
...
```

- Accordion: click to expand schema details.
- Schema displayed as a simple property list (name + type + required badge).
- `[Refresh]` button triggers `GET /api/mcp-servers/{id}/tools` and updates list.

---

## MCPImportExportModal Component

### Import Tab
```
┌────────────────────────────────────────────────────────┐
│  Import from Claude Desktop JSON                        │
│                                                         │
│  Paste your claude_desktop_config.json content:         │
│  ┌─────────────────────────────────────────────────┐   │
│  │ {                                               │   │
│  │   "mcpServers": {                               │   │
│  │     "filesystem": { ... }                       │   │
│  │   }                                             │   │
│  │ }                                               │   │
│  └─────────────────────────────────────────────────┘   │
│  ⚠ 2 servers found. 1 already exists (will update).    │
│                                                         │
│  [Cancel]                        [Import & Connect All] │
└────────────────────────────────────────────────────────┘
```

### Export Tab
```
┌────────────────────────────────────────────────────────┐
│  Export as Claude Desktop JSON                          │
│                                                         │
│  ┌─────────────────────────────────────────────────┐   │
│  │ {                                               │   │
│  │   "mcpServers": { ... }                         │   │
│  │ }                                               │   │
│  └─────────────────────────────────────────────────┘   │
│                                                [Copy]  │
└────────────────────────────────────────────────────────┘
```

- JSON textarea is syntax-highlighted (using a lightweight library, e.g. `react-simple-code-editor` + `prism-react-renderer`).
- Parse errors shown inline below the textarea in red.

---

## Chat Tool Badge (App.tsx)

In the chat message input area (bottom bar), add a small pill:

```
🔌 12 tools  ▾
```

- Count = built-in tools + all external MCP tools from connected servers.
- Clicking opens a read-only `MCPToolBrowser` overlay listing all tools (grouped by server).
- Updates whenever MCP server status changes.

---

## Navigation

Add to the existing sidebar/settings navigation (wherever Settings items live in `App.tsx`):

```
Settings
  ├── General
  ├── Models
  ├── MCP Servers     ← new
  └── ...
```

Route: `/settings/mcp-servers`

---

## Dependencies (frontend)

No new mandatory dependencies. Optional enhancements:
- `react-simple-code-editor` + `prismjs` for JSON syntax highlighting in the import/export modal (already used for code blocks if present; otherwise a plain `<textarea>` is acceptable for v1).
