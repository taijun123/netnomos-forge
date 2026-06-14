# AI Worksite Handoff

<!-- Maintained by skills/worksite-handoff/scripts/update_handoff.py. -->

- Updated: 2026-06-14 14:10:31 +0800
- Repo: E:\yanchh\model_control\netnomos-forge
- Branch: wip/ui-workspace-real-backend-20260614
- Last Commit: 8ee39e9 fix: require real workflows for finance and network demos
## Objective

Finish NetNomos Forge new UI and make all finance/network one-click demos use real backend workflows

## Current Status

Removed frontend mock fallback from finance/network one-click demos. NetworkDemoPage and FinanceDemoPage now wait for real WorkflowLog results via awaitGate, surface backend errors, and use report-network/report-finance for A/B dual runs. demoDriver autoUpload now always uses uploadDataSource and throws on failure. WorkflowLog and ScenarioRunPanel now propagate backend errors. 3D office finance/network scenario runner now uses report-network/report-finance real jobs and no longer falls back to DUAL_MOCK.

## Changed Files

```text
exit 0
```

## Validation

- npm run build in web => passed
- GET http://127.0.0.1:8000/api/health => status ok, jobs increased from 110 to 122 during browser QA
- Browser topnav one-click network => #/network reached report page, live result 922 rules / 12 cards / 3 violations, uploaded dataSourceId 29ea750b63bd, app console errors/warnings []
- Browser topnav one-click finance => #/finance reached report page, live result 7 rules / 7 cards / 5 violations, uploaded dataSourceId 8e43e07c6d25, app console errors/warnings []
- rg mock fallback in NetworkDemoPage/FinanceDemoPage/office/App/demoDriver => no active imports or fallback usage; only unused demoMocks definitions and explicit no-mock UI text remain
- git diff --check => passed

## Services

- 127.0.0.1:8000 listening
- 127.0.0.1:5173 listening

## Decisions And Boundaries

- Do not merge Jack log commit d807ec9 yet; current UI branch remains independent from Jack log code.
- Network/finance one-click demos should fail visibly if backend fails; no local simulated result may be substituted.
- forge/contracts.py remains untouched.

## Blockers

- None recorded.

## Next Steps

- Continue UI polish only after this real workflow baseline.
- After UI acceptance, review unused demoMocks.ts and Jack log branch separately.

## Agent Notes

- None recorded.
