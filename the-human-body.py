# Shebang statement tells system to execute in Python
#!/usr/bin/env python


"""
File: the-human-body.py
Author: Stefanie Moreno
Date: Dec 23, 2025
Description: The following script is a highly inclusive account for the total input
and output of the human body measured per day.
"""

# Import packages/modules
import math

# 1. Cell Compartment Class
class CellCompartment:
    """
    Represents a population of cells (human or microbial) with
    a daily turnover fraction and growth bias.
    """
    def __init__(
            self, name, initial_cells,
            turnover_fraction,
            growth_bias=0.0,
            kind="human"
    ):

        self.name = name
        self.cells = initial_cells
        self.turnover = turnover_fraction
        self.growth_bias = growth_bias
        self.kind = kind

        # Tracking
        self.dead_today = 0.0
        self.born_today = 0.0

    def step(self, dt=1.0):
        # Cells that die today
        dying = self.cells * self.turnover * dt

        # Cells born today (steady-state + optional growth)
        born = dying * (1.0 + self.growth_bias)

        # Update population
        self.cells += (born - dying)

        # Log
        self.dead_today = dying
        self.born_today = born


# 2. Model Parameters
class ModelParameters:
    def __init__(self):
        # Energy
        self.bmr_kcal = 1500
        self.activity_factor = 1.3
        self.co2_g_per_kcal = 0.20

        # Water
        self.urine_l = 1.5
        self.sweat_l = 0.5
        self.insensible_l = 0.4

        # Solid waste
        self.base_feces_g = 150.0

        # Approx mass per cell (very rough)
        self.mass_per_cell_g = 1e-12 * 1000  # convert to grams


# 3. Body State
class BodyState:
    def __init__(self, mass_kg=70.0):
        self.total_mass_kg = mass_kg
        self.fat_mass_kg = 15.0
        self.lean_mass_kg = mass_kg - self.fat_mass_kg
        self.total_water_l = 42.0

        # Energy buffer
        self.energy_kcal = 2000.0

        # Daily logs
        self.inputs = {"food_kcal": 0.0, "water_l": 0.0}
        self.outputs = {
            "co2_g": 0.0,
            "urine_l": 0.0,
            "sweat_l": 0.0,
            "feces_g": 0.0,
            "dead_human_cells": 0.0,
            "dead_microbial_cells": 0.0
        }

        # Cell compartments
        self.compartments = []

    def add_compartment(self, comp):
        self.compartments.append(comp)

    @property
    def total_human_cells(self):
        return sum(c.cells for c in self.compartments if c.kind == "human")

    @property
    def total_microbes(self):
        return sum(c.cells for c in self.compartments if c.kind == "microbial")


# 4. Daily Simulation Step
def step_day(body, params, food_kcal, water_l, dt=1.0):

    # Reset logs
    body.inputs["food_kcal"] = food_kcal
    body.inputs["water_l"] = water_l
    for k in body.outputs:
        body.outputs[k] = 0.0

    # Energy balance
    daily_need = params.bmr_kcal * params.activity_factor * dt
    body.energy_kcal += food_kcal

    used = min(body.energy_kcal, daily_need)
    body.energy_kcal -= used

    # If deficit, burn fat
    if used < daily_need:
        deficit = daily_need - used
        fat_loss = deficit / 7700.0
        body.fat_mass_kg = max(0.0, body.fat_mass_kg - fat_loss)
        body.total_mass_kg -= fat_loss

    # CO2 output
    body.outputs["co2_g"] = used * params.co2_g_per_kcal

    # Water balance
    water_out = (params.urine_l + params.sweat_l + params.insensible_l) * dt
    body.total_water_l += (water_l - water_out)

    body.outputs["urine_l"] = params.urine_l * dt
    body.outputs["sweat_l"] = params.sweat_l * dt

    # Cell turnover
    dead_human = 0.0
    dead_microbes = 0.0

    for comp in body.compartments:
        comp.step(dt)
        if comp.kind == "human":
            dead_human += comp.dead_today
        else:
            dead_microbes += comp.dead_today

    body.outputs["dead_human_cells"] = dead_human
    body.outputs["dead_microbial_cells"] = dead_microbes


    # Solid waste (feces)
    dead_mass_g = (dead_human + dead_microbes) * params.mass_per_cell_g
    feces_g = params.base_feces_g * dt + dead_mass_g
    body.outputs["feces_g"] = feces_g

    # Mass loss from feces
    body.total_mass_kg -= feces_g / 1000.0


# 5. Run Simulation
def run_sim(days=30):
    params = ModelParameters()
    body = BodyState()

    # Add compartments
    body.add_compartment(CellCompartment("gut_epithelium", 1e11, 0.20, kind="human"))
    body.add_compartment(CellCompartment("skin_epithelium", 1e11, 0.03, kind="human"))
    body.add_compartment(CellCompartment("rbc", 2e13, 1/120, kind="human"))
    body.add_compartment(CellCompartment("gut_microbiome", 3e13, 0.30, kind="microbial"))
    body.add_compartment(CellCompartment("systemic_microbiome", 1e9, 0.30, kind="microbial"))

    history = []

    for day in range(days):
        step_day(body, params, food_kcal=2200, water_l=2.0)

        history.append({
            "day": day,
            "mass_kg": body.total_mass_kg,
            "water_l": body.total_water_l,
            "human_cells": body.total_human_cells,
            "microbes": body.total_microbes,
            "co2_g": body.outputs["co2_g"],
            "feces_g": body.outputs["feces_g"],
            "dead_human_cells": body.outputs["dead_human_cells"],
            "dead_microbes": body.outputs["dead_microbial_cells"]
        })

    return history


# 6. Example Usage
if __name__ == "__main__":
    data = run_sim(10)
    for day in data:
        print(day)

