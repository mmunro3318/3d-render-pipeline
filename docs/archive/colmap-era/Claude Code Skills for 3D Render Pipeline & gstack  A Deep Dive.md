# Claude Code Skills for 3D Render Pipeline & gstack: A Deep Dive

## Executive Summary

This report maps the **real, existing** Claude Code skill ecosystem as it applies to a 3D render pipeline and your existing gstack workflow. It covers gstack's full 28-command anatomy, how Superpowers (the community's leading implementation framework) slots into gstack's gaps, and a curated stack of 3D/game-dev specific skills from real community repos. For every skill, there is a clear answer to the question: *how does this feed into what gstack already does?*

***

## Part 1: gstack — The Full 28-Command Map

gstack is not just a few slash commands. It is an opinionated seven-phase sprint cycle — **Think → Plan → Build → Review → Test → Ship → Reflect** — with 28 specialist roles covering the full lifecycle from napkin sketch to production monitoring.[^1][^2]

### Planning Phase

| Command | Role | What It Actually Does |
|---|---|---|
| `/office-hours` | Discovery consultant (YC mode) | Forces 6 hard questions before any code; generates a design doc that every downstream skill reads. Token cost: ~24k.[^3] |
| `/plan-ceo-review` | Product strategist ("Brian Chesky mode") | Challenges scope with 4 explicit modes: Expansion, Selective Expansion, Hold, Reduction.[^1][^4] |
| `/plan-eng-review` | Architect | Locks data flow, API contracts, edge cases, error handling, test strategy before Build begins.[^2] |
| `/plan-design-review` | Design auditor | Rates every design dimension 0–10; edits until all hit 10; no "we'll polish later."[^2][^1] |
| `/autoplan` | Pipeline | Runs CEO + Design + Eng review automatically; only surfaces taste decisions to the human.[^1] |

One user described `/office-hours` this way: "It challenged my framing, told me I was solving the wrong problem, generated 3 implementation approaches with effort estimates, then wrote a design doc that every other skill in the system reads automatically."[^5]

### Development & Review Phase

| Command | Role | What It Actually Does |
|---|---|---|
| `/review` | Staff engineer | Auto-fixes obvious issues (formatting, imports, naming); flags race conditions, N+1 queries, missing error handling. Token cost: ~19k.[^3][^1] |
| `/investigate` | Debugger | Traces root causes systematically; stops after 3 failed fixes to avoid runaway loops.[^1] |
| `/design-review` | Designer-engineer | Performs a full design audit and fixes findings atomically in the same pass.[^1] |
| `/codex` | Second opinion | Spawns an independent OpenAI Codex CLI review in 3 modes — alternative opinion from a different model.[^1] |

### Testing & Security Phase

| Command | Role | What It Actually Does |
|---|---|---|
| `/qa` | QA lead | Opens a **real headless Chromium** session (persistent, ~100ms per command), identifies affected routes from your diff, tests them, fixes bugs with atomic commits, re-verifies.[^1] |
| `/qa-only` | QA reporter | Same discovery process, no code changes — just a bug report.[^1] |
| `/cso` | Security auditor | Runs OWASP Top 10 + STRIDE threat modeling against your codebase.[^1] |
| `/benchmark` | Performance engineer | Baselines Core Web Vitals and load times.[^1] |

The browser daemon is one of gstack's most technically distinctive features. Unlike standard browser MCP tools that cold-start for every task, gstack runs a persistent Playwright-backed Chromium process. Cold start is ~3 seconds; every subsequent command runs in 100–200ms — claimed to be 20x faster than Chrome MCP alternatives. The stack is 79.6% TypeScript and 18.3% Go, compiled into a ~58MB binary via Bun.[^1]

### Deployment Phase

| Command | Role | What It Actually Does |
|---|---|---|
| `/ship` | Release engineer | Syncs main, runs full test suite, audits coverage, opens PR.[^1] |
| `/land-and-deploy` | Deployment | Merges PR, waits for CI, verifies production health metrics.[^1] |
| `/canary` | SRE | Post-deploy monitoring for console errors and regressions.[^1] |
| `/document-release` | Technical writer | Updates all project docs — README, changelog, API docs — to match what shipped.[^1] |

