import streamlit as st
import pandas as pd
import pulp
import matplotlib.pyplot as plt
import numpy as np
import math
from matplotlib.patches import Patch


## Page config: wide layout
st.set_page_config(
    page_title="Coral Restoration Optimisation Tool",
    page_icon="🪸",
    layout="wide",
    initial_sidebar_state="expanded"
)


## Default ecological proportions (growth forms only)
default_props = {
    "Branching": 0.234,
    "Massive/Sub-massive": 0.429,
    "Columnar": 0.124,
    "Table/Plate": 0.162,
    "Encrusting": 0.051
}

# Default ecological function scores
default_scores = {
    "Branching": 0.3,
    "Massive/Sub-massive": 0.9,
    "Columnar": 0.56,
    "Table/Plate": 0.45,
    "Encrusting": 0.45
}

st.title("🪸 Coral Restoration Optimisation Tool")
st.write("**Supply-driven mode**: Allocate available coral fragments across growth forms to optimise for ecological function")


## Global Options (collapsible)
with st.expander("Global Options", expanded=False):
    normalize_toggle = st.checkbox(
        "Normalize proportions to sum to 1 (default: on for ecological balance)",
        value=True
    )

    prop_tolerance = st.number_input(
        "Proportion tolerance (whole fragments)",
        min_value=0, max_value=10, value=1, step=1,
        help="Allowed shortfall per group (in fragments) to accommodate integer rounding (0 = strict mode)."
    )

    survival_rate = st.slider(
        "Expected 1-year survival to maturity (%)",
        min_value=0, max_value=100, value=60, step=5,
        help="Percentage of outplanted fragments expected to survive and reach reproductive size after one year, based on peer-reviewed literature."
    ) / 100.0

    use_weights = st.checkbox(
        "Use ecological function weightings",
        value=True,
        help="If enabled, the optimiser maximises the weighted ecological function score instead of just total fragments."
    )

if "layout_seed" not in st.session_state:
    st.session_state.layout_seed = np.random.randint(0, 1_000_000)


## Available Fragments Input + Tickboxes
st.subheader("Available Fragments per Growth Form")
st.caption("Tick to include growth forms and enter the number of fragments available for each.")

supply = {}
enabled_groups = []
excluded_groups = []

cols = st.columns(len(default_props))
for i, gf in enumerate(default_props.keys()):
    with cols[i]:
        include = st.checkbox(gf, value=True, key=f"include_{gf}")
        if include:
            enabled_groups.append(gf)
            input_val = st.text_input("Fragments", value="0", key=f"supply_{gf}")
            try:
                supply[gf] = int(input_val)
            except ValueError:
                st.warning(f"Invalid input for {gf}. Using 0.")
                supply[gf] = 0
        else:
            excluded_groups.append(gf)
            st.text("")  # keep layout aligned (empty col)
            supply[gf] = 0

# 👉 Guard checks after inputs
if sum(supply.values()) == 0:
    st.info("ℹ️ Please enter the number of coral fragments available above to begin optimisation.")
    st.stop()

if any(supply[gf] == 0 for gf in enabled_groups):
    st.error("❌ At least one enabled growth form has 0 available fragments. Please adjust its value or untick it.")
    st.stop()

## Growth form proportions input
st.subheader("Coral Growth Form Proportions")
st.caption(
    "Default proportions are derived from Madin et al. (2023), by filtering their recommended species for the Indian Ocean "
    "and then grouping the set into growth forms and calculating relative representation. Please see documentation for limitations."
)

user_props = {}
cols = st.columns(len(default_props))
for i, gf in enumerate(default_props.keys()):
    with cols[i]:
        if gf in enabled_groups:
            input_val = st.text_input("Target proportion", value=str(default_props[gf]), key=f"text_{gf}")
            try:
                user_props[gf] = float(input_val)
            except ValueError:
                st.warning(f"Invalid input for {gf}. Using default value.")
                user_props[gf] = float(default_props[gf])
        else:
            st.text("")  # keep alignment

if normalize_toggle:
    total_prop = sum(user_props.values())
    if total_prop > 0:
        user_props = {gf: val / total_prop for gf, val in user_props.items()}


##Ecological function scores (if enabled)
eco_scores = {}
if use_weights:
    st.subheader("Ecological Function Scores")
    st.caption(
        "Default values are illustrative functional weights partly inspired by growth rate. "
        "Users should adapt scores to their specific ecological context and management goals."
    )
    cols_scores = st.columns(len(default_props))
    for i, gf in enumerate(default_props.keys()):
        if gf in enabled_groups:
            with cols_scores[i]:
                eco_scores[gf] = st.number_input(
                    gf,
                    min_value=0.0, value=default_scores.get(gf, 1.0), step=0.01, key=f"eco_{gf}"
                )
        else:
            st.text("")  # keep alignment
