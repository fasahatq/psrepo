# Cluster Inference Guidelines
## Perfect Store — India Shopper-Led Cluster Summaries

> **Purpose**: This document instructs the LLM to generate cluster summaries, inferences, and commercial action plans in the style of a shopper-led cluster methodology. All outputs must be grounded in the data features provided and presented in the exact structure below.

---

## §1 Core Philosophy

Every cluster summary must answer two strategic questions:

- **Where to Play** — Which channel, occasion, and shopper type does this cluster represent?
- **How to Win** — What portfolio, execution, and activation levers will drive incremental revenue?

Summaries must be **data-grounded** (cite feature values), **India-contextualised** (use GT/MT/AfH terminology, SEC codes, Rs. price points), and **commercially actionable** (tie every insight to a specific commercial lever).

---

## §2 Channel Taxonomy

| Channel Code | India Name | Store Types | Shopper Mission | Execution Focus |
|---|---|---|---|---|
| GT | General Trade / Traditional Trade | Kirana, pan shops, local grocers, neighbourhood stores | Top-up, impulse, immediate | Hero SKU availability, MBD, chiller placement |
| MT | Modern Trade / Organised Trade | Supermarkets, hypermarkets, cash & carry, convenience chains | Weekly stock-up, planned purchase | Range, planogram compliance, secondary display |
| AfH | Away from Home | Dhabas, QSR, canteens, hotels, transit food courts | Meal occasion, on-the-move, social | Single-serve formats, combo visibility, cooler |
| EC | E-Commerce | Online grocery, quick commerce (Blinkit, Zepto, Swiggy Instamart) | Convenience, future consumption | Pack-size mix, bundle promotions, ratings |

Each cluster **must be assigned one primary channel** and, if evidence supports it, a secondary channel.

---

## §3 Shopper Occasion Framework

Map every cluster to **one primary occasion** using the signals below:

| Occasion | Key Signals | Typical Channel | India Shopper Archetype |
|---|---|---|---|
| Immediate Consumption / Grab & Go | High % IC, high single-serve, high MRP ≤ Rs. 20 packs | GT, AfH | Impulse buyer at kirana or dhaba |
| Future Consumption / Stock-up | High multi-pack, high LTR packs, planned purchase indicators | MT, EC | Family shopper at supermarket |
| Meal Accompaniment | High food-adjacent SKU mix, lunch/dinner footfall POI | AfH, MT | Household cook or restaurant-goer |
| Celebratory / Social Sharing | High party packs (1.25L–2L), bulk, seasonal spike | MT, GT | Festival & event shopper |
| On-the-Move / Transit | Proximity to transit POI, petrol pumps, highways | GT, AfH | Commuter / traveller |
| Youth / Youngsters | Proximity to schools, colleges; high Rs. 10–20 share | GT | Student impulse buyer |
| Premium / Indulgence | High ASP, premium brand mix, low price-sensitive pack share | MT, AfH | Urban affluent weekend treat |
| Morning / Breakfast | Morning footfall spike, breakfast category adjacency | GT, AfH | Office-goer / daily routine shopper |

---

## §4 Demographic Dimensions

### 4.1 Socioeconomic Classification (SEC)

| SEC | Monthly HH Income (approx.) | Key Sensitivity | Pack Priority |
|---|---|---|---|
| A1/A2 | > Rs. 50,000 | Quality & brand | Large-format, premium variants |
| B1/B2 | Rs. 25,000–50,000 | Value for money | Mid-pack (500 ml–1L), gifting |
| C | Rs. 15,000–25,000 | Price-performance | Rs. 20–40 price points |
| D/E | < Rs. 15,000 | Affordability | Rs. 5–10 price points, sachet |

### 4.2 Age & Life-Stage Signals

- **Youth (15–24)**: school/college POI density, high Rs. 10 impulse share
- **Young Adults (25–35)**: office POI, quick-commerce growth, premium mix
- **Families (35–50)**: supermarket proximity, multi-pack, weekend peak
- **Seniors (50+)**: traditional kirana loyalty, low digital, high-repeat SKUs

### 4.3 Urbanicity

| Tier | Definition | Activation Nuance |
|---|---|---|
| Metro | Mumbai, Delhi, Bengaluru, Hyderabad, Chennai, Kolkata | Full range, premium, digital |
| Tier-1 | State capitals, 1M+ population | Core range + aspirational SKUs |
| Tier-2/3 | 100K–1M population | Hero SKUs, price-pack focus |
| Rural | < 100K | Rs. 5/10 packs, strong GT |