### Safety & Utilities

| Command | What It Does |
|---|---|
| `/careful` | Warns before destructive commands: `rm -rf`, `DROP TABLE`, force-push.[^1] |
| `/freeze` | Restricts edits to a single directory — critical during debugging sprints.[^1] |
| `/guard` | Activates `/careful` + `/freeze` together for production-adjacent work.[^1] |
| `/browse` | Direct browser automation with the persistent Chromium daemon.[^1] |
| `/retro` | Weekly engineering manager retrospective: per-role breakdowns, shipping streaks, test health.[^1] |

### The gstack Sprint Chain

The canonical flow is:

```
/office-hours → /plan-ceo-review → /plan-eng-review → build → /review → /qa → /ship → /land-and-deploy → /retro
```

You don't have to run every command — gstack is **opt-in at every step**. Many teams start with just `/review` and `/qa` and expand from there.[^1]

***

## Part 2: Superpowers — The Missing Implementation Layer

### What Superpowers Adds

gstack owns **everything before and after implementation**. Superpowers (107k+ stars, obra/superpowers) owns **the implementation loop itself** — specifically the code-writing phase that sits between gstack's `/plan-eng-review` and `/review`.[^6][^1]

A Particula Tech analysis described the relationship directly: "Superpowers owns the implementation loop, gstack owns everything before and after it." Several teams use gstack for planning (`/office-hours`, `/plan-ceo-review`) and QA (`/qa`, `/cso`), while using Superpowers for TDD-driven coding.[^1]

### The 14 Superpowers Skills

| Skill | What It Does | Where It Feeds Into gstack |
|---|---|---|
| `brainstorming` | Socratic design refinement; generates design doc, saves to `docs/` | Deepens the output of `/office-hours`; gstack's design doc becomes better-formed input for plan phase[^7][^6] |
| `writing-plans` | Breaks designs into 2–5 minute tasks with exact file paths, complete code, and expected output; dispatches `plan-document-reviewer` subagent for review[^8][^9] | Operates between gstack's `/plan-eng-review` and Build phase |
| `test-driven-development` | Enforces RED-GREEN-REFACTOR; code written before a failing test exists gets deleted and redone[^6][^7] | The implementation engine inside gstack's Build phase |
| `subagent-driven-development` | Dispatches one **fresh** subagent per task; two-stage review after each (spec compliance first, then code quality)[^10][^11] | Replaces direct coding in main session; parallelizes write work without context pollution |
| `executing-plans` | Batch execution with checkpoints in the current session[^12] | Alternative to subagent-driven when staying in-session |
| `dispatching-parallel-agents` | Concurrent subagent workflows for independent branches[^13] | Parallelizes independent build tasks; feeds cleaner diffs into `/review` |
| `systematic-debugging` | 4-phase root-cause process: reproduce → isolate → hypothesize → fix → verify[^7] | Augments gstack's `/investigate` with structured discipline |
| `using-git-worktrees` | Creates isolated branch and workspace after design approval; verifies clean test baseline before any code[^14][^7] | Prevents main branch contamination during parallel Build tasks |
| `requesting-code-review` | Spawns a fresh `code-reviewer` subagent[^11] | Lightweight alternative to `/review` between individual tasks during Build |
| `finishing-a-development-branch` | Merge/PR/keep/discard options with cleanup[^7] | Hands off cleanly to gstack's `/ship` |
| `using-superpowers` | Meta-skill; mandates skill-first approach before any response or action[^15][^16] | Bootstrap skill — ensures the framework self-applies |
| `writing-skills` | TDD methodology applied to creating new skills themselves[^17] | Lets you grow the skill library with the same discipline as production code |

**The key subagent insight:** Superpowers' `subagent-driven-development` dispatches a **fresh** subagent per task — no context pollution from the main conversation — then runs a two-stage review: spec compliance first, then code quality. The main agent acts as orchestrator only; it does not implement anything directly. One HN user running 200k+ LOC projects put it plainly: "My main agent prompt always has a complete ban on the main agent doing any work themselves. All work is done by subagents which they coordinate."[^10][^11][^18]

