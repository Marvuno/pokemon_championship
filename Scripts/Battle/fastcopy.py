"""A deepcopy for the shapes this engine actually holds.

`copy.deepcopy` is the single largest cost in a battle. The AI copies a
Pokemon and a Move for every candidate move it scores, every turn, and the
generic machinery -- dispatch through `__reduce_ex__`, a memo entry for every
object -- costs far more than these objects are worth. Measured on this
machine: a Move 26.5us against 3.6us, a Pokemon 49.2us against 5.1us.

The copies themselves are not optional. They are what stops the AI's scoring
from writing on the real board, and the engine has already been bitten hard
by exactly that (see the shared-move-table note in CLAUDE.md). So this is a
faster copy, not one copy fewer.

**It keeps the memo.** Two attributes pointing at one list must still point at
one list afterwards, or an edit through one stops being visible through the
other -- and the engine does alias: switching hands a Pokemon its own
`default_type` list, and `previous_move` holds a live Move.

**It treats as atomic exactly what deepcopy treats as atomic**, functions
included. A Move carries a callable in `special_effect`, and copying that
rather than sharing it would be both wrong and slower.

Anything it does not recognise falls through to `copy.deepcopy`, so an object
shape added later is copied correctly rather than quietly shallowly.

Equivalence is asserted two ways in Test/gui/test_engine_integrity.py: field
by field against deepcopy over every Move and every Pokemon in the game, and
end to end by Test/gui/fingerprint.py, which replays forty battles from a
fixed seed and compares every transcript.
"""
import copy
import types

#: what deepcopy hands back unchanged, and so must this
_ATOMIC = frozenset((
    int, float, bool, complex, str, bytes, bytearray, type(None),
    type, types.FunctionType, types.BuiltinFunctionType, types.MethodType,
    types.ModuleType, range, frozenset, slice,
))

_deepcopy = copy.deepcopy


def fast_copy(obj, memo=None):
    """A deep copy of `obj`, equivalent to `copy.deepcopy(obj)`."""
    kind = type(obj)
    if kind in _ATOMIC:
        return obj

    if memo is None:
        memo = {}
    key = id(obj)
    seen = memo.get(key)
    if seen is not None:
        return seen

    # The atomic test is inlined into these two loops rather than left to the
    # recursive call. Nearly everything in this engine's containers is a
    # number or a string -- stat arrays, IVs, move names, the volatile-status
    # counters -- and a Python function call per element was most of the cost
    # of copying at all: 2.8 million calls over twenty-five battles, against
    # 63,000 objects actually copied.
    if kind is list:
        clone = []
        memo[key] = clone                    # before recursing, for cycles
        append = clone.append
        for item in obj:
            append(item if type(item) in _ATOMIC else fast_copy(item, memo))
        return clone
    if kind is dict:
        clone = {}
        memo[key] = clone
        for name, value in obj.items():
            # keys are strings throughout; copy one only if it is not atomic
            if type(name) not in _ATOMIC:
                name = fast_copy(name, memo)
            clone[name] = (value if type(value) in _ATOMIC
                           else fast_copy(value, memo))
        return clone
    if kind is tuple:
        clone = tuple(fast_copy(item, memo) for item in obj)
        memo[key] = clone
        return clone
    if kind is set:
        clone = {fast_copy(item, memo) for item in obj}
        memo[key] = clone
        return clone

    # A plain object: rebuild it without running __init__, then copy its
    # attributes. Only for classes that keep their state in __dict__ and
    # define no copying protocol of their own -- anything else is deepcopy's
    # business, and it knows how.
    # `__deepcopy__` looked up on the class, not the instance: every object
    # inherits __reduce_ex__ and (since 3.11) __getstate__ from object, so
    # asking hasattr about those sends everything to deepcopy and buys
    # nothing. A class that wants to control its own copying says so by
    # defining one of these itself.
    state = getattr(obj, "__dict__", None)
    if (state is None or kind.__module__ == "builtins"
            or getattr(kind, "__deepcopy__", None) is not None
            or getattr(kind, "__copy__", None) is not None
            or "__reduce__" in kind.__dict__
            or "__getstate__" in kind.__dict__):
        return _deepcopy(obj, memo)
    clone = object.__new__(kind)
    memo[key] = clone
    fresh = {}
    for name, value in state.items():
        fresh[name] = (value if type(value) in _ATOMIC
                       else fast_copy(value, memo))
    clone.__dict__ = fresh
    return clone
