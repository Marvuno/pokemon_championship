Test/ -- offline tools. None of these are part of the game, none read or
write a save, and none are needed to play. Run them from the project root.


opponent_ladder.py      Which competitors are actually stronger?

    Every competitor plays every other one five times with the AI driving
    both sides, and the results become a ladder. The interesting column is
    "vs rating": where they finished on win rate minus where their
    Data/competitors.csv rating says they should have. Positive means the
    rating undersells them, negative means it flatters them.

        python Test/opponent_ladder.py                    all of them
        python Test/opponent_ladder.py --only Elite Champion
        python Test/opponent_ladder.py --pair Goblin "Monkey King"
        python Test/opponent_ladder.py --repeat 10 --seed 7

    Roughly five battles a second, so the full round robin is about half an
    hour; --only and --pair are how you ask a narrower question quickly.
    Writes Documentation/opponent_ladder.txt.

    Teams are rolled the way the game rolls them -- from each competitor's
    own rating, plus whichever Pokemon the CSV pins to them -- so this
    measures the competitor, roster and all.


ai_simulation.py        Which Pokemon are actually stronger?

    The older sibling: same battle engine, but random teams, so it measures
    the Pokemon rather than the competitors. Edit `mode` and `repeat` at the
    top. Results in Documentation/ai_sim_win_rate.txt.


build_custom_sprites.py Turn a custom art file into left/right battle GIFs
sharpen_sprites.py      Pre-scale sprites so Qt is not upscaling a 64px GIF
image_builder.py        Sprite sheet helper
stats.py                Pokemon stat spreadsheet helper


A note on running these: thousands of AI-vs-AI battles is the best bug
detector this project has -- the phantom-move-slot IndexError in
Scripts/Battle/ai.py surfaced at battle 1,900 of 7,700. opponent_ladder.py
therefore counts a battle the engine cannot finish and names it at the end
rather than taking the whole run down with it.