A parallel-subagent best practice from the Claude Code team: parallel subagents only work cleanly when agents touch different files. Domain-based routing in `CLAUDE.md` makes this automatic.[^19]

### The Combined Workflow (Superpowers + gstack)

```
gstack /office-hours
  → Superpowers:brainstorming (deeper Socratic design doc)
  → gstack /plan-ceo-review
  → gstack /plan-eng-review
  → Superpowers:writing-plans (TDD-structured task breakdown)
  → Superpowers:using-git-worktrees (isolated branch)
  → Superpowers:subagent-driven-development
       ↳ Each task: fresh subagent → TDD → commit → 2-stage review
  → Superpowers:finishing-a-development-branch
  → gstack /review (staff engineer pass on full diff)
  → gstack /qa (real browser regression testing)
  → gstack /cso (OWASP + STRIDE)
  → gstack /ship → /land-and-deploy → /retro
```

***

## Part 3: 3D & Game Dev Skills — Real Repos, Real Installs

These are verified, real skills from community repos mapped to your 3D render pipeline.

### 1. `game-developer` — Jeffallan/claude-skills ⭐ 403

**Install:**
```bash
git clone https://github.com/Jeffallan/claude-skills.git
cp -r claude-skills/skills/game-developer ~/.claude/skills/
# Or via playbooks:
npx playbooks add skill jeffallan/claude-skills --skill game-developer
```

Positions Claude as a senior game developer across Unity C#, Unreal C++, and Godot. Covers ECS architecture, shader programming, multiplayer networking, game AI, and cross-platform optimization.[^20][^21]

The skill enforces production-grade constraints that prevent the most common AI-generated game code disasters: always use object pooling for frequent instantiation; cache component references, never call `GetComponent` in Update loops; use delta time for frame-independent movement; no hardcoded game values.[^20]

Five reference files load progressively on demand: `unity-patterns.md`, `unreal-cpp.md`, `ecs-patterns.md`, `performance-optimization.md`, `multiplayer-networking.md`.[^21][^20]

**Feeds into gstack:** This skill activates during Build phase. When you run gstack's `/plan-eng-review` on a game system, it produces an architecture doc. The `game-developer` skill then gives the subagent(s) doing implementation the production knowledge to execute it correctly — particularly ECS patterns and shader pipeline design.[^21][^20]

***

### 2. `r3f-best-practices` + 11 R3F Skills — EnzeD/r3f-skills ⭐ 11

**Install:**
```bash
git clone https://github.com/EnzeD/r3f-skills.git
cp -r r3f-skills/skills/* ~/.claude/skills/
```

The `r3f-best-practices` skill contains 70+ rules across 12 priority categories for React Three Fiber + the full Poimandres ecosystem. The 11-skill collection also covers:[^22][^20]

| Sub-skill | Covers |
|---|---|
| `r3f-materials` | PBR materials, Drei materials, shader materials, material properties[^23][^24] |
| `r3f-shaders` | Custom visual effects, vertex shaders, fragment shaders, extending built-in materials[^25] |
| `r3f-loaders` | `useGLTF`, `useLoader`, Suspense patterns, preloading, HDR environments[^26] |
| `r3f-animation` | `useFrame` patterns, animation loops[^27] |
| `r3f-physics` | Rapier physics setup, body types, colliders, collision events[^22] |
| `r3f-postprocessing` | EffectComposer, SelectiveBloom, custom shader effects[^22] |

The single most critical rule — preventing the most common R3F performance disaster — is: **never call `setState` inside `useFrame`**. That causes 60 re-renders per second. Mutate refs directly instead. Without this skill loaded, Claude will generate the broken pattern regularly.[^20]

**Feeds into gstack:** Auto-activates during the Build phase whenever a task touches R3F/Three.js code. Pairs with `game-developer` for the full web 3D stack. The `/benchmark` command in gstack will have cleaner targets to hit if this skill prevented re-render disasters at the code generation stage.[^22][^20]

***

### 3. `threejs-ecs-ts` — Nice-Wolf-Studio/claude-skills-threejs-ecs-ts

**Install:**
```bash
git clone https://github.com/Nice-Wolf-Studio/claude-skills-threejs-ecs-ts.git
cp -r claude-skills-threejs-ecs-ts/skills/* ~/.claude/skills/
```

