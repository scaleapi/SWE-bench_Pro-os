# Codex Tool Set

This tool bundle provides 4 essential file operations tools designed for code editing agents, matching OpenAI's function interface.

## Tools Overview

### 1. apply_patch
Apply patches in OpenAI's custom patch format for multi-file operations.

**Interface:**
```typescript
type apply_patch = (_: {
  patch: string,
}) => any;
```

**Usage:**
```bash
apply_patch --patch '*** Begin Patch
*** Update File: foo.py
 def hello():
-    print("old")
+    print("new")
*** End Patch'
```

### 2. read_file
Read file contents with optional line range.

**Interface:**
```typescript
type read_file = (_: {
  path: string,
  line_start?: number,  // default: 1
  line_end?: number,    // default: 20
}) => any;
```

**Usage:**
```bash
read_file --path src/main.py
read_file --path src/main.py --line_start 10 --line_end 50
```

### 3. list_files
List directory contents in tree structure.

**Interface:**
```typescript
type list_files = (_: {
  path?: string,   // default: ""
  depth?: number,  // default: 1
}) => any;
```

**Usage:**
```bash
list_files
list_files --path src --depth 2
```

### 4. find_matches
Search for text patterns in files (like grep).

**Interface:**
```typescript
type find_matches = (_: {
  query: string,
  path?: string,        // default: ""
  max_results?: number, // default: 50
}) => any;
```

**Usage:**
```bash
find_matches --query "def main"
find_matches --query "TODO" --path src --max_results 100
```

## Configuration

This tool bundle is configured in `config/jeff_tool_gpt5_codex.yaml`:

```yaml
agent:
  tools:
    bundles:
      - path: tools/codex_set
    enable_bash_tool: false  # No terminal access, only these 4 functions
```

## Design Philosophy

This is a **4-function, no-terminal** tool set that provides:
- ✅ **File reading** - View code before editing
- ✅ **File searching** - Find relevant code locations
- ✅ **Directory listing** - Understand project structure
- ✅ **File editing** - Apply changes via patches

**No bash/terminal access** - All operations are restricted to these 4 safe file operations.

## Advantages

1. **Constrained interface** - Only 4 functions, easier for models to use correctly
2. **Safe operations** - No arbitrary command execution
3. **Multi-file support** - apply_patch can modify many files in one call
4. **Fuzzy matching** - apply_patch tolerates whitespace differences
5. **Standard interface** - Matches OpenAI's function calling format

## File Structure

```
tools/codex_set/
├── bin/
│   ├── apply_patch      # Patch application tool
│   ├── read_file        # File reading tool
│   ├── list_files       # Directory listing tool
│   └── find_matches     # Text search tool
├── config.yaml          # Tool configuration
└── README.md           # This file
```

## Testing

All tools have been tested and verified:
- ✅ read_file: Reads files with line ranges
- ✅ list_files: Shows directory trees
- ✅ find_matches: Searches for patterns
- ✅ apply_patch: Applies multi-file patches with fuzzy matching

## Related Tools

- `tools/edit_anthropic` - Alternative editing tools (str_replace_editor)
- `tools/apply_patch` - Standalone patch tool (stdin-based)
- `tools/submit` - Task submission tools
