def status_effect_immunity_check(user, target, move, status):
    if status == 'Paralysis':
        if "Ground" in target.type and "Electric" in move.type:
            print("Ground type is immune to electric paralysis moves.")
            return target.status
        elif "Electric" in target.type:
            print("Electric type is immune to paralysis.")
            return target.status
    elif status == 'Poison' or status == 'BadPoison':
        if "Poison" in target.type or "Steel" in target.type:
            print("Poison and Steel type is immune to poison moves.")
            return target.status
    elif status == 'Burn':
        if "Fire" in target.type:
            print("Fire type is immune to burning moves.")
            return target.status
    elif status == 'Freeze':
        if "Ice" in target.type:
            print("Ice type is immune to freezing moves.")
            return target.status
    return status