### 4.4 POI Signals → Occasion Mapping

| POI Type | Occasion Inference |
|---|---|
| Schools / Colleges | Youth Impulse, Rs. 10 pack priority |
| Offices / IT parks | On-the-Move, premium convenience |
| Hospitals | Hydration/functional, single-serve |
| Transit hubs (railway, bus stands) | On-the-Move, pack variety |
| Tourist spots | Tourist/Premium, souvenir packs |
| Dhabas / Restaurants | Meal Accompaniment, AfH activation |
| Residential density (high) | Stock-up, family multi-pack |

---

## §5 Required Output Sections

Generate **all seven sections** for every cluster. Do not skip or merge sections.

---

### Section 1: Cluster Identity Card

```
CLUSTER [N] — [CLUSTER NAME]
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Cluster ID        : [N]
Primary Channel   : [GT / MT / AfH / EC]
Primary Occasion  : [from §3 table]
Outlet Count      : [N] stores ([X]% of universe)
Avg Monthly VPO   : Rs. [X]
Growth Potential  : [High / Medium / Low]
SEC Profile       : [A/B/C/D/E dominant]
```

---

### Section 2: Shopper Profile

3–5 sentences covering:
- Who shops here (age, SEC, life-stage)
- What they buy and why (occasion, need state)
- When they shop (time of day, week, season)
- How they shop (impulse vs. planned, basket size)

Use India-specific language: "kirana loyalty", "festival stocking", "evening chai break", "office-goer", etc.

---

### Section 3: Demographic & Catchment Profile

3–5 sentences covering:
- Dominant SEC band and income sensitivity
- Urbanicity / tier
- POI mix (residential / commercial / transit / institutional)
- Seasonal or event-driven demand patterns
- Key neighbourhood archetype (e.g. "college corridor", "suburban residential", "highway dhaba cluster")

---

### Section 4: Store Characteristics

3–5 sentences covering:
- Store size / outlet type (kirana vs supermarket vs dhaba)
- VPO level and revenue tier
- SKU depth and breadth (range carried vs universe average)
- Chiller / cooler presence
- Execution quality (planogram compliance, secondary displays)

---

### Section 5: Sales Behaviour Dimensions

Score each cluster on **8 dimensions** on a scale of **1 (low) to 5 (high)** relative to the universe average. Derive scores from the underlying feature data.

| Dimension | Score (1–5) | Rationale |
|---|---|---|
| Beverage Category Depth | [1–5] | SKU range relative to universe |
| Immediate Consumption Mix | [1–5] | % IC volume vs avg |
| Seasonal Demand Spike | [1–5] | Seasonal index |
| Premium Mix | [1–5] | High-ASP SKU share |
| Low Price-Pack Dependency | [1–5] | Rs. 5–10 pack share (high = 5) |
| Footfall Intensity | [1–5] | Footfall index |
| Loyalty / Repeat Purchase | [1–5] | Basket repeat frequency proxy |
| Execution Quality | [1–5] | Planogram + chiller compliance |

**After the table, include a radar chart instruction block:**

```
[RADAR CHART]
Axes: Beverage Depth, IC Mix, Seasonal Spike, Premium Mix,
      Low Price-Pack, Footfall, Loyalty, Execution
Scale: 1–5
Cluster line: [colour per §6 palette]
Universe average overlay: grey dashed (#888888)
Fill: cluster colour at 25% opacity
```

---

### Section 6: Comparative Cluster Snapshot

Provide a markdown table comparing **all clusters** on 5 key metrics, with this cluster's row highlighted:

| Cluster | Name | Count | Avg VPO (Rs.) | IC Mix | Premium Mix | Growth Potential |
|---|---|---|---|---|---|---|
| 1 | … | … | … | … | … | … |
| **[N]** | **[THIS CLUSTER]** | **…** | **…** | **…** | **…** | **…** |

**After the table, include a bar chart instruction block:**

```
[BAR CHART]
X-axis: Cluster names
Y-axis (left): Avg VPO (Rs.)
Y-axis (right): Outlet count
Bar colour: #004B87 (VPO), #009CDE (count)
Highlight this cluster with outline: #FFB81C (gold)
```

---

### Section 7: Commercial Action Plan

Provide **6–8 specific, implementable actions**. Structure each as:

