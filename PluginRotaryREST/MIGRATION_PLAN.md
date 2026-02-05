# Migration Plan: PluginRotaryRP → PluginRotaryREST

## Overview
This plan outlines the steps to create a fresh copy of PluginRotaryRP as PluginRotaryREST, with all necessary naming updates and project structure adaptations.

## Project Analysis

### Source Project (PluginRotaryRP)
- **Framework**: .NET Framework 4.5.1 (old-style csproj)
- **Namespace**: `PluginRotaryRP`
- **Main Classes**: 
  - `PluginRotaryRP` (main plugin class)
  - `RotaryRP` (rotary device implementation)
  - `TurntableRestClient` (REST API client)
  - `PluginUtils` (utility class)
- **Dependencies**:
  - `PluginRotaryInterface.dll` (external)
  - `Common.dll` (external)
  - `Newtonsoft.Json.dll` (NuGet package)
  - `System.Net.Http` (framework)

### Destination Project (PluginRotaryREST)
- **Framework**: .NET 10.0 (SDK-style csproj) - **NOTE: May need to change to .NET Framework 4.8 or .NET 8.0 depending on compatibility requirements**
- **Namespace**: `PluginRotaryREST` (target)
- **Current State**: Empty project with Class1.cs placeholder
- **References Already Added** ✅:
  - `Common.dll` (from FlexScan3D 3.5 installation: `C:\Program Files\Polyga\FlexScan3D 3.5\App\Common.dll`)
  - `PluginRotaryInterface.dll` (from FlexScan3D 3.5 installation: `C:\Program Files\Polyga\FlexScan3D 3.5\App\PluginRotaryInterface.dll`)
  - `Newtonsoft.Json` (added - either as DLL reference or NuGet package)
  - All FlexScan3D references set with `<Private>False</Private>` (correct for FlexScan3D plugins)

## Step-by-Step Migration Plan

### Phase 1: Project Configuration Setup

#### 1.1 Update .csproj File
- [x] ✅ Add project references:
  - [x] `PluginRotaryInterface.dll` (already added from FlexScan3D 3.5)
  - [x] `Common.dll` (already added from FlexScan3D 3.5)
  - [x] `Newtonsoft.Json` (already added)
- [ ] Set assembly name and root namespace:
  - [ ] Add `<AssemblyName>PluginRotaryREST</AssemblyName>`
  - [ ] Add `<RootNamespace>PluginRotaryREST</RootNamespace>`
- [ ] Configure output paths (if needed for FlexScan3D plugin deployment)
- [ ] Configure build configurations (Debug/Release, x86/x64) if needed
- [ ] Change target framework if needed (verify compatibility - currently .NET 10.0, may need .NET Framework 4.8)

#### 1.2 Remove Placeholder Files
- [ ] Delete `Class1.cs`

### Phase 2: Copy and Adapt Source Files

#### 2.1 Core Implementation Files
- [ ] **PluginRotaryRP.cs** → **PluginRotaryREST.cs**
  - Copy file
  - Update namespace: `PluginRotaryRP` → `PluginRotaryREST`
  - Update class name: `PluginRotaryRP` → `PluginRotaryREST`
  - Update `pluginID` property: `"PluginRotaryRP"` → `"PluginRotaryREST"`
  - Update rotary ID generation: `pluginID + "::Turntable"` (will auto-update)
  - Update all log messages containing "PluginRotaryRP" → "PluginRotaryREST"

- [ ] **RotaryRP.cs** → **RotaryREST.cs**
  - Copy file
  - Update namespace: `PluginRotaryRP` → `PluginRotaryREST`
  - Update class name: `RotaryRP` → `RotaryREST`
  - Update static property: `nMotors` (keep as is)
  - Update all references to `RotaryRP` → `RotaryREST`
  - Update all log messages containing "RotaryRP" → "RotaryREST"
  - Update Settings references: `Properties.Settings.Default.Rotary_RP_*` → `Properties.Settings.Default.Rotary_REST_*`

