# 🪸 Coral Restoration Optimisation Tool

A Streamlit-based decision support tool that allocates available coral fragments across families to optimise ecological function and assess restoration benchmarks.  

## 🚶 Walkthrough of the App

This section explains each part of the app, what it does, and whether user input is required.

### 🔧 Global Options

#### What it is: 
Advanced settings to control the optimisation.
#### User input: 
Optional: defaults are provided.
- Normalise proportions: Ensures proportions sum to 1 (recommended).
- Proportion tolerance: Allows minor deviations from exact targets to account for whole fragments.
- Survival rate: Assumed % of fragments surviving to reproductive maturity (default 60%, based on peer-reviewed syntheses).
- Use ecological function weightings: If enabled, the optimiser maximises a weighted ecological score (allocation × growth form score) instead of just total fragments.

### 🪸 Available Fragments per Growth Form

#### What it is: 
- The starting supply of coral fragments available in each growth form (e.g. branching, massive).
#### User input: 
- Required: Tick the growth forms you plan to use and enter the number of fragments available. Unticked growth forms are excluded from the optimisation, but their columns remain visible for clarity.

### 📊 Coral Growth Form Proportions

#### What it is: 
- Target proportions for each growth form. Defaults are derived from Madin et al. (2023) by filtering their recommended species for the Indian Ocean and grouping into growth forms.
#### User input:
- Optional — adjust if you have different restoration goals or local ecological knowledge.

### ⚖️ Optimal Allocation (Linear Programming)

#### What it is: 
- The optimiser (using PuLP) calculates the best allocation of fragments across growth forms.
Constraints:
 - Each growth form must meet its minimum target proportion.
 - Allocations cannot exceed available supply.
Objective:
- If ecological weightings are off → maximise the total number of fragments allocated.
- If ecological weightings are on → maximise the weighted ecological score, subject to the constraints.
#### User input: 
- None - this is calculated automatically.
#### Outputs:
- A table of available fragments, optimal allocation, target %, achieved %, and (if enabled) ecological score contributions.
- A bar chart comparing available vs. allocated fragments.
- A pie chart showing proportional allocation.

### 🌐 Simulated Reef Layout

#### What it is: 
- A simple visualisation of how “reef stars” (clusters of ~14 fragments) might be distributed across a restoration site. Includes clustering weights to mimic natural grouping.
#### User input:
- Clustering weights for each growth form (0–1).
- Shuffle button to randomise layout.
- Restoration site area and shape.
### 📏 Ecological Benchmarks
#### What it is: 
- Benchmarks from Ricardo et al. (2025) suggest 13–50 colonies per 100 m² are required for ≥10% fertilisation success. The tool estimates whether your plan meets this, adjusted by the assumed survival rate.
#### User input: 
- None — calculated automatically.