```
ACTION [N]: [LEVER TYPE]
Initiative : [Specific initiative name]
Objective  : [What business outcome this drives]
Hero SKUs  : [Specific SKUs / packs to prioritise]
Channel    : [GT / MT / AfH / EC]
Timeline   : [Immediate (0–4 wks) / Short (1–3 mo) / Medium (3–6 mo)]
KPI        : [Measurable metric to track success]
```

Cover at least one action from each of these **8 levers** across the plan:
1. **Portfolio** — pack-price architecture, new SKU introduction
2. **Merch & Space** — shelf share, secondary display, chiller placement
3. **Hero SKU Distribution** — must-stock list, numeric distribution target
4. **Picture of Success (PoS)** — planogram, shelf standards, POSM
5. **Pricing & Promo** — price-pack bridge, promotional mechanic
6. **Occasion Activation** — occasion-led campaign, seasonal push
7. **Demographic Targeting** — SEC-tailored offer, age-group activation
8. **Channel Partnership** — trade terms, retailer engagement, loyalty programme

---

## §6 Visualisation Instructions

All charts must be generated in Python. Use the following specifications.

### 6.1 Radar / Spider Chart (per cluster)

```python
import numpy as np
import matplotlib.pyplot as plt

DIMENSIONS = [
    "Beverage\nDepth", "IC Mix", "Seasonal\nSpike",
    "Premium Mix", "Low Price-Pack", "Footfall",
    "Loyalty", "Execution"
]
CLUSTER_COLOURS = [
    "#004B87", "#009CDE", "#E4002B", "#FFB81C",
    "#41B6E6", "#6CC24A", "#FF6900", "#7B2D8B"
]

def plot_radar(scores, universe_avg, cluster_name, colour, ax=None):
    N = len(DIMENSIONS)
    angles = np.linspace(0, 2 * np.pi, N, endpoint=False).tolist()
    scores_plot = scores + [scores[0]]
    universe_plot = universe_avg + [universe_avg[0]]
    angles += angles[:1]

    if ax is None:
        fig, ax = plt.subplots(figsize=(6, 6), subplot_kw=dict(polar=True))

    ax.plot(angles, scores_plot, color=colour, linewidth=2, label=cluster_name)
    ax.fill(angles, scores_plot, color=colour, alpha=0.25)
    ax.plot(angles, universe_plot, color="#888888", linewidth=1.5,
            linestyle="--", label="Universe Avg")
    ax.set_xticks(angles[:-1])
    ax.set_xticklabels(DIMENSIONS, size=9)
    ax.set_ylim(0, 5)
    ax.set_yticks([1, 2, 3, 4, 5])
    ax.legend(loc="upper right", bbox_to_anchor=(1.3, 1.1))
    ax.set_title(cluster_name, size=13, fontweight="bold", pad=20)
    return ax
```

### 6.2 Grouped Bar Chart (VPO + Outlet Count by Cluster)

```python
def plot_cluster_bars(cluster_names, vpo_values, outlet_counts):
    x = np.arange(len(cluster_names))
    width = 0.35
    fig, ax1 = plt.subplots(figsize=(10, 5))
    ax2 = ax1.twinx()

    bars1 = ax1.bar(x - width/2, vpo_values, width, color="#004B87", label="Avg VPO (Rs.)")
    bars2 = ax2.bar(x + width/2, outlet_counts, width, color="#009CDE", label="Outlet Count")

    ax1.set_xlabel("Cluster")
    ax1.set_ylabel("Avg Monthly VPO (Rs.)", color="#004B87")
    ax2.set_ylabel("Outlet Count", color="#009CDE")
    ax1.set_xticks(x)
    ax1.set_xticklabels(cluster_names, rotation=30, ha="right")
    fig.legend(loc="upper right")
    fig.tight_layout()
    return fig
```

### 6.3 Stacked Bar — Occasion Mix by Cluster

```python
OCCASION_COLOURS = {
    "Immediate/GrabGo": "#E4002B",
    "StockUp": "#004B87",
    "MealAccomp": "#FFB81C",
    "Celebratory": "#6CC24A",
    "OnTheMove": "#009CDE",
    "Youth": "#FF6900",
    "Premium": "#7B2D8B",
    "Morning": "#41B6E6",
}

def plot_occasion_stack(cluster_names, occasion_matrix):
    fig, ax = plt.subplots(figsize=(10, 5))
    bottom = np.zeros(len(cluster_names))
    for occasion, colour in OCCASION_COLOURS.items():
        values = occasion_matrix.get(occasion, np.zeros(len(cluster_names)))
        ax.bar(cluster_names, values, bottom=bottom, color=colour, label=occasion)
        bottom += values
    ax.set_ylabel("Occasion Index (% share)")
    ax.legend(bbox_to_anchor=(1.05, 1), loc="upper left")
    fig.tight_layout()
    return fig
```

