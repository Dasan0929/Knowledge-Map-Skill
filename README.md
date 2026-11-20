# Knowledge Map

Turn a topic into a visual learning map so you can see what to learn first and work through each module with an AI agent, one core question at a time.

![Learning map for Jung’s eight function-attitudes](image.png)

## Quick start

You’ll need Codex with local file access and Python 3.9 or later. The map scripts use the Python standard library. A browser can open the offline preview, and Obsidian is optional.

1. From the root of this checkout, copy the entire skill folder into Codex’s project skill directory.

   ```sh
   mkdir -p .agents/skills
   cp -R skills/knowledge-map .agents/skills/
   ```

   Open this folder in Codex. If the skill doesn’t appear, restart Codex and open the folder again. See the [Codex skills documentation](https://learn.chatgpt.com/docs/build-skills#where-codex-loads-local-skills) for how project skills are discovered.

2. In Codex, select `$knowledge-map` and try this prompt.

   ```text
   Use $knowledge-map to help me learn Jung’s eight function-attitudes.
   I want to distinguish all eight and illustrate the differences with a concrete situation.
   ```

3. Open the generated HTML preview in a browser. Click a card to see its core question and prerequisites. To view or edit the Canvas, place the `.canvas` file in an Obsidian vault and open it from there. You can also download the [included HTML example](examples/jungian-functions/learning-map.html) and open it locally before setting up the skill.

## Why a learning map?

A conversation can answer the question you have right now. When the topic spans several concepts, it’s easy to lose track of what to learn first and how the pieces fit together. A learning map makes the prerequisites visible and gives each module one question you can bring into a learning conversation.

For example, a card about **sensation and intuition** might ask, “In the same situation, what would sensation attend to, and what would intuition pick up?” That question gives the module a clear stopping point. The full map follows the same principle. Its modules cover what you need to reach a specific objective, such as distinguishing the eight function-attitudes in one concrete situation and explaining the limits of that interpretation.

## How a map takes shape

1. **Find a starting point.** For a broad request such as “I want to learn AI,” the skill asks what you want to do or understand and may ask a few short questions about your background. A focused request such as the Jungian functions example can go straight to a draft.
2. **Draft the route.** The skill creates five to eight modules. Each card describes what you’ll learn and poses a core question. Arrows run from prerequisite to dependent module. In the example, the common framework leads to parallel branches for perception and judgment, which meet when you compare similar-looking behaviors.
3. **Revise and confirm.** Tell the agent which parts you already know or where you’d like more practice. The skill updates the map and locks the route once you confirm it.
4. **Zoom in when needed.** A module that needs more structure can become a smaller map. Its core question becomes the objective for that submap, and its cards cover the steps needed to answer it.
**Example：**
[!image.png]


## Generated files

| File | What it contains |
| --- | --- |
| `learning-map.canvas` | An editable JSON Canvas with cards, layout, and prerequisite arrows. |
| `learning-map.html` | An offline browser preview with zoom, pan, and clickable card details. |
| `map.json` | The source of truth for module content, core questions, prerequisites, and route status. |
| `context.json` | The learning objective, scope, assumptions, and links between parent and child maps. |

Canvas edits are local to that view. Rebuilding reads the content and dependencies from `map.json`.

## Project status and development

v0.3 is a draft. The HTML preview has been tested in a browser, and the Canvas exporter has passed structural and reference checks. 

- [Skill instructions](skills/knowledge-map/SKILL.md) describe how the agent scopes, drafts, revises, and confirms a route.
- [Map protocol](skills/knowledge-map/references/protocol.md) documents the state files and the validation and build commands.

Run the test suite from the root of this checkout.

```sh
python3 -m unittest discover -s skills/knowledge-map/tests -v
```
