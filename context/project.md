# Perfect Store – End-to-End Context for LLM-Driven Execution

---

## 1. What is Perfect Store (PS)?

Perfect Store is a **core CPG execution framework** used to translate commercial strategy into
store-level actions that win with shoppers and deliver sustainable revenue and margin growth.
It defines, measures, and continuously improves what *"good looks like"* in-store across channels,
formats, and markets.

At scale, Perfect Store enables **consistent yet locally relevant execution** across millions of
outlets by combining analytics, GTM routines, and disciplined measurement.

At its core, Perfect Store answers three questions:

1. **Which stores matter most?** (Segmentation)
2. **What should happen in those stores?** (MSL, Price-Pack, Promotion, Visibility)
3. **Are we executing well, and is it delivering value?** (Scorecards, KPIs, Value Realization)

This project covers the **end-to-end Perfect Store lifecycle**, from segmentation to activation and
measurement, aligned to the manufacturer's commercial operating model.

---

## 2. Commercial Intent Behind Perfect Store

Perfect Store is not an analytics exercise — it is a **commercial execution engine** embedded into
the manufacturer's Go-To-Market model.

The commercial intent is to:
- Maximize **Net Revenue, NSV, and Margin** by prioritizing the right stores and shopper missions
- Improve **availability, visibility, and affordability** of the right SKUs
- Enable **price-pack architecture discipline** to balance penetration and margin
- Focus GTM effort where manufacturer brands have the **highest incremental upside**
- Replace intuition-led execution with **scalable, data-backed standards**

Perfect Store explicitly links store-level execution to the manufacturer's growth levers:
- Revenue growth (distribution, conversion, premiumization)
- Margin protection (price ladders, pack roles, promo efficiency)
- Productivity (focused call universe, differentiated execution)

**Objective**: Define differentiated execution standards by store segment and mission, and ensure
disciplined activation that maximizes shopper value and commercial returns for the manufacturer.

This is achieved by:
- Segmenting stores based on shopper demand, opportunity, and execution feasibility
- Designing segment-specific execution playbooks
- Embedding outputs into GTM routines and digital tools
- Closing the loop with measured commercial impact

---

## 3. End-to-End Perfect Store Operating Model

The Perfect Store workflow consists of six tightly connected steps. Each step feeds into the next
and must remain **commercially consistent** across brands, categories, and markets.

### Step 1 — Store Segmentation (Foundation Layer)
**Purpose**: Determine where the manufacturer should deploy different execution intensity and
assortment complexity.

Key principles:
- Data-led, scalable, and repeatable across markets
- Based on **observed demand patterns**, not only store size
- Designed to be **simple enough for GTM execution**

Typical inputs: store-level sales and volume, price-point/pack-size/flavor behavior, channel,
geography, demand proxies, store productivity and feasibility signals.

Output: mutually exclusive, collectively exhaustive segments; clear prioritization (e.g., Core /
Growth / Tactical); anchor for all downstream Perfect Store decisions.

### Step 2 — Shopper & Mission Context
Perfect Store is **shopper-backward**.

Stores serve different missions (immediate consumption, routine top-up, stock-up, etc.). Missions
drive: assortment depth, entry price sensitivity, pack-size relevance, and role of promotions.

Execution standards must reflect **how shoppers actually buy products in that store**, not universal
brand rules.

### Step 3 — Must-Stock List (MSL)
MSL defines the **minimum assortment that must be present** in a store to satisfy shopper demand
and protect category share.

MSL design principles:
- Segment-specific
- Anchored in demand and SKU productivity
- Biased toward availability and simplicity

Inputs: segment-level demand, SKU contribution, pack and flavor relevance, space and route feasibility.
Output: clear SKU list per segment; direct inputs to sales and distributor execution.

### Step 4 — Shopper Value Offer (SVO) & Price-Pack Architecture
**Purpose**: Ensure the manufacturer delivers the right value proposition at the shelf, balancing
affordability and margin.

SVO covers: entry price points, value vs. premium packs, trade-up pathways, mission-based
affordability.

Key principles:
- Segment × mission specific
- Clear pack roles to avoid cannibalization
- Reduced reliance on sub-optimal discounting

### Step 5 — Activation & GTM Enablement
Perfect Store creates value only when embedded in **sales routines and GTM tools**.

Activation includes: converting analytics into simple store rules; integration into Salesforce
routines, distributor priorities, and digital selling tools.

**Key Principle: Complexity in analytics, simplicity at execution.**

### Step 6 — Measurement, Scorecards & Value Realization

Execution measurement: MSL availability, price-pack adherence, visibility compliance.

Commercial measurement: incremental NSV, distribution expansion, uplift vs. control, ROI by segment.

Closed loop: measurement outputs continuously refine segmentation, MSL, and SVO.

---

## 4. Inputs & Outputs by Step

```json
{
  "Store Segmentation": {
    "inputs": ["store_sales", "price_pack_behavior", "channel", "demand_proxies"],
    "outputs": ["store_segment", "priority_level"]
  },
  "Shopper & Mission": {
    "inputs": ["segment", "shopping_patterns", "occasion_proxies"],
    "outputs": ["mission_type", "mission_weight"]
  },
  "MSL": {
    "inputs": ["segment", "mission", "sku_sales", "space_constraints"],
    "outputs": ["msl_sku_list"]
  },
  "SVO & Price-Pack": {
    "inputs": ["segment", "mission", "price_ladders", "margin_targets"],
    "outputs": ["recommended_price_pack", "pack_roles"]
  },
  "Activation": {
    "inputs": ["segment", "msl", "svo"],
    "outputs": ["store_execution_rules"]
  },
  "Measurement": {
    "inputs": ["execution_data", "sales_outcomes"],
    "outputs": ["uplift", "roi", "refinement_actions"]
  }
}
```