else:
    eco_scores = {gf: 1.0 for gf in default_props.keys()}


## Linear optimisation with PuLP
alloc = pulp.LpVariable.dicts("alloc", enabled_groups, lowBound=0, cat="Integer")
T = pulp.LpVariable("TotalAllocated", lowBound=1, cat="Integer")
slack = pulp.LpVariable.dicts("slack", enabled_groups, lowBound=0, cat="Integer")

prob = pulp.LpProblem("CoralAllocation", pulp.LpMaximize)

## Objective: maximise weighted ecological function
prob += pulp.lpSum([eco_scores[f] * alloc[f] for f in enabled_groups]), "MaximiseWeightedFunction"

## Total allocated definition
prob += pulp.lpSum([alloc[f] for f in enabled_groups]) == T, "TotalDef"

## Constraints
for gf in enabled_groups:
    prob += alloc[gf] <= supply.get(gf, 0), f"Supply_{gf}"
    prob += alloc[gf] + slack[gf] >= user_props[gf] * T, f"PropLower_{gf}"
    prob += slack[gf] <= prop_tolerance, f"SlackCap_{gf}"

status = prob.solve(pulp.PULP_CBC_CMD(msg=0))
status_str = pulp.LpStatus[status]

if status_str != "Optimal":
    st.error("❌ No feasible solution found. Check supply vs. proportions.")
