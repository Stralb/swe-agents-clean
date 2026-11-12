# AUTHENTIC PRE-EXISTING REPOSITORY CONTEXT

The following code existed in the repository before the task's historical implementation.

```text
function updateMarketplace(skills) {
  const marketplace = JSON.parse(fs.readFileSync(MARKETPLACE_FILE, "utf8"));
  const plugin = marketplace.plugins[0];

  const oldDescription = plugin.description;
  const newDescription = updateSkillCount(plugin.description, skills.length);
  const hadStaleSkillsArray = "skills" in plugin;

  if (newDescription === oldDescription && !hadStaleSkillsArray) {
    return { updated: false };
  }

  plugin.description = newDescription;
  delete plugin.skills;

  fs.writeFileSync(MARKETPLACE_FILE, JSON.stringify(marketplace, null, 2) + "\n");

  return { updated: true, removedSkillsArray: hadStaleSkillsArray };
}
```