- [ ] **TurntableRestClient.cs**
  - Copy file (name can stay the same)
  - Update namespace: `PluginRotaryRP` → `PluginRotaryREST`
  - Update log messages if they contain "PluginRotaryRP"

- [ ] **PluginUtils.cs**
  - Copy file (name can stay the same)
  - Update namespace: `PluginRotaryRP` → `PluginRotaryREST`

#### 2.2 Settings and Configuration Files
- [ ] **Settings.cs**
  - Copy file
  - Update namespace: `PluginRotaryRP.Properties` → `PluginRotaryREST.Properties`

- [ ] **Properties/Settings.settings**
  - Copy file
  - Update `GeneratedClassNamespace`: `PluginRotaryRP.Properties` → `PluginRotaryREST.Properties`
  - Update setting names:
    - `_Rotary_RP_CurrentSteps` → `_Rotary_REST_CurrentSteps`
    - `Rotary_RP_Speed` → `Rotary_REST_Speed`
    - `Rotary_RP_ServerUrl` → `Rotary_REST_ServerUrl`
    - `Rotary_RP_StepsPerDegree` → `Rotary_REST_StepsPerDegree`

- [ ] **Properties/Settings.Designer.cs**
  - Copy file
  - Update namespace: `PluginRotaryRP.Properties` → `PluginRotaryREST.Properties`
  - Update all property names:
    - `_Rotary_RP_CurrentSteps` → `_Rotary_REST_CurrentSteps`
    - `Rotary_RP_Speed` → `Rotary_REST_Speed`
    - `Rotary_RP_ServerUrl` → `Rotary_REST_ServerUrl`
    - `Rotary_RP_StepsPerDegree` → `Rotary_REST_StepsPerDegree`

- [ ] **Properties/AssemblyInfo.cs**
  - Copy file (or create new one for SDK-style project)
  - Update assembly attributes:
    - `AssemblyTitle("PluginRotaryRP")` → `AssemblyTitle("PluginRotaryREST")`
    - `AssemblyProduct("PluginRotaryRP")` → `AssemblyProduct("PluginRotaryREST")`
    - Generate new GUID for the assembly

#### 2.3 Configuration Files
- [ ] **app.config**
  - Copy file
  - Update section name: `PluginRotaryRP.Properties.Settings` → `PluginRotaryREST.Properties.Settings`
  - Update setting names:
    - `Rotary_RP_Speed` → `Rotary_REST_Speed`
    - `Rotary_RP_ServerUrl` → `Rotary_REST_ServerUrl`
    - `Rotary_RP_StepsPerDegree` → `Rotary_REST_StepsPerDegree`
  - Update startup runtime version if needed

- [ ] **PluginRotaryRP.dll.config** → **PluginRotaryREST.dll.config**
  - Copy file with new name
  - Apply same updates as app.config

### Phase 3: Update All References

#### 3.1 Code References
- [ ] Search and replace in all `.cs` files:
  - `PluginRotaryRP` (namespace) → `PluginRotaryREST`
  - `class RotaryRP` → `class RotaryREST`
  - `new RotaryRP()` → `new RotaryREST()`
  - `RotaryRP rotary` → `RotaryREST rotary`
  - `RotaryRP.nMotors` → `RotaryREST.nMotors`
  - `Rotary_RP_` → `Rotary_REST_` (in Settings references)
  - `"PluginRotaryRP"` → `"PluginRotaryREST"` (in pluginID)

#### 3.2 String Literals and Log Messages
- [ ] Update all log messages containing:
  - `"PluginRotaryRP"` → `"PluginRotaryREST"`
  - `"RotaryRP"` → `"RotaryREST"`

### Phase 4: Dependency Management

#### 4.1 External DLLs
- [x] ✅ FlexScan3D Library References (Already Complete):
  - [x] `PluginRotaryInterface.dll` (referenced from FlexScan3D 3.5 installation)
  - [x] `Common.dll` (referenced from FlexScan3D 3.5 installation)
  - [x] `Newtonsoft.Json` (already added - either as DLL or NuGet)

