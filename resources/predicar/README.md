# PREDICAR resources

This directory contains preparation materials only.

- Papers are local reading copies linked from `references/predicar/resource-manifest.json`.
- Source kits are downloaded for inspection/reference and remain outside the runtime package.
- The AllenSDK archive is marked optional because it is a large external toolkit; it is not imported by the core package.
- No large dataset, video, private source or raw biological record is included.
- Before redistribution, review the license and notices of every archive and paper.

The fetch script is:

```powershell
.\tools\fetch_predicar_resources.ps1
```

Optional large toolkit:

```powershell
.\tools\fetch_predicar_resources.ps1 -IncludeOptionalLargeKits -Force
```
