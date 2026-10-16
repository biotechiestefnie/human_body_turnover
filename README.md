

This program is a structured, extensible model in Python that depicts
the following equation for the human body:
    state(t + dt) = state(t) + inputs - outputs + internal changes

1.1 It includes:
    * A BodyState class
    * A CellCompartment class
    * A ModelParameters class
    * A daily simulation step
    * A multi‑day simulation loop
    * Logging of mass, water, CO₂, feces, and cell turnover

And accounts for:
2.1 Human compartments (for cells + mass):
    * Skin 
    * Gut epithelium
    * Blood (RBCs, WBCs as a lump)
    * “Stable” tissues (brain, etc.)
2.2 Microbial compartments:
    * Gut microbiome
    * Skin microbiome
    * Systemic/low‑abundance microbiome (blood/brain/etc. lumped)
2.3 Global state variables:
    * Total body mass
    * Total body water
    * Energy balance
2.4 Daily I/O: 
    * food 
    * water 
    * CO₂
    * O2
    * urine 
    * excrement 
    * sweat 
    * dead cells shed

All will be simulated in daily timesteps to ensure manageability.

Core Data Structures:
3.1. Cell compartments:
Each cell compartment (human or microbial) can be represented with:
    * Current cell count
    * Daily turnover fraction (fraction of cells that die each day)
    * Optional growth bias (for microbes)
```
class CellCompartment:
    def __init__(self, name, initial_cells, daily_turnover_fraction, growth_bias=0.0, kind="human"):
        """
        name: str, e.g. "gut_epithelium", "gut_microbiome"
        initial_cells: float, number of cells
        daily_turnover_fraction: 0–1, fraction of cells dying per day
        growth_bias: net growth per day (for microbes, e.g. 0.01 = +1%/day at steady intake)
        kind: "human" or "microbial"
        """
        self.name = name
        self.cells = initial_cells
        self.turnover = daily_turnover_fraction
        self.growth_bias = growth_bias
        self.kind = kind

        # tracking
        self.dead_today = 0.0
        self.born_today = 0.0

    def step(self, dt_days=1.0):
        # cells that die this timestep
        dying = self.cells * self.turnover * dt_days

        # by default, assume replacement maintains near steady-state
        born = dying * (1.0 + self.growth_bias)

        self.cells += (born - dying)

        self.dead_today = dying
        self.born_today = born

```

Instantiating things like:
```
gut_epithelium = CellCompartment(
    name="gut_epithelium",
    initial_cells=1e11,
    daily_turnover_fraction=0.20,  # ~20%/day
    kind="human"
)

skin_epithelium = CellCompartment(
    name="skin_epithelium",
    initial_cells=1e11,
    daily_turnover_fraction=0.01,
    kind="human"
)

rbc_compartment = CellCompartment(
    name="rbc",
    initial_cells=2e13,
    daily_turnover_fraction=1/120,
    kind="human"
)

gut_microbiome = CellCompartment(
    name="gut_microbiome",
    initial_cells=3e13,
    daily_turnover_fraction=0.30,   # very dynamic
    growth_bias=0.0,
    kind="microbial"
)

systemic_microbiome = CellCompartment(
    name="systemic_microbiome",
    initial_cells=1e9,              # much smaller, very rough
    daily_turnover_fraction=0.30,
    kind="microbial"
)

```

Whole body state and parameters: 
```
class ModelParameters:
    def __init__(self):
        # Energy
        self.bmr_kcal_per_day = 1500
        self.activity_factor = 1.3
        self.co2_g_per_kcal = 0.20  # rough

        # Water
        self.urine_l_per_day = 1.5
        self.sweat_l_per_day = 0.5
        self.insensible_l_per_day = 0.4  # breath + skin evap

        # Solid waste baseline (non‑cell / diet‑dependent)
        self.base_fecal_mass_g_per_day = 150.0

        # Mapping dead cells to waste mass (extremely approximate)
        self.mass_per_cell_g = 1e-12  # order‑of‑magnitude

```

Body State: 
```
class BodyState:
    def __init__(self, initial_mass_kg=70.0):
        self.total_mass_kg = initial_mass_kg
        self.fat_mass_kg = 15.0
        self.lean_mass_kg = initial_mass_kg - self.fat_mass_kg
        self.total_body_water_l = 42.0

        # Energy buffer (simplified “available kcal”)
        self.energy_kcal = 2000.0

        # Daily I/O logs
        self.inputs = {"food_kcal": 0.0, "water_l": 0.0}
        self.outputs = {
            "co2_g": 0.0,
            "urine_l": 0.0,
            "sweat_l": 0.0,
            "feces_g": 0.0,
            "dead_human_cells": 0.0,
            "dead_microbial_cells": 0.0
        }

        # Compartments
        self.compartments = []

    def add_compartment(self, comp: CellCompartment):
        self.compartments.append(comp)

    @property
    def total_human_cells(self):
        return sum(c.cells for c in self.compartments if c.kind == "human")

    @property
    def total_microbial_cells(self):
        return sum(c.cells for c in self.compartments if c.kind == "microbial")

```