Three.js + Entity Component System + TypeScript. Covers scene setup, rendering, materials, textures, ECS architecture with ECSY, entity pooling, component caching, and instanced meshes for performance. Bridges the gap between the `game-developer` skill's ECS patterns and actual Three.js/browser implementation.[^28][^29]

**Feeds into gstack:** Activates during Build for TypeScript + Three.js tasks. The ECS guidance ensures that when Superpowers' subagents implement game entities, they follow the same architecture patterns that `/plan-eng-review` specified.[^29]

***

### 4. `DavinciDreams 3D Design Team` — DavinciDreams/Agent-Team-Plugins

**Install:**
```bash
git clone https://github.com/DavinciDreams/Agent-Team-Plugins.git
cp -r Agent-Team-Plugins/teams/3d-design/skills/* ~/.claude/skills/
cp -r Agent-Team-Plugins/teams/3d-design/agents/* ~/.claude/agents/
```

This is the most comprehensive 3D pipeline plugin: 9 skills + 7 pre-built agents covering the entire production pipeline.[^20]

**9 Skills:**

| Skill | Focus |
|---|---|
| `blender` | Interface, workflows, export pipelines (Unity: 1.00 scale, -Z forward, Y up; Unreal: 0.01 scale, -X forward, Z up) |
| `modeling` | Topology, sculpting, subdivision, hard surface vs. organic |
| `texturing` | UV mapping, PBR, Substance workflows, shader nodes |
| `rigging` | Armatures, weight painting, IK, Rigify |
| `animation` | Keyframing, NLA editor, Grease Pencil |
| `asset-optimization` | LOD, texture atlasing, draw call reduction |
| `unity` | Unity integration and export |
| `omniverse` | NVIDIA Omniverse workflows |
| `vroid` | VRoid Studio for avatar/VTuber creation |

**7 Agents:** `modeler`, `texturer`, `rigger`, `animator`, `asset-optimizer`, `3d-analyst`, `vtuber-specialist`.[^20]

**Feeds into gstack:** This is the closest to a full "3D team in a box." When you run `/autoplan` on a 3D pipeline task, the resulting design doc should route to these agents. The `3d-analyst` agent pairs naturally with gstack's `/investigate` for debugging pipeline issues; `asset-optimizer` pairs with `/benchmark` for performance baselines.

***

### 5. `3d-modeling` + `shader-techniques` — majiayu000/claude-skill-registry ⭐ 78

**Install:**
```bash
git clone https://github.com/majiayu000/claude-skill-registry.git
cp -r claude-skill-registry/skills/data/3d-modeling ~/.claude/skills/
cp -r claude-skill-registry/skills/data/shader-techniques ~/.claude/skills/
```

**`3d-modeling`** is a production-grade skill written from "12 years of battle-hardened 3D experience." Strong opinions enforced: always apply scale and rotation before export; quads required for deforming meshes; N-gons unacceptable in final geometry; texel density inconsistency is amateur work. Three reference files: `patterns.md` (how to build), `sharp_edges.md` (failure modes), `validations.md` (rules and constraints).[^20]

**`shader-techniques`** covers HLSL/GLSL across Unity URP/HDRP, Unreal, Godot, and Vulkan/SPIR-V. Includes production-ready shader code (PBR, toon/cel, dissolve, vignette), an operation cost table for optimization decisions, and troubleshooting for the classic failure modes (pink material = compile error; too slow = reduce texture samples and move calculations to vertex shader).[^20]

The shader operation cost table:

| Operation | Relative Cost | Notes |
|---|---|---|
| Add/Multiply | 1x | Baseline |
| Divide | 4x | Avoid in loops |
| Sqrt | 4x | Use rsqrt when possible |
| Sin/Cos | 8x | Use lookup tables on mobile |
| Texture Sample | 4–8x | Varies by hardware |
| Pow | 8x | Use exp2(x*log2(y)) |

**Feeds into gstack:** The `3d-modeling` skill activates during Build phase for any geometry-related tasks; the `shader-techniques` skill activates for shader writing. Both feed directly into gstack's `/review` (where the staff engineer checks correctness) and `/benchmark` (where performance assumptions get tested).[^20]

