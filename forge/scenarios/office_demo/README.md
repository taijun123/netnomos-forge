# office_demo

`office_demo` is a backend-facing composite scenario for the product office UI.
It does not add new frozen contract types. Instead, it reuses the existing
`RuleSet`, `RuleCard`, `DualReport`, `WorkflowEvent`, and job result envelope,
then adds office-specific JSON fields under the job result:

- `agents`
- `ruleGroups`
- `dataSources`
- `artifacts`
- `office`
- `workflowEvents`

The scenario combines `finance_v1` and `network_cidds` rules, data-source
metadata, and report summaries so the UI can render the six office roles from
real backend state.
