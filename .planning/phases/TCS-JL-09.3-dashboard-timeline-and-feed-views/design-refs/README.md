# design-refs — the 9.3 Stitch exports

The agent can **see** these screens (screenshots render fine in the browser panel) and can read
their **text**, but it cannot read their **markup**: the Stitch MCP only returns download URLs
(`get_screen` → `screenshot` + `htmlCode`), the agent's URL reader strips HTML down to plain text,
a cross-origin `fetch` from the dev origin is refused by CORS, and the cloud-download URL is served
as an attachment so the browser downloads it instead of rendering it.

So the exact Tailwind class strings, spacing values and type scale in the generated HTML are the one
thing still out of reach. Dropping the files here closes that gap — then the rebuild works from the
real markup rather than from a picture of it.

## What to save, and as what

Open each URL below in your browser (they are the `htmlCode` links for the seven screens in Stitch
project `3852118218307261541`, design system `assets/9887579562818178405`) and save the file in **this
folder** under the exact name in the last column. If a link has expired, open Stitch and use that
screen's code panel — or ask the agent to re-issue `get_screen` for a fresh URL.

| Screen | Stitch screen id | Device | Save as |
|---|---|---|---|
| Candidate Dashboard | `317a8ffb6ab640fb97610c52d4c87bcb` | Desktop | `dashboard.html` |
| Candidate Dashboard (mobile) | `8ca8d4bedafa4e2aaa19f6df128eb3a0` | Mobile | `dashboard-mobile.html` |
| Personal Recruitment Timeline | `a8fab62c6c314f4caeba338b28b69f86` | Desktop | `timeline.html` |
| Add / Edit Milestone Modal | `44c81bb31f004537a1c1d0a920aa1a89` | Desktop | `timeline-modal.html` |
| Community Discussions Feed | `39f6f72d9c4a432e988948d38b52f1d9` | Desktop | `feed.html` |
| Community Discussions Feed (mobile) | `b467616e6311419db79024902e88341d` | Mobile | `feed-mobile.html` |
| Create Community Post | `390dc3824ecb41db9e3392cc225c62be` | Desktop | `create-post.html` |

`feed.html` is the priority — it is the surface being rebuilt right now, and it is also the one whose
text extraction returns only its pinned-announcement card.

Download URLs (from this session; regenerate via `get_screen` if they have expired):

```
dashboard        https://contribution.usercontent.google.com/download?c=CgthaWRhX2NvZGVmeBJ7Eh1hcHBfY29tcGFuaW9uX2dlbmVyYXRlZF9maWxlcxpaCiVodG1sX2ZhMTMyOWU0MTRmOTQ3ZDdhNTU2YjIyYWJmZjBkMmUxEgsSBxC_u4XskAcYAZIBIwoKcHJvamVjdF9pZBIVQhMzODUyMTE4MjE4MzA3MjYxNTQx&filename=&opi=96797242
dashboard-mobile https://contribution.usercontent.google.com/download?c=CgthaWRhX2NvZGVmeBJ7Eh1hcHBfY29tcGFuaW9uX2dlbmVyYXRlZF9maWxlcxpaCiVodG1sXzA2MmI2NzUyMzgzOTQ1MjE4YzBlNGJjNDU0MGRmMmFkEgsSBxC_u4XskAcYAZIBIwoKcHJvamVjdF9pZBIVQhMzODUyMTE4MjE4MzA3MjYxNTQx&filename=&opi=96797242
timeline         https://contribution.usercontent.google.com/download?c=CgthaWRhX2NvZGVmeBJ7Eh1hcHBfY29tcGFuaW9uX2dlbmVyYXRlZF9maWxlcxpaCiVodG1sX2E5MDg1YTZlZjBjMDQ0ZDliMmFjMjliODE5ZGQxZWM4EgsSBxC_u4XskAcYAZIBIwoKcHJvamVjdF9pZBIVQhMzODUyMTE4MjE4MzA3MjYxNTQx&filename=&opi=96797242
timeline-modal   https://contribution.usercontent.google.com/download?c=CgthaWRhX2NvZGVmeBJ7Eh1hcHBfY29tcGFuaW9uX2dlbmVyYXRlZF9maWxlcxpaCiVodG1sXzUzMzZmMGRkMTY1NjRiZmJiMzdmYmUxNjE2ZGMzY2E5EgsSBxC_u4XskAcYAZIBIwoKcHJvamVjdF9pZBIVQhMzODUyMTE4MjE4MzA3MjYxNTQx&filename=&opi=96797242
feed             https://contribution.usercontent.google.com/download?c=CgthaWRhX2NvZGVmeBJ7Eh1hcHBfY29tcGFuaW9uX2dlbmVyYXRlZF9maWxlcxpaCiVodG1sX2U3MTc4YjNkNjkwMDRjZDJiNDY5NzdmMTZhYWJlNjQ4EgsSBxC_u4XskAcYAZIBIwoKcHJvamVjdF9pZBIVQhMzODUyMTE4MjE4MzA3MjYxNTQx&filename=&opi=96797242
feed-mobile      https://contribution.usercontent.google.com/download?c=CgthaWRhX2NvZGVmeBJ7Eh1hcHBfY29tcGFuaW9uX2dlbmVyYXRlZF9maWxlcxpaCiVodG1sX2JlYWJjZmFmNzQ5NDQ2OGY5YzkxYmNhNDBlNWY5YTk0EgsSBxC_u4XskAcYAZIBIwoKcHJvamVjdF9pZBIVQhMzODUyMTE4MjE4MzA3MjYxNTQx&filename=&opi=96797242
create-post      https://contribution.usercontent.google.com/download?c=CgthaWRhX2NvZGVmeBJ7Eh1hcHBfY29tcGFuaW9uX2dlbmVyYXRlZF9maWxlcxpaCiVodG1sXzNiMWRjZDY1ZWNhYzQ0ZjI5YzFiNTcwZDM1ODVmNThhEgsSBxC_u4XskAcYAZIBIwoKcHJvamVjdF9pZBIVQhMzODUyMTE4MjE4MzA3MjYxNTQx&filename=&opi=96797242
```

## How the markup will be used

Per the workflow's standing directive, Stitch output is **design reference, not code**: the rebuild
maps what the markup specifies (layout, spacing, radii, weights, sizes, colour roles) onto this
project's own token layer (`src/theme/tokens.ts`, `src/index.css`'s `@theme`) and Tailwind utilities,
rather than importing or pasting the generated HTML. Where the export's values conflict with
`05_UI_UX_SPECIFICATION.md`, the spec wins and the conflict is recorded in
`../09.3-DESIGN-RECONCILIATION.md`.

Everything the export asks for that the API cannot supply stays in that file's recorded-divergence
table — the markup is not licensed to invent data.