---

## 5. Brand & Portfolio

**Beverage portfolio**: Carbonated soft drinks, juices, water, sports drinks, energy drinks,
enhanced water — configure specific brand names per deployment.

**Snacks portfolio**: Salty snacks, extruded snacks, baked snacks, breakfast/oats — configure
specific brand names per deployment.

**Price-pack architecture (India)**:
- ₹5 / ₹10 — impulse, entry, high-frequency GT packs
- ₹20 / ₹30 — mid-tier, convenience
- ₹40–60 — modern trade, premium single-serve
- ₹90+ — large format, multi-serve, premium

**PPG (Price-Pack-Group) labels used in data**: Small, Medium, Large, Extra Large, Insti Large, Insti Mids

---

## 6. Trade Channel Definitions

| Code | Full Name | Store Types |
|---|---|---|
| GT | General Trade | Kirana, pan shops, local grocers, neighbourhood stores |
| MT | Modern Trade | Supermarkets, hypermarkets, cash & carry, convenience chains |
| AfH | Away from Home | Dhabas, QSR, canteens, hotels, transit food courts |
| EC | E-Commerce | Online grocery, quick commerce (Blinkit, Zepto, Swiggy Instamart) |

---

## 7. Key Metrics & Terminology

- **VPO** — Value Per Outlet (monthly net revenue from a store, in local currency)
- **AVG_SKU** — Average number of distinct SKUs stocked per store per month
- **ACTIVE_MONTHS** — Number of months a store has been actively transacting
- **TOTAL_REVENUE** — Cumulative lifetime revenue of the store
- **BI** — Business Index (store's revenue relative to category average)
- **SEC** — Socioeconomic Classification of the store's neighbourhood households (A/B/C/D/E)
- **Priority bucket** — A/B/C/D tier assigned by VPO percentile rank:
  - A = top 20% (high performers)
  - B = next 20% (good performers)
  - C = next 30% (mid performers)
  - D = bottom 30% (low performers)
- **Opportunity gap** — Difference between a store's predicted 75th-percentile potential VPO and its actual VPO; positive gap = underperforming store
- **NSV** — Net Sales Value (revenue net of trade discounts and returns)
- **MSL** — Minimum Stocking List: the core SKUs a store in a given segment must carry
- **SVO** — Shopper Value Offer: store-level value proposition across price and packs
- **POSM** — Point-of-Sale Material
- **MBD** — Merchandising and Brand Display

---

## 8. Geographic & Demographic Context

- **Urbanicity tiers**: Metro (e.g. Mumbai, Delhi, Bengaluru, Hyderabad, Chennai, Kolkata) → Tier-1 → Tier-2/3 → Rural
- **SEC households** per neighbourhood: sec_a_hhs through sec_e_hhs (higher = wealthier catchment)
- **POI proximity columns**: distance_to_nearest_school_in_km, distance_to_nearest_large_office_in_km, distance_to_nearest_malls, distance_to_nearest_bus_stn_in_km, distance_to_nearest_train_stn_in_km

---

## 9. Perfect Store Glossary

- **Perfect Store (PS)**: CPG execution framework to define and measure ideal in-store execution
- **Segmentation**: Grouping of stores with similar demand and opportunity profiles
- **MSL (Must-Stock List)**: Minimum SKUs required in a store
- **SVO (Shopper Value Offer)**: Store-level value proposition across price and packs
- **Price-Pack Architecture**: Structured ladder of packs and prices with defined roles
- **Mission**: Shopper intent driving purchase behavior in a store
- **Activation**: Translation of analytics into GTM execution
- **Scorecard**: Measurement of execution compliance and outcomes
- **Value Realization**: Quantified commercial impact from Perfect Store
- **GTM**: Go-To-Market (the field sales and distribution system)
- **NSV**: Net Sales Value — revenue net of trade discounts
- **VPO**: Value Per Outlet — monthly net revenue per store

---

## 10. Role of LLM / AI in This Project

This context is intended to ground the LLM so it:
- Understands Perfect Store as an **end-to-end CPG commercial system**
- Respects dependencies across steps (segmentation → MSL → SVO → activation → measurement)
- Generates outputs that are **segment-aware, shopper-centric, and executable**

The LLM should treat Perfect Store as a **decision framework**, not isolated models. Every output
must be commercially grounded — tied to a specific growth lever (revenue, margin, or productivity)
and executable by a field sales team.

---

## 11. Output Standards

All LLM-generated text in this pipeline appears in:
1. Executive PDF reports reviewed by leadership
2. Field team Excel workbooks used by sales representatives
3. Segment narrative slides for trade marketing

Language must be **professional, specific, and commercially actionable**. Use CPG/FMCG trade
terminology throughout. Avoid generic statements — every insight must be grounded in the data
features provided and tied to a specific commercial lever.

---

## 12. Success Definition

Perfect Store is successful when:
- GTM teams know **where to focus and what to do**
- Shoppers receive the **right products and value**
- Commercial teams can **quantify ROI**
- The system scales across markets
