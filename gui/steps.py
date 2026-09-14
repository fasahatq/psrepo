"""Mapping between the 7 pipeline steps and the 5 Perfect Store wheel wedges.

Pipeline step numbers come straight from pipeline.run_pipeline's progress_callback
(``Step N/7`` in the logs). Step 0 is the "init" event, step 8 is "complete".
"""

# step_no -> short label shown in the checklist
STEP_META = {
    1: "Load data",
    2: "Data quality checks",
    3: "Prioritization  (A / B / C / D + opportunity gap)",
    4: "Segmentation",
    5: "MSL generation  (must-stock list)",
    6: "Space allocation  (planogram)",
    7: "Outputs and Inferences  (segment CSVs, Excel, PDF, deck)",
}
STEP_ORDER = [1, 2, 3, 4, 5, 6, 7]

# The 5 wedges, clockwise starting from the top-right of the wheel, matching the
# Perfect Store framework diagram.
WEDGES = [
    {
        "key": "seg",
        "title": "Segmentation & Prioritization",
        "band": "WHERE TO PLAY",
        "color": "#1E7BA5",   # deep sky blue
        "steps": [1, 2, 3, 4],
    },
    {
        "key": "shopper",
        "title": "Shopper Value Offer",
        "band": "HOW TO WIN",
        "color": "#3F8A2E",   # deep green
        "steps": [5],
    },
    {
        "key": "retail",
        "title": "Retail Value Offer",
        "band": "HOW TO WIN",
        "color": "#134E7E",   # deep navy blue
        "steps": [6],
    },
    {
        "key": "pos",
        "title": "Picture of Success",
        "band": "HOW TO EXECUTE",
        "color": "#C67F0A",   # deep amber
        "steps": [7],
    },
    {
        "key": "track",
        "title": "Execution & Tracking",
        "band": "HOW TO EXECUTE",
        "color": "#7C1A6B",   # deep magenta
        "steps": [],           # completes when the whole run finishes
    },
]