else:
    allocations = [int(pulp.value(alloc[gf])) for gf in enabled_groups]
    available = [supply.get(gf, 0) for gf in enabled_groups]
    target_perc = [round(user_props[gf], 3) for gf in enabled_groups]

    total_alloc = sum(allocations)
    achieved_perc = [a / total_alloc for a in allocations] if total_alloc > 0 else [0 for _ in allocations]

    result_df = pd.DataFrame({
        "Available": available,
        "Optimal Allocation": allocations,
        "Target %": target_perc,
        "Achieved %": achieved_perc,
        "Eco score": [eco_scores[f] for f in enabled_groups],
        "Score contribution": [eco_scores[f] * a for f, a in zip(enabled_groups, allocations)]
    }, index=enabled_groups)

    ## Add totals row
    result_df.loc["Total"] = [
        sum(result_df["Available"]),
        sum(result_df["Optimal Allocation"]),
        "-",
        1.0 if total_alloc > 0 else 0,
        "-",
        sum(result_df["Score contribution"])
    ]

    st.write("### Optimal Allocation", result_df.round(3))
    st.caption(f"Total ecological function score: {sum(result_df['Score contribution'][:-1]):.2f}")

    
    ## Visualisations
    
    st.subheader("Visualisations")
    col1, col2 = st.columns(2)
    with col1:
        fig, ax = plt.subplots(figsize=(7, 4))
        result_df[["Available", "Optimal Allocation"]].iloc[:-1].plot(kind="bar", ax=ax, rot=0)
        ax.set_xticklabels(enabled_groups, fontsize=9)
        ax.set_title("Fragments: Available vs Planned Allocation", fontsize=12)
        ax.set_ylabel("Number of Fragments", fontsize=10)
        ax.set_xlabel("Growth form", fontsize=10)
        ax.tick_params(axis="y", labelsize=9)
        ax.legend(fontsize=9)
        plt.tight_layout()
        st.pyplot(fig)

    with col2:
        fig2, ax2 = plt.subplots(figsize=(7, 5))
        result_df["Optimal Allocation"].iloc[:-1].plot.pie(
            labels=result_df.index[:-1],
            autopct="%1.1f%%",
            ax=ax2,
            textprops={"fontsize": 9}  # controls pie label font size
        )
        ax2.set_ylabel("")
        ax2.set_title("Proportion of Allocated Fragments", fontsize=12)
        ax2.legend(fontsize=9, bbox_to_anchor=(1.05, 1), loc="upper left")
        st.pyplot(fig2)
    
    ## Reef Layout Grid Visualisation
    
    st.subheader("Simulated Reef Layout with Clustering")

    st.markdown("#### Clustering Weights (0–1)")
    clustering_scores = {}
    default_cluster = {
        "Branching": 0.3,
        "Massive/Sub-massive": 1.0,
        "Columnar": 0.3,
        "Table/Plate": 0.6,
        "Encrusting": 0.6
    }

    cols = st.columns(len(enabled_groups))
    for i, gf in enumerate(enabled_groups):
        with cols[i]:
            st.markdown(f"**{gf}**")
            input_val = st.text_input(
                "Clustering Weight",
                value=str(default_cluster.get(gf, 0.5)),
                key=f"clustering_weight_{gf}"
            )
            try:
                score = float(input_val)
                if score < 0 or score > 1:
                    st.warning(f"{gf}: must be 0–1. Using default.")
                    score = default_cluster.get(gf, 0.5)
            except ValueError:
                st.warning(f"{gf}: invalid input. Using default.")
                score = default_cluster.get(gf, 0.5)
            clustering_scores[gf] = score

    if st.button("🔀 Shuffle Layout"):
        st.session_state.layout_seed = np.random.randint(0, 1_000_000)

    site_area = st.number_input(
        "Restoration Site Area (m²)", min_value=10, value=100, step=10,
        help="Approximate footprint of the restoration plot in square meters. Used to derive an indicative cell size."
    )

    shape_choice = st.selectbox(
        "Site Shape",
        [
            "Square (1:1)",
            "Wide rectangle (2:1)",
            "Very wide (4:1)"
        ],
        index=2,
        help="Overall outline of the site. Affects the grid's width-to-height ratio only."
    )

    ratio_map = {
        "Square (1:1)": 1.0,
        "Wide rectangle (2:1)": 2.0,
        "Very wide (4:1)": 4.0
    }
    site_aspect = ratio_map[shape_choice]

    fragments_per_star = 14
    reef_stars = []
    for gf, alloc_value in zip(enabled_groups, allocations):
        n_stars = max(1, math.ceil(alloc_value / fragments_per_star))
        reef_stars.extend([gf] * n_stars)

    np.random.seed(st.session_state.layout_seed)
    np.random.shuffle(reef_stars)

    total_stars = len(reef_stars)
    reef_height = max(5, int(np.sqrt(total_stars / site_aspect)))
    reef_width = max(5, int(site_aspect * reef_height))

    if reef_height * reef_width > 0:
        cell_area = site_area / (reef_height * reef_width)
        st.caption(f"Approximate area per grid cell: ~{cell_area:.2f} m²")

    grid = np.full((reef_height, reef_width), None, dtype=object)

    unplaced = 0
    for gf in reef_stars:
        score = clustering_scores[gf]
        placed = False
        for _ in range(200):
            if np.random.rand() < score:
                positions = list(zip(*np.where(grid == gf)))
                if positions:
                    y, x = positions[np.random.randint(len(positions))]
                    y_new = min(max(y + np.random.randint(-1, 2), 0), reef_height - 1)
                    x_new = min(max(x + np.random.randint(-1, 2), 0), reef_width - 1)
                else:
                    y_new = np.random.randint(reef_height)
                    x_new = np.random.randint(reef_width)
            else:
                y_new = np.random.randint(reef_height)
                x_new = np.random.randint(reef_width)
            if grid[y_new, x_new] is None:
                grid[y_new, x_new] = gf
                placed = True
                break
        if not placed:
            unplaced += 1

    st.caption("ℹ️ Note: Some reef stars may not fit if the site area is too small or clustering too high. This can be corrected in future model refinements.")

    colors = plt.cm.tab10.colors[:len(enabled_groups)]
    gf_ids = {gf: i for i, gf in enumerate(enabled_groups)}
    color_grid = np.zeros((reef_height, reef_width, 3))
    for gf in enabled_groups:
        mask = grid == gf
        color_grid[mask] = colors[gf_ids[gf]][:3]

    fig, ax = plt.subplots(figsize=(10, 5))
    ax.imshow(color_grid, origin="lower")
    ax.set_xticks([])
    ax.set_yticks([])
    legend_handles = [Patch(color=colors[i], label=gf) for i, gf in enumerate(enabled_groups)]
    ax.legend(handles=legend_handles, bbox_to_anchor=(1.05, 1), loc="upper left")
    ax.set_title(f"Simulated Reef Layout with Clustering (Dynamic Grid)\nEach square ≈ {fragments_per_star} fragments / 1 reef star")
    st.pyplot(fig)

    if unplaced > 0:
        st.warning(f"{unplaced} tiles could not be placed due to space/constraints. Increase area or reduce fragments per tile.")


    
    ## Ecological Benchmarks
    
    st.subheader("Ecological Benchmarks")

    benchmarks = []
    for gf, alloc_value in zip(enabled_groups, allocations):
        expected_adults = alloc_value * survival_rate
        fam_density = (expected_adults / site_area) * 100
        if fam_density < 13:
            status = "⚠️ Below threshold"
        elif fam_density > 50:
            status = "⚠️ Above typical range"
        else:
            status = "✅ Within range"
        benchmarks.append({
            "Growth form": gf,
            "Allocated fragments": int(alloc_value),
            f"Expected adults ({int(survival_rate*100)}%)": int(round(expected_adults)),
            "Density (/100 m²)": round(fam_density, 0),
            "Status": status
        })

    benchmarks_df = pd.DataFrame(benchmarks)
    st.table(benchmarks_df)

    st.caption(
        "Benchmark: 13–50 colonies / 100 m² for ≥10% fertilisation success (Ricardo et al., 2025). "
        f"Survival assumption: ~{int(survival_rate*100)}% one-year survival reported across restoration studies "
        "(Boström-Einarsson et al., 2020)."
    )