***

### 6. `shadertoy-shader-development` — MCP Market / mcpmarket.com

**Install:**
```bash
# Via plugin marketplace:
/plugin marketplace add shadertoy-shader-development
# Or manual SKILL.md from mcpmarket.com
```

GLSL ES for Shadertoy/WebGL. Covers ray marching, signed distance fields (SDFs), procedural noise, `fBm`, complex number plots, multi-pass rendering buffers, and browser-based WebGL constraints. This is the skill for custom real-time visual effects in the render pipeline that go beyond what material editors provide.[^30][^31]

**Feeds into gstack:** Auto-activates on shader tasks involving raymarching, SDFs, or Shadertoy-compatible GLSL. The `/cso` skill in gstack has no special graphics security profile, but `/review` can catch shader resource issues with this skill's knowledge injected at the right point.

***

### 7. `blender-3d-modeling` — Andrew1326/dominations

**Install:**
```bash
git clone https://github.com/Andrew1326/dominations.git
cp -r dominations/.claude/skills/blender-3d-modeling ~/.claude/skills/
```

Laser-focused on Blender Python scripting for procedural geometry. Covers `bpy.from_pydata()`, `bmesh` operations (extrude, subdivide, per-face manipulation), modifier application, Bezier/NURBS curves, procedural generation patterns, and material assignment per face.[^20]

Key enforced rules: use `from_pydata()` for static meshes, bmesh for anything requiring operations; always `mesh.update()` after `from_pydata()`; always `bm.free()` after bmesh operations; for 10k+ face meshes, prefer bmesh over repeated `bpy.ops` calls (operator overhead); Blender is Z-up — account for Y-up game engines.[^20]

**Feeds into gstack:** During Build phase, when subagents generate Blender Python scripts for your render pipeline, this prevents the bmesh memory management errors and coordinate system mismatches that would otherwise require gstack's `/investigate` to debug.

***

### 8. `blender-automation` — phuetz/code-buddy

**Install:**
```bash
git clone https://github.com/phuetz/code-buddy.git
mkdir -p ~/.claude/skills/blender-automation
cp code-buddy/.codebuddy/skills/bundled/blender/SKILL.md ~/.claude/skills/blender-automation/
```

Covers Blender automation beyond geometry creation: command-line rendering, batch processing, Geometry Nodes scripting, and MCP server integration.[^20]

Five workflow templates: batch render multiple scenes; procedural asset generation with random placement; camera animation sequences (orbital paths); batch model import and render (portfolio turntables); material library application.[^20]

MCP tools registered: `blender_execute_script`, `blender_render_frame`, `blender_create_object`, `blender_modify_object`, `blender_set_material`, `blender_add_keyframe`, `blender_import_model`, `blender_export_model`, `blender_list_objects`, `blender_get_scene_info`.[^20]

**Feeds into gstack:** This is where your Blender MCP integration slots in. When `/plan-eng-review` specifies a render pipeline automation task, this skill makes the Build phase execute it correctly. `/qa` can then verify the rendered output via the persistent browser daemon.[^20]

***

## Part 4: Highly Recommended Utility Skills

### `multi-agent-architecture-patterns` — MCP Market

Covers Supervisor/Orchestrator pattern, Peer-to-Peer Swarms, and Hierarchical delegation layers for distributed LLM systems. Provides context isolation strategies and formal handoff protocols that prevent "lost-in-the-middle" degradation in single-agent setups. 5.5k popularity score in ecosystem rankings.[^32][^33]

**Feeds into gstack:** This is the meta-skill that makes `/autoplan` smarter. When gstack's pipeline decides how to partition a 3D pipeline task across specialist agents, this skill provides the architectural patterns for doing that correctly.

### `context-engineering` — Community Registry

Context engineering fundamentals for reducing token waste and preventing context window bloat in long sessions. Rated 5.5k stars in ecosystem rankings. Pairs with Anthropic's official guidance on context compression in multi-agent sessions.[^34][^32]