#### 4.2 NuGet Packages
- [x] ✅ `Newtonsoft.Json` (already added)
- [x] ✅ Packages restored (if using NuGet)

### Phase 5: Build and Verification

#### 5.1 Build Configuration
- [ ] Clean solution
- [ ] Build Debug configuration
- [ ] Build Release configuration
- [ ] Verify no compilation errors
- [ ] Verify no missing references

#### 5.2 Testing Checklist
- [ ] Verify assembly name is `PluginRotaryREST`
- [ ] Verify namespace is `PluginRotaryREST`
- [ ] Verify pluginID returns `"PluginRotaryREST"`
- [ ] Verify all settings are accessible with new names
- [ ] Verify REST client functionality
- [ ] Test rotary connection and movement

### Phase 6: Cleanup

#### 6.1 Remove Unused Files
- [ ] Remove any temporary files
- [ ] Remove old placeholder files

#### 6.2 Documentation
- [ ] Update any inline comments if needed
- [ ] Update README if exists

## Important Considerations

### Framework Compatibility
⚠️ **IMPORTANT**: The destination project uses `.NET 10.0`, which may not be compatible with:
- `PluginRotaryInterface.dll` (from FlexScan3D 3.5 - likely .NET Framework)
- `Common.dll` (from FlexScan3D 3.5 - likely .NET Framework)

**Current Status**: References are already added and pointing to FlexScan3D 3.5 installation. If build fails due to framework incompatibility:
- **Option 1**: Change target framework to `.NET Framework 4.8` (most compatible with FlexScan3D)
- **Option 2**: Try `.NET 8.0` if FlexScan3D DLLs support it
- **Option 3**: Keep `.NET 10.0` if it works (test during Phase 5)

**Note**: Since references are from FlexScan3D 3.5 installation, the framework compatibility will be determined during the first build attempt.

### Naming Convention Changes
- `PluginRotaryRP` → `PluginRotaryREST`
- `RotaryRP` → `RotaryREST`
- `Rotary_RP_*` → `Rotary_REST_*` (settings)
- All namespace references updated

### Settings Migration
Users with existing settings will need to:
- Update settings in app.config manually, OR
- Settings will be reset to defaults (if using user settings)

## Files to Copy (Summary)

### Source Files (from PluginRotaryRP)
1. `PluginRotaryRP.cs` → `PluginRotaryREST.cs`
2. `RotaryRP.cs` → `RotaryREST.cs`
3. `TurntableRestClient.cs` (keep name)
4. `PluginUtils.cs` (keep name)
5. `Settings.cs` (keep name)
6. `Properties/AssemblyInfo.cs`
7. `Properties/Settings.settings`
8. `Properties/Settings.Designer.cs`
9. `app.config`
10. `PluginRotaryRP.dll.config` → `PluginRotaryREST.dll.config`

### Files NOT to Copy
- `flex/` directory (appears to be FlexScan3D-specific)
- Documentation files (`.md` files)
- Python files (`turntable_client.py`, `turntable_gui.py`)
- Screenshot files
- Build artifacts (`obj/`, `bin/`)

## Execution Order

1. **First**: Complete .csproj configuration (set assembly name/namespace - dependencies are done ✅)
2. **Second**: Copy all source files
3. **Third**: Perform all search-and-replace operations
4. **Fourth**: Build and fix any compilation errors (including framework compatibility issues)
5. **Fifth**: Test functionality

## Current Progress

### ✅ Completed
- ✅ FlexScan3D library references added (`Common.dll`, `PluginRotaryInterface.dll`)
- ✅ Newtonsoft.Json reference added
- ✅ Project structure created
- ✅ All dependencies configured

### 🔄 Remaining Tasks
- Configure assembly name and root namespace in .csproj
- Copy and adapt all source files (Phase 2)
- Update all naming references (Phase 3)
- Build and test (Phase 5)

---

**Status**: Plan updated - FlexScan3D references confirmed. Ready for next steps.