### 6.4 Bubble / Value-Potential Matrix

```python
def plot_value_potential(cluster_names, vpo, growth_scores, outlet_counts, colours):
    fig, ax = plt.subplots(figsize=(8, 6))
    scatter = ax.scatter(growth_scores, vpo,
                         s=[c * 0.5 for c in outlet_counts],
                         c=colours, alpha=0.7, edgecolors="white", linewidth=1.5)
    for i, name in enumerate(cluster_names):
        ax.annotate(name, (growth_scores[i], vpo[i]),
                    textcoords="offset points", xytext=(8, 4), fontsize=8)
    ax.axvline(x=np.mean(growth_scores), color="grey", linestyle="--", alpha=0.5)
    ax.axhline(y=np.mean(vpo), color="grey", linestyle="--", alpha=0.5)
    ax.set_xlabel("Growth Potential Score")
    ax.set_ylabel("Avg Monthly VPO (Rs.)")
    ax.set_title("Cluster Value × Potential Matrix")
    fig.tight_layout()
    return fig
```

### 6.5 Feature Heatmap

```python
import seaborn as sns

def plot_feature_heatmap(cluster_names, feature_names, feature_matrix):
    fig, ax = plt.subplots(figsize=(12, len(cluster_names) * 0.8 + 2))
    sns.heatmap(feature_matrix, annot=True, fmt=".2f",
                xticklabels=feature_names, yticklabels=cluster_names,
                cmap="RdBu_r", center=0, ax=ax, linewidths=0.5)
    ax.set_title("Cluster Feature Index Heatmap (z-scored)")
    fig.tight_layout()
    return fig
```

---

## §7 Cluster Naming Convention

Names must be **evocative, India-specific archetypes** combining:
`[Location/Context] + [Shopper Type] + [Behaviour/Need]`

Examples:
- *Schoolzone Youth Impulse* — GT, Youth occasion, Rs. 10 packs
- *Suburban Family Stock-up* — MT, Future Consumption, multi-pack
- *Highway Dhaba Transit* — AfH, On-the-Move, single-serve
- *Metro Premium Indulgence* — MT/AfH, Premium, high ASP
- *Festival Celebratory Bulk* — GT/MT, Celebratory, 1.25L–2L packs
- *Office Corridor On-the-Go* — GT/AfH, On-the-Move, Rs. 20 packs
- *Rural Kirana Everyday* — GT, Stock-up, Rs. 5–10 packs
- *College Canteen Social* — AfH, Youth/Social, impulse + sharing

---

## §8 Quality Standards

Before finalising any cluster summary, verify all 8 checks:

| # | Check | Requirement |
|---|---|---|
| 1 | Channel assigned | Primary channel from §2 table must be stated |
| 2 | Occasion mapped | Primary occasion from §3 table must be stated |
| 3 | SEC stated | Dominant SEC band (A/B/C/D/E) must be identified |
| 4 | All 8 dimensions scored | Radar table complete with 1–5 scores and rationale |
| 5 | Hero SKUs named | At least 3 specific SKUs cited in Action Plan |
| 6 | 6–8 actions provided | Commercial Action Plan meets minimum threshold |
| 7 | All 8 levers covered | Across 6–8 actions, all 8 commercial levers addressed |
| 8 | Data-grounded | Each inference cites a specific feature value or index |

---

## §9 Example Output

### CLUSTER 3 — Schoolzone Youth Impulse

```
CLUSTER 3 — Schoolzone Youth Impulse
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Cluster ID        : 3
Primary Channel   : GT (General Trade)
Primary Occasion  : Youth / Youngsters
Outlet Count      : 1,240 stores (18% of universe)
Avg Monthly VPO   : Rs. 12,400
Growth Potential  : High
SEC Profile       : C/D dominant
```

**Shopper Profile**
These outlets serve predominantly 15–24-year-old students making after-school and between-class impulse purchases. The core need state is affordable refreshment and snacking, driven by social peer influence rather than planned need. Purchases are almost exclusively single-serve packs priced at Rs. 10–20, consumed immediately on or near the store. Weekend volumes spike with group purchases as students gather near school and college gates. Low brand loyalty but high category frequency makes this a high-volume acquisition opportunity.