**Feeds into gstack:** Token costs are real. `/office-hours` alone costs ~24k tokens, `/plan-ceo-review` ~27.5k. Context engineering discipline reduces session costs while maintaining quality — relevant if you're running the full gstack pipeline frequently.[^3]

### `writing-skills` — obra/superpowers

The skill for creating new skills using TDD methodology: write a failing baseline test (run Claude without the skill, document where it goes wrong), then write minimal skill content to fix exactly those failures. This is how you build domain-specific skills for your own 3D pipeline conventions.[^17]

**Feeds into gstack:** `/document-release` in gstack updates docs after shipping. `writing-skills` lets you encode what you learned during a sprint into new skills — making each sprint improve the system for the next one.

***

## Part 5: CLAUDE.md Routing for gstack + Skills

The recommended setup for wiring skills into gstack via `CLAUDE.md`:[^35][^19]

```markdown
# Skill Routing

## Planning
- For new features: use /office-hours before /plan-ceo-review
- For architecture decisions: use /plan-eng-review

## Build Phase
- For game systems, shaders, ECS: load game-developer skill
- For Three.js/R3F: load r3f-best-practices + r3f-shaders
- For Blender Python: load blender-3d-modeling
- For Blender automation/rendering: load blender-automation
- For GLSL/WebGL shaders: load shader-techniques or shadertoy-shader-development
- For complex implementations: use Superpowers subagent-driven-development

## Subagent Rules
- Parallel subagents: ONLY when agents touch different files
- Domain boundaries: frontend (R3F/Three.js) | backend (render pipeline) | assets (Blender)
- Main agent: orchestrates only. All implementation via subagents.

## Safety
- Before any destructive command: /careful
- During active debugging: /freeze [target directory]
```

Skills load lazily — only ~100 tokens at startup for the name/description; full SKILL.md loads only when the task matches. This means you can have all of these installed without meaningful context overhead until they're actually relevant.[^36]

***

## Part 6: Security Note

The Snyk ToxicSkills study found prompt injection in 36% of skills tested and 1,467 malicious payloads across the ecosystem. Before installing any skill, read the `SKILL.md` and any bundled scripts. The `allowed-tools` frontmatter field shows what tools a skill can use — a Blender automation skill that requests `Bash` access for running `blender --background --python` is reasonable; a texturing reference skill that requests `Bash` access warrants more scrutiny.[^20]

All skills listed in this report come from identifiable sources with readable content.

***

## Recommended Install Sequence

For a 3D render pipeline + gstack setup, install in this order:

1. **Superpowers** (`obra/superpowers`) — fills gstack's implementation gap
2. **`game-developer`** (`Jeffallan/claude-skills`) — core 3D/game engine knowledge
3. **EnzeD R3F skills** (`EnzeD/r3f-skills`) — R3F/Three.js + shader/physics/post-processing
4. **`threejs-ecs-ts`** (`Nice-Wolf-Studio`) — ECS + TypeScript integration
5. **`DavinciDreams 3D Design Team`** (`DavinciDreams/Agent-Team-Plugins`) — full pipeline + 7 agents
6. **`3d-modeling` + `shader-techniques`** (`majiayu000/claude-skill-registry`) — production topology + HLSL/GLSL
7. **`blender-3d-modeling`** (`Andrew1326`) — procedural Python
8. **`blender-automation`** (`phuetz/code-buddy`) — CLI + Geometry Nodes + MCP
9. **`shadertoy-shader-development`** — ray marching / SDF / WebGL
10. **`writing-skills`** (already in Superpowers) — build your own domain skills with TDD

---

## References