Main Function:
One step_day function that: 
    * Applies inputs (food, water).
    * Computes energy use and CO₂ production.
    * Updates water balance.
    * Steps each cell compartment and tallies dead cells.
    * Updates waste (feces includes dead cells + baseline).
    * Adjusts mass roughly where needed.

```
def step_day(body: BodyState, params: ModelParameters, food_kcal, water_l, dt_days=1.0):
    # Reset daily logs
    body.inputs["food_kcal"] = food_kcal
    body.inputs["water_l"] = water_l
    for k in body.outputs:
        body.outputs[k] = 0.0

    # 1. Energy balance
    daily_need = params.bmr_kcal_per_day * params.activity_factor * dt_days
    body.energy_kcal += food_kcal

    # energy used today
    used = min(body.energy_kcal, daily_need)
    body.energy_kcal -= used

    # If deficit, pull from fat mass (very rough: 1 kg fat ~ 7700 kcal)
    if used < daily_need:
        deficit = daily_need - used
        fat_loss_kg = deficit / 7700.0
        body.fat_mass_kg = max(0.0, body.fat_mass_kg - fat_loss_kg)
        body.total_mass_kg -= fat_loss_kg

    # CO2 output
    co2_g = used * params.co2_g_per_kcal
    body.outputs["co2_g"] = co2_g

    # 2. Water balance
    water_in = water_l
    water_out = (
        params.urine_l_per_day +
        params.sweat_l_per_day +
        params.insensible_l_per_day
    ) * dt_days

    body.total_body_water_l += (water_in - water_out)
    body.outputs["urine_l"] = params.urine_l_per_day * dt_days
    body.outputs["sweat_l"] = params.sweat_l_per_day * dt_days

    # 3. Cell turnover
    total_dead_human = 0.0
    total_dead_microbes = 0.0

    for comp in body.compartments:
        comp.step(dt_days=dt_days)
        if comp.kind == "human":
            total_dead_human += comp.dead_today
        else:
            total_dead_microbes += comp.dead_today

    body.outputs["dead_human_cells"] = total_dead_human
    body.outputs["dead_microbial_cells"] = total_dead_microbes

    # 4. Solid waste (feces): baseline + dead cells converted to mass
    dead_cells_mass_g = (total_dead_human + total_dead_microbes) * params.mass_per_cell_g * 1e3  # to g
    feces_g = params.base_fecal_mass_g_per_day * dt_days + dead_cells_mass_g
    body.outputs["feces_g"] = feces_g

    # Very rough: losing fecal mass reduces total mass
    body.total_mass_kg -= feces_g / 1000.0

```

This allows it to be run on a multi-day simulation:

```
def run_simulation(days=30):
    params = ModelParameters()
    body = BodyState(initial_mass_kg=70.0)

    # Add compartments
    body.add_compartment(gut_epithelium)
    body.add_compartment(skin_epithelium)
    body.add_compartment(rbc_compartment)
    body.add_compartment(gut_microbiome)
    body.add_compartment(systemic_microbiome)

    history = []

    for day in range(days):
        # Example: fixed diet; you could vary this per day
        food_kcal = 2200
        water_l = 2.0

        step_day(body, params, food_kcal, water_l, dt_days=1.0)

        history.append({
            "day": day,
            "mass_kg": body.total_mass_kg,
            "water_l": body.total_body_water_l,
            "total_human_cells": body.total_human_cells,
            "total_microbial_cells": body.total_microbial_cells,
            "co2_g": body.outputs["co2_g"],
            "feces_g": body.outputs["feces_g"],
            "dead_human_cells": body.outputs["dead_human_cells"],
            "dead_microbial_cells": body.outputs["dead_microbial_cells"]
        })

    return history

```

And can then visualize:
    * Total human vs microbial cells over time
    * Daily dead cells (turnover) per compartment
    * Daily CO₂, feces, water loss
    * Weight changes with different diets or activity factors

Once this skeleton is in place, we can iteratively:
    * Refine turnover rates and compartment sizes
    * Include O₂ intake explicitly via respiratory equations
    * Add stochasticity (random variation around means)
    * Add events (fasting, illness, intense exercise) and watch how cell turnover and I/O change
    * Document assumptions like a mini‑paper

Important Rates to Keep in Mind:

Compartment	Daily   |    Turnover Fraction
---------------------------------------------------------
Gut epithelium	    |       0.20–0.33
Stomach epithelium  |       0.11–0.50
Colon epithelium    |	    0.12–0.25
Skin epithelium	    |       0.025–0.035
RBCs	            |       0.008
Neutrophils	        |       0.20–1.00
Lymphocytes	        |       0.001–0.01
Monocytes	        |       1.00
Platelets	        |       0.10–0.12
Hepatocytes	        |       0.003–0.005
Adipocytes	        |       0.0003
Skeletal muscle	    |       0.0001
Osteoclasts	        |       0.07
Osteoblasts	        |       0.01
Osteocytes	        |       ~0
Gut microbiome	    |       0.20–0.60
Skin microbiome	    |       0.10–0.30
Systemic microbiome |	    0.20–0.30 (modeling assumption)

For each kcal of energy used, the body consumes about 
0.2 liters of O₂ and produces about 0.2 liters of CO₂ (this is tied to respiratory 
quotient and substrate mix.
energy(exp) <-> O2(consumed) <-> CO2(expelled)