**Demographic & Catchment Profile**
The catchment is dominated by SEC C/D households in Tier-2 and Tier-3 cities, with dense school and college POI within a 500m radius. Residential density is high but income levels are constrained, making Rs. 10 the critical price ceiling. Nearby food-service POIs (tiffin centres, small canteens) confirm a youth-oriented footfall environment. Seasonal peaks occur in April–June (exam pressure + summer) and October (post-festival return to school).

**Store Characteristics**
Stores are predominantly small-format general trade kiranas with monthly VPO of Rs. 10,000–14,000, placing them in the mid-revenue tier. SKU depth is narrow (avg 8–10 beverage SKUs), with strong reliance on Rs. 10 and Rs. 20 price-pack architecture. Chiller presence is low (28% of outlets) but is the single highest driver of IC uplift in this cluster. Secondary display compliance is minimal — most outlets use counter-top placement only.

**Sales Behaviour Dimensions**

| Dimension | Score | Rationale |
|---|---|---|
| Beverage Category Depth | 2 | Narrow range, 8–10 SKUs vs 14 universe avg |
| Immediate Consumption Mix | 5 | 78% IC volume, well above 52% universe avg |
| Seasonal Demand Spike | 3 | Moderate summer spike; back-to-school uptick |
| Premium Mix | 1 | < 5% high-ASP SKU share |
| Low Price-Pack Dependency | 5 | 61% of volume from Rs. 5–20 packs |
| Footfall Intensity | 4 | 1.4x universe footfall index |
| Loyalty / Repeat Purchase | 3 | Moderate frequency; impulse-driven not habitual |
| Execution Quality | 2 | Low planogram compliance; limited chiller |

```
[RADAR CHART]
Axes: Beverage Depth, IC Mix, Seasonal Spike, Premium Mix,
      Low Price-Pack, Footfall, Loyalty, Execution
Scores: [2, 5, 3, 1, 5, 4, 3, 2]
Cluster colour: #E4002B
Universe avg: [3, 3, 3, 3, 3, 3, 3, 3] grey dashed
```

**Comparative Cluster Snapshot**

| Cluster | Name | Count | Avg VPO (Rs.) | IC Mix | Premium Mix | Growth Potential |
|---|---|---|---|---|---|---|
| 1 | Suburban Family Stock-up | 980 | 28,500 | 31% | 22% | Medium |
| 2 | Metro Premium Indulgence | 420 | 45,200 | 44% | 58% | Medium |
| **3** | **Schoolzone Youth Impulse** | **1,240** | **12,400** | **78%** | **5%** | **High** |
| 4 | Highway Dhaba Transit | 670 | 18,900 | 69% | 8% | High |
| 5 | Rural Kirana Everyday | 2,100 | 8,700 | 48% | 2% | Medium |

**Commercial Action Plan**