1. [GStack Guide - Garry Tan's Claude Code Skill Pack](https://awesomeagents.ai/guides/gstack-garry-tan-claude-code-guide/) - GStack turns Claude Code into a virtual dev team with 28 slash commands for planning, review, QA, se...

2. [gstack: The AI Development Workflow That Changes Everything](https://www.dench.com/blog/gstack-explained) - gstack is DenchClaw's structured AI development workflow — 7 phases, 18 specialist roles — that tran...

3. [Is gstack by Garry Tan worth it ? : r/ClaudeAI - Reddit](https://www.reddit.com/r/ClaudeAI/comments/1s8hcgo/is_gstack_by_garry_tan_worth_it/) - The popular skills such as: /office-hours is roughly 24k tokens. /plan-ceo-review is 27.5k tokens. /...

4. [Garry Tan runs YC with 13 Claude Code “/“ commands. Full ...](https://www.facebook.com/61571060319687/posts/garry-tan-runs-yc-with-13-claude-code-commandsfull-breakdown-of-planning-phaseof/122162365052702010/) - Garry Tan runs YC with 13 Claude Code “/“ commands. Full breakdown of Planning Phase: /office-hours ...

5. [best coding agent skill i've used. just tried garry tan's gstack today ...](https://www.facebook.com/thanhhm/posts/best-coding-agent-skill-ive-used-just-tried-garry-tans-gstack-today-three-things/10164693084058126/) - best coding agent skill i've used. just tried garry tan's gstack today, three things stood out: /off...

6. [The Superpowers Plugin for Claude Code: The Structured Workflow ...](https://www.builder.io/blog/claude-code-superpowers-plugin) - It enforces a structured four-step workflow (brainstorm, isolate a git worktree, write a detailed pl...

7. [Superpowers Plugin for Claude Code: The Complete Tutorial](https://namiru.ai/blog/superpowers-plugin-for-claude-code-the-complete-tutorial) - What Superpowers actually does · Brainstorm: refines your idea through Socratic questioning · Plan: ...

8. [superpowers/skills/writing-plans/SKILL.md at main - GitHub](https://github.com/obra/superpowers/blob/main/skills/writing-plans/SKILL.md) - Write comprehensive implementation plans assuming the engineer has zero context for our codebase and...

9. [Writing Plans - Superpowers - Mintlify](https://www.mintlify.com/obra/superpowers/skills/writing-plans) - Brainstorming Ideas Into Designs · Test-Driven Development (TDD) · Systematic Debugging · Writing Pl...

10. [SKILL.md - Subagent-Driven Development - GitHub](https://github.com/obra/superpowers/blob/main/skills/subagent-driven-development/SKILL.md) - Execute plan by dispatching fresh subagent per task, with two-stage review after each: spec complian...

11. [Subagent-Driven Development | SkillsHunt](https://skillshunt.io/skills/superpowers/subagent-driven-development) - Execute plan by dispatching fresh subagent per task, with code review after each. Core principle: Fr...

12. [Skills Library Overview - Superpowers - Mintlify](https://www.mintlify.com/obra/superpowers/skills/overview) - Brainstorming · Writing Plans · Execution Choice · Subagent-Driven Development · Executing Plans · T...

13. [Dispatching Parallel Agents - obra/superpowers - GitHub](https://github.com/obra/superpowers/blob/main/skills/dispatching-parallel-agents/SKILL.md) - You delegate tasks to specialized agents with isolated context. By precisely crafting their instruct...

14. [Top 10 Claude Code Skills Every Builder Should Know in 2026](https://composio.dev/content/top-claude-skills) - Remotion Best Practices Skill. The Remotion Best Practices Skill gives Claude deep domain knowledge ...

15. [Using Superpowers - Mintlify](https://mintlify.com/obra/superpowers/skills/using-superpowers) - The using-superpowers skill establishes the fundamental rule for working with the Superpowers framew...

16. [Using Superpowers - Claude Code Skill Workflow Guide - MCP Market](https://mcpmarket.com/tools/skills/using-superpowers-5) - Enforces a rigorous workflow for identifying and invoking specialized skills before responding to an...

17. [superpowers/skills/writing-skills/SKILL.md at main - GitHub](https://github.com/obra/superpowers/blob/main/skills/writing-skills/SKILL.md) - Skills help future Claude instances find and apply effective approaches. Skills are: Reusable techni...

18. [How to use Claude Code subagents to parallelize development](https://news.ycombinator.com/item?id=45181577) - Like many others here, I believe subagents will starve for context. Claude Code Agent is context-ric...

19. [Claude Code Sub-Agents: Parallel vs Sequential Patterns](https://claudefa.st/blog/guide/agents/sub-agent-best-practices) - The central AI should dispatch parallel sub-agents when work spans independent domains. Configure do...

20. [Top 8 Claude Skills for 3D Modeling, Game Dev, and Shader ... - Snyk](https://snyk.io/articles/top-claude-skills-3d-modeling-game-dev-shader-programming/) - From Blender Python automation to shader writing and game engine scripting, these 8 Claude Skills gi...

21. [game-developer - jeffallan/claude-skills](https://skills-rank.com/skill/jeffallan/claude-skills/game-developer) - You specialize in Unity C#, Unreal C++, ECS architecture, and cross-platform optimization. You build...

22. [r3f-best-practices - Agent Skills](https://agentskills.me/skill/r3f-best-practices) - Optimizing R3F performance (re-renders are the #1 issue); Using Drei helpers correctly; Managing sta...

23. [R3f Materials — AI Coding Skill - Claude Skills Playground](https://skillsplayground.com/skills/enzed-r3f-skills-r3f-materials/) - React Three Fiber materials - PBR materials, Drei materials, shader materials, material properties. ...

24. [r3f-materials - Agent Skill by enzed/r3f-skills](https://agentskills.so/skills/enzed-r3f-skills-r3f-materials) - r3f-textures - Texture loading and configuration; r3f-shaders - Custom shader development; r3f-light...

25. [R3f Shaders — AI Coding Skill | Skills Playground](https://skillsplayground.com/skills/enzed-r3f-skills-r3f-shaders/) - Use when creating custom visual effects, modifying vertices, writing fragment shaders, or extending ...

26. [R3f Loaders — AI Coding Skill - Claude Skills Playground](https://skillsplayground.com/skills/enzed-r3f-skills-r3f-loaders/) - React Three Fiber asset loading - useGLTF, useLoader, Suspense patterns, preloading. Use when loadin...

27. [11 React Three Fiber (R3F) skills for Claude Code and Codex ...](https://x.com/NicolasZu/status/2013725848818376955) - 🛠️11 React Three Fiber (R3F) skills for Claude Code and Codex: animation, shaders, physics, postproc...

28. [Claude Code Skills: Three.js, ECS, and TypeScript - GitHub](https://github.com/Nice-Wolf-Studio/claude-skills-threejs-ecs-ts) - This repository contains specialized skills that extend Claude Code's capabilities for: Three.js Dev...

29. [claude skills for three.js and typescript - Shyft](https://shyft.ai/skills/claude-skills-threejs-ecs-ts) - Use Claude skills for Three.js and ECS-TS development. Streamline your TypeScript projects with spec...

30. [Shadertoy Shader Development | Claude Code Skill for GLSL](https://mcpmarket.com/tools/skills/shadertoy-shader-development) - Master GLSL with the Shadertoy Shader Development Claude Code skill. Create procedural graphics, 3D ...

31. [Shadertoy Shader Development - Claude Code Skill - MCP Market](https://mcpmarket.com/tools/skills/shadertoy-shader-development-1) - It provides a comprehensive library of shader patterns—including ray marching, signed distance field...

32. [Claude Code Skills: Top 20 Most Popular Skills in 2026](https://www.heyuan110.com/posts/ai/2026-01-20-claude-code-skills-top20/) - 1. Superpowers (29.1k Stars) · Enforced TDD (Test-Driven Development) · YAGNI principle (You Aren't ...

33. [Multi-Agent Architecture Patterns | Claude Code Skill - MCP Market](https://mcpmarket.com/tools/skills/multi-agent-architecture-patterns-4) - Architects complex LLM workflows using advanced multi-agent patterns like supervisors, swarms, and h...

34. [Effective context engineering for AI agents - Anthropic](https://www.anthropic.com/engineering/effective-context-engineering-for-ai-agents) - Anthropic's agentic coding solution Claude Code uses this approach to perform complex data analysis ...

35. [gstack/qa/SKILL.md at main - GitHub](https://github.com/garrytan/gstack/blob/main/qa/SKILL.md) - gstack works best when your project's CLAUDE.md includes skill routing rules. This tells Claude to u...

36. [How to Implement Context Engineering Strategies for your Agent ...](https://newsletter.victordibia.com/p/context-engineering-101-how-agents) - How to Implement Context Engineering Strategies for your Agent (Claude Code). #59 | Managing context...

