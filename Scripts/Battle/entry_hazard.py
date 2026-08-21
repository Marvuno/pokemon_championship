import math
from Scripts.Battle.type_chart import *
from Scripts.Battle.constants import has_ability


def entry_hazard_effect(switch_side, pokemon):
    stealth_rock_entry_hazard(switch_side, pokemon)
    spikes_entry_hazard(switch_side, pokemon)
    toxic_spikes_entry_hazard(switch_side, pokemon)
    sticky_web_entry_hazard(switch_side, pokemon)


def stealth_rock_entry_hazard(switch_side, pokemon):
    type_effectiveness = math.prod([typeChart["Rock"][x] for x in pokemon.type])
    pokemon.battle_stats[0] -= math.floor(pokemon.hp * 0.125 * type_effectiveness * switch_side.entry_hazard["Stealth Rock"])


def spikes_entry_hazard(switch_side, pokemon):
    # ungrounded pokemon unaffected
    if pokemon.volatile_status['Grounded'] == 1:
        spikes_damage = {0: 0, 1: 1 / 8, 2: 1 / 6, 3: 1 / 4}  # fraction
        pokemon.battle_stats[0] -= math.floor(pokemon.hp * spikes_damage[switch_side.entry_hazard["Spikes"]])


def toxic_spikes_entry_hazard(switch_side, pokemon):
    # ungrounded pokemon unaffected
    if pokemon.volatile_status['Grounded'] == 1:
        if "Poison" not in pokemon.type and "Steel" not in pokemon.type:
            toxic_spikes_effect = {0: "Normal", 1: "Poison", 2: "BadPoison"}
            if pokemon.status == "Normal":  # normal
                pokemon.status = toxic_spikes_effect[switch_side.entry_hazard["Toxic Spikes"]]


def sticky_web_entry_hazard(switch_side, pokemon):
    # ungrounded pokemon unaffected
    if pokemon.volatile_status['Grounded'] == 1:
        # ability is a list; "!= 'Clear Body'" was always true, so Clear Body
        # never protected anything here
        if not has_ability(pokemon, "Clear Body"):
            pokemon.modifier[5] -= 1 * switch_side.entry_hazard["Sticky Web"]
