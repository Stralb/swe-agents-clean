# BOUNDED PRE-CHANGE IMPLEMENTATION CONTEXT

Target: `.github/scripts/sync-skills.js`

Relevant pre-change structure:

```js
const fs = require("fs");
const path = require("path");

const SKILLS_DIR = "skills";
const MARKETPLACE_FILE = ".claude-plugin/marketplace.json";
const README_FILE = "README.md";

function getSkillsWithMetadata() {
  // scans skills/ and returns normalized metadata
}

function updateReadme(skills) {
  // refreshes the generated skills table
}

function updateMarketplace(skills) {
  // Existing marketplace synchronization implementation.
  // Its body is not included in this bounded packet.
}

function main() {
  const skills = getSkillsWithMetadata();

  const marketplaceResult = updateMarketplace(skills);
  const readmeUpdated = updateReadme(skills);

  if (!marketplaceResult.updated && !readmeUpdated) {
    console.log("Everything is already in sync");
    return;
  }

  if (marketplaceResult.updated) {
    console.log(`Updated marketplace.json (${skills.length} skills)`);
  }

  if (readmeUpdated) {
    console.log("Updated README.md skills table");
  }
}

main();
```

Implement the task within this synchronization script, preserving its existing style and command-line behavior.
