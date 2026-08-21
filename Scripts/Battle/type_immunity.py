from Scripts.Art import narrator
def status_effect_immunity_check(user, target, move, status):
    if status == 'Paralysis':
        if "Ground" in target.type and "Electric" in move.type:
            narrator.say("Ground type is immune to electric paralysis moves.", "fail")
            return target.status
        elif "Electric" in target.type:
            narrator.say("Electric type is immune to paralysis.", "fail")
            return target.status
    elif status == 'Poison' or status == 'BadPoison':
        if "Poison" in target.type or "Steel" in target.type:
            narrator.say("Poison and Steel type is immune to poison moves.", "fail")
            return target.status
    elif status == 'Burn':
        if "Fire" in target.type:
            narrator.say("Fire type is immune to burning moves.", "fail")
            return target.status
    elif status == 'Freeze':
        if "Ice" in target.type:
            narrator.say("Ice type is immune to freezing moves.", "fail")
            return target.status
    return status