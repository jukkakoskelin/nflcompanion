---
on:
  workflow_dispatch:

permissions:
  contents: read
  issues: read
  copilot-requests: write

network: defaults

tools:
  github:
    toolsets: [default]

safe-outputs:
  create-issue:

---

# Agentic Workflow Access Test

Create a new issue in this repository titled "Agentic Workflow Test Successful".
In the body of the issue, include a short greeting and confirm that the agentic workflow was able to execute successfully.