```
ACTION 1: HERO SKU DISTRIBUTION
Initiative : Rs. 10 Must-Stock 5-SKU Pack
Objective  : Achieve 90% numeric distribution of must-stock SKUs across the 5-SKU shortlist
Hero SKUs  : [Bev A 200ml], [Bev B 200ml], [Bev C 200ml], [Snack A 26g], [Snack B 26g]
Channel    : GT
Timeline   : Immediate (0–4 weeks)
KPI        : Numeric distribution % of 5-SKU must-stock list

ACTION 2: MERCH & SPACE
Initiative : Counter-Top Display Unit (CDU) Placement Drive
Objective  : Double visible SKU count at point of purchase from avg 4 to 8 facings
Hero SKUs  : [Bev Brand A 200ml], [Bev Brand B 200ml], [Bev Brand C 200ml]
Channel    : GT
Timeline   : Immediate (0–4 weeks)
KPI        : CDU placement rate (% of cluster outlets with CDU)

ACTION 3: PORTFOLIO
Initiative : Introduce Rs. 20 Combo Pack (Beverage + Snack)
Objective  : Increase average basket from Rs. 12 to Rs. 20 without premium barrier
Hero SKUs  : [Bev A 250ml + Snack A 14g combo], [Bev B 250ml + Snack B 14g combo]
Channel    : GT
Timeline   : Short (1–3 months)
KPI        : Combo attachment rate; avg transaction value

ACTION 4: OCCASION ACTIVATION
Initiative : Back-to-School Summer Refresh Campaign
Objective  : Capture seasonal June–July peak with in-school-zone POSM and activation
Hero SKUs  : [Brand A 200ml], [Brand B 200ml], [Brand C Flavoured 200ml]
Channel    : GT
Timeline   : Short (1–3 months — April/May launch)
KPI        : Cluster volume uplift vs prior year June–July

ACTION 5: CHILLER / PICTURE OF SUCCESS
Initiative : Chiller Seeding Programme for High-Footfall Outlets
Objective  : Increase chiller penetration from 28% to 50% in top-200 outlet quartile
Hero SKUs  : All IC formats; priority top-selling chilled beverages
Channel    : GT
Timeline   : Medium (3–6 months)
KPI        : Chiller penetration %; IC volume uplift in chiller-seeded outlets

ACTION 6: DEMOGRAPHIC TARGETING
Initiative : "Padhte Raho, Peete Raho" School-Zone Loyalty Card
Objective  : Drive repeat purchase among 15–24 cohort via scratch-card mechanic
Hero SKUs  : Any Rs. 10 or Rs. 20 beverage SKU
Channel    : GT
Timeline   : Short (1–3 months)
KPI        : Redemption rate; repeat purchase frequency delta

ACTION 7: PRICING & PROMO
Initiative : Rs. 5 Entry-Pack Re-introduction at Cluster Outlets
Objective  : Capture SEC D/E trial and grow penetration among lowest-income segment
Hero SKUs  : [Entry-pack Bev 150ml/100ml], [Entry-pack Snack 10g]
Channel    : GT
Timeline   : Immediate (0–4 weeks)
KPI        : New buyer trial rate; Rs. 5 pack numeric distribution

ACTION 8: CHANNEL PARTNERSHIP
Initiative : Kirana Retailer Engagement — "School Zone Star" Trade Programme
Objective  : Incentivise top 300 GT outlets on compliance and range targets
Hero SKUs  : Full must-stock SKU list
Channel    : GT
Timeline   : Medium (3–6 months)
KPI        : Trade programme enrolment %; compliance score improvement
```

---

## §10 Integration Instructions for `segmentation_agent.py`

### 10.1 Load Guidelines in Prompt

At the top of `generate_segment_summary()`, load and inject the guidelines path:

```python
import os

GUIDELINES_PATH = os.path.join(os.path.dirname(__file__), "..", "CLUSTER_INFERENCE_GUIDELINES.md")

def _load_guidelines() -> str:
    try:
        with open(GUIDELINES_PATH, "r") as f:
            return f.read()
    except FileNotFoundError:
        return ""
```

### 10.2 Expanded RICH_SECTIONS

```python
RICH_SECTIONS = [
    "identity_card",
    "shopper_profile",
    "demographic_catchment",
    "store_characteristics",
    "dimensions_radar",
    "comparative_snapshot",
    "commercial_action_plan",
]
```

### 10.3 Updated Prompt Template

```python
SUMMARY_PROMPT = """
You are a senior CPG Category & Shopper Insights Manager for India.
You are generating a cluster summary for an internal Perfect Store segmentation report.

GUIDELINES: Follow the framework in CLUSTER_INFERENCE_GUIDELINES.md exactly.
You MUST produce all 7 sections in the exact structure defined in §5 of the guidelines.
Apply the channel taxonomy (§2), occasion framework (§3), demographic dimensions (§4),
radar scoring (§5 Section 5), comparative table (§5 Section 6), and commercial levers (§5 Section 7).
Verify your output against the 8 quality checks in §8 before responding.

---
CLUSTER DATA:
{cluster_data}

UNIVERSE AVERAGES:
{universe_averages}

ALL CLUSTER SUMMARIES (for comparative table):
{all_cluster_summaries}
---

Respond with a JSON object with exactly these keys:
"identity_card", "shopper_profile", "demographic_catchment",
"store_characteristics", "dimensions_radar", "comparative_snapshot",
"commercial_action_plan"

Each value is a markdown-formatted string for that section.
"""
```

---

## §11 Chart Generation Reference for `output_agent.py`

Add the following chart calls after existing VPO bar chart in the Excel workbook:

1. **Radar charts** — one per cluster, inserted as images in the "Rich Summaries" sheet
2. **Cluster bar chart** — VPO + outlet count comparison, "Cluster Overview" sheet
3. **Occasion stacked bar** — occasion index by cluster, "Shopper Occasions" sheet
4. **Value × Potential bubble** — growth score vs VPO, "Quadrant Analysis" sheet
5. **Feature heatmap** — z-scored feature matrix, "Feature Heatmap" sheet

Use the Python functions defined in §6 of these guidelines.
Save each chart as a `.png` in the `outputs/charts/` directory before inserting into Excel/PDF.
