# Which Pokemon wins a straight fight

Every Pokemon against every other, one against one, 3 times in each
orientation. IVs are pinned to 31 on both sides and neither trainer
has a character ability, so the only thing that differs between two
sides is the species: its base stats, its typing, its movepool and
the ability it rolled.

This is deliberately *not* the same question as
`Documentation/ai_win_rate_table.md`, which ranks competitors. A
Pokemon's win rate inside those 6v6 battles mostly reflects whose
team it was on -- a high-rated competitor draws from a higher tier --
so this strips the team away entirely.

**What it cannot see:** anything whose value is to a *team*. Entry
hazards pay off over six slots, a pivot exists to leave, and a wall
that buys a turn for somebody else has nobody to buy it for. Those
Pokemon read as weak here and are not.

```
RANK  POKEMON                       WIN%      W     L     D   BST  TIER
--------------------------------------------------------------------------------
1     Memoraider                   96.1%   1499    60     1   730  Boss
2     Armadragdon                  95.2%   1485    68     7   730  Boss
3     Poseidon                     90.5%   1412   138    10   700  Boss
4     Pianotic                     89.8%   1401   150     9   609  Ultra High
5     Genesect                     83.4%   1301   255     4   600  Very High
6     Krusadian Salamence          81.7%   1274   284     2   600  Ultra High
7     Marshadow                    80.3%   1253   299     8   600  Very High
8     Douma                        79.4%   1238   315     7   610  Ultra High
9     Garchomp                     78.4%   1223   321    16   600  Very High
10    Faker-Greninja               78.3%   1221   327    12   640  Ultra High
11    Mega Scizor                  76.6%   1195   356     9   600  Very High
12    Victini                      74.5%   1162   391     7   600  Very High
13    Charizard                    74.4%   1160   373    27   534  High
14    Magearna                     73.6%   1148   392    20   600  Very High
15    Baxcalibur                   72.4%   1129   422     9   600  Very High
16    Dreadigo                     72.4%   1129   411    20   600  Ultra High
17    Brambleblood                 71.9%   1122   412    26   562  Very High
18    Heatran                      71.8%   1120   431     9   600  Very High
19    Dragonite                    71.0%   1108   439    13   600  Very High
20    Cinderace                    71.0%   1107   438    15   530  High
21    Mamoswine                    69.9%   1091   465     4   530  Medium
22    Kokushibo                    69.7%   1088   471     1   684  Boss
23    Jirachi                      69.2%   1080   473     7   600  Very High
24    Volcarona                    69.2%   1080   458    22   550  Very High
25    Darkrai                      68.7%   1072   478    10   600  Very High
26    Incineroar                   68.6%   1070   457    33   530  High
27    Xurkitree                    68.1%   1062   479    19   570  Very High
28    Kogoshaka                    67.9%   1060   487    13   681  Boss
29    Kingambit                    67.9%   1059   491    10   550  Very High
30    Milotic                      67.8%   1058   482    20   540  High
31    Volcanion                    66.9%   1044   498    18   600  Very High
32    Blaziken                     66.6%   1039   479    42   530  Very High
33    Dragapult                    65.6%   1024   531     5   600  Very High
34    Chesiquen                    65.5%   1022   523    15   580  Ultra High
35    Porygon-Z                    65.3%   1019   521    20   535  Very High
36    Metagross                    64.7%   1009   546     5   600  Very High
37    Bewear                       64.1%   1000   542    18   500  High
38    Gyutaro                      64.0%    999   547    14   450  Medium
39    Tanjiro                      64.0%    998   544    18   520  Very High
40    Durant                       63.8%    995   556     9   484  Medium
41    Charmorin                    63.7%    993   555    12   516  High
42    Scizor                       63.7%    993   551    16   500  High
43    Hydreigon                    63.5%    991   554    15   600  Very High
44    Gyarados                     63.3%    987   563    10   540  Very High
45    Mimikyu                      63.2%    986   392   182   476  High
46    Excadrill                    63.1%    985   558    17   508  High
47    Sylveon                      62.9%    982   564    14   525  High
48    Akaza                        62.8%    980   530    50   580  Very High
49    Ceruledge                    62.7%    978   572    10   525  High
50    Gardevoir                    62.6%    976   568    16   518  Medium
51    Boneknight                   62.5%    975   579     6   495  High
52    Revavroom                    62.4%    973   573    14   500  High
53    Spectrier                    62.4%    973   571    16   580  Very High
54    Inteleon                     62.1%    969   581    10   530  High
55    Scorchrome                   61.3%    956   589    15   509  High
56    Tinkaton                     61.3%    956   593    11   506  High
57    Kartana                      61.2%    954   593    13   570  Very High
58    Dracovish                    61.0%    951   593    16   505  High
59    Diggersby                    60.1%    938   602    20   423  Low
60    Weavile                      59.8%    933   620     7   510  Medium
61    Centiskorch                  59.7%    931   614    15   525  Medium
62    Togekiss                     59.6%    929   613    18   545  Very High
63    Espathra                     59.2%    924   630     6   481  High
64    Clawitzer                    59.2%    923   608    29   500  High
65    Fieritre                     59.2%    923   612    25   542  High
66    Nightdaunter                 59.2%    923   628     9   490  High
67    Copperajah                   59.0%    920   621    19   500  High
68    Arcanine                     58.7%    915   598    47   555  Very High
69    Vanilluxe                    58.4%    911   635    14   535  High
70    Pelipper                     58.3%    910   627    23   440  Medium
71    Goodra                       58.1%    907   629    24   600  High
72    Swampert                     58.1%    907   637    16   535  High
73    Empoleon                     58.0%    905   646     9   530  Medium
74    Kangaskhan                   58.0%    905   639    16   490  Low
75    Tyranitar                    58.0%    905   642    13   600  High
76    Archeops                     57.9%    903   637    20   567  High
77    Nihilego                     57.8%    901   645    14   570  Very High
78    Aerodactyl                   57.7%    900   646    14   515  High
79    Kommo-o                      57.6%    899   653     8   600  High
80    Heracross                    57.6%    898   629    33   500  Medium
81    Fairyflame                   57.3%    894   647    19   505  Very High
82    Haxorus                      56.9%    888   657    15   540  Very High
83    Blastoise                    56.5%    882   663    15   530  Medium
84    Lapras                       56.5%    881   641    38   535  Medium
85    Ygadr                        56.5%    881   669    10   558  High
86    Lucario                      56.4%    880   667    13   525  High
87    Naganadel                    56.4%    880   665    15   540  High
88    Vindaxe                      56.3%    879   679     2   530  Very High
89    Flygon                       56.3%    878   673     9   520  Medium
90    Mudsdale                     56.0%    874   676    10   500  Low
91    Delphox                      55.8%    871   669    20   534  Medium
92    Hantengu                     55.8%    871   655    34   520  High
93    Duraludon                    55.8%    870   677    13   535  Medium
94    Frosmoth                     55.6%    868   680    12   475  Medium
95    Greninja                     55.6%    868   679    13   530  High
96    Starmie                      55.5%    866   682    12   520  High
97    Sworphin                     55.5%    866   682    12   522  High
98    Bisharp                      54.8%    855   692    13   490  High
99    Hippowdon                    54.4%    849   696    15   525  Medium
100   Nidoking                     54.4%    849   674    37   505  High
101   Drampa                       54.4%    848   695    17   485  Medium
102   Celesteela                   54.2%    845   707     8   570  Very High
103   Roserade                     54.0%    842   708    10   515  High
104   Ninetales                    53.8%    839   708    13   505  High
105   Emmount                      53.3%    831   706    23   516  Medium
106   Overqwil                     53.3%    831   556   173   510  High
107   Toxtricity                   53.3%    831   722     7   502  High
108   Cloyster                     53.1%    829   722     9   525  High
109   Torterra                     52.9%    826   690    44   525  Medium
110   Kingdra                      52.5%    819   729    12   540  High
111   Ludicolo                     52.5%    819   726    15   480  Medium
112   Alolan Sandslash             52.1%    812   730    18   450  Medium
113   Nidoqueen                    52.1%    812   734    14   505  High
114   Tsareena                     51.9%    810   730    20   510  High
115   Medicham                     51.8%    808   721    31   410  Low
116   Machamp                      51.6%    805   735    20   505  High
117   Barraskewda                  51.5%    804   727    29   490  High
118   Crobat                       51.5%    803   737    20   535  Medium
119   Fezandipiti                  51.3%    800   715    45   555  High
120   Talonflame                   51.2%    798   701    61   499  Medium
121   Krookodile                   51.0%    796   751    13   519  Medium
122   Aegislash (Shield Forme)     50.8%    792   764     4   500  High
123   Yanmega                      50.6%    790   750    20   515  High
124   Dhelmise                     50.5%    788   757    15   517  Medium
125   Magnezone                    50.5%    788   759    13   535  High
126   Steelix                      50.4%    787   760    13   510  High
127   Gliscor                      50.4%    786   769     5   510  Medium
128   Aurorus                      49.8%    777   775     8   521  Medium
129   Beartic                      49.7%    776   757    27   505  Low
130   Rhyperior                    49.7%    775   779     6   535  Medium
131   Electivire                   49.6%    773   767    20   540  High
132   Glalie                       49.6%    773   772    15   480  Low
133   Venusaur                     49.6%    773   770    17   525  Medium
134   Infernape                    49.5%    772   722    66   534  High
135   Grimmsnarl                   49.4%    771   773    16   510  High
136   Landozer                     49.3%    769   774    17   495  Medium
137   Luxray                       49.2%    768   763    29   523  Low
138   Bruxish                      49.2%    767   773    20   475  High
139   Alolan Ninetales             49.1%    766   783    11   505  High
140   Perrserker                   49.1%    766   774    20   440  Low
141   Vikavolt                     49.1%    766   779    15   500  High
142   Noivern                      49.0%    765   780    15   535  Medium
143   Maruka                       48.9%    763   787    10   490  High
144   Dragalge                     48.5%    757   775    28   494  Medium
145   Pyroar                       48.5%    756   789    15   507  High
146   Eelektross                   48.3%    753   784    23   515  High
147   Psyvinstry                   48.3%    753   779    28   525  High
148   Tyrantrum                    47.4%    740   792    28   521  Medium
149   Ampharos                     47.2%    737   810    13   510  Medium
150   Boltund                      47.1%    734   811    15   490  Medium
151   Drapion                      46.9%    731   816    13   500  High
152   Avalugg                      46.8%    730   817    13   514  Medium
153   Blacephalon                  46.7%    728   683   149   570  High
154   Galarian Rapidash            46.6%    727   828     5   500  Medium
155   Stunfisk                     46.5%    726   817    17   471  Low
156   Ribombee                     46.5%    725   824    11   464  Low
157   Galvantula                   46.3%    723   826    11   472  High
158   Jellicent                    46.3%    722   764    74   480  Medium
159   Tangrowth                    46.3%    722   822    16   535  High
160   Araquanid                    46.2%    721   824    15   454  Medium
161   Rotom (Frost)                46.2%    720   833     7   520  High
162   Voltamelon                   46.0%    718   833     9   508  Medium
163   Honchkrow                    46.0%    717   776    67   505  High
164   Palossand                    46.0%    717   802    41   480  Low
165   Grapploct                    45.8%    715   828    17   480  Low
166   Gigalith                     45.5%    710   839    11   515  Medium
167   Masquerain                   45.4%    708   838    14   454  Medium
168   Slowbro                      45.3%    707   831    22   490  Medium
169   Gyokko                       45.3%    706   830    24   490  High
170   Aegislash (Blade Forme)      45.2%    705   846     9   500  Secret
171   Snorlax                      45.0%    702   698   160   540  Medium
172   Gengar                       44.8%    699   587   274   500  High
173   Breloom                      44.7%    698   848    14   460  Low
174   Tentacruel                   44.7%    698   839    23   515  High
175   Kingler                      44.4%    693   848    19   475  Very Low
176   Chandelure                   44.3%    691   862     7   520  High
177   Glimmora                     44.2%    690   866     4   525  High
178   Toxapex                      44.0%    686   849    25   495  Medium
179   Drednaw                      43.6%    680   864    16   485  Medium
180   Tauros                       43.5%    679   814    67   490  Medium
181   Umbreon                      43.5%    679   858    23   525  Low
182   Heliolisk                    43.5%    678   853    29   481  Medium
183   Scrafty                      42.9%    669   871    20   488  Medium
184   Sceptile                     42.7%    666   884    10   530  Medium
185   Mienshao                     42.5%    663   876    21   510  Medium
186   Bronzong                     42.4%    661   881    18   500  Low
187   Crabominable                 42.1%    656   883    21   478  Low
188   Cinccino                     42.0%    655   880    25   470  Medium
189   Azumarill                    41.7%    650   896    14   420  Medium
190   Relicanth                    41.4%    646   894    20   485  Low
191   Decidueye                    41.2%    643   890    27   530  High
192   Torkoal                      40.8%    636   903    21   470  Low
193   Krusadian Flygon             40.7%    635   913    12   520  Medium
194   Dedenne                      40.2%    627   920    13   431  Very Low
195   Kuroseh                      39.9%    623   917    20   448  Low
196   Hawlucha                     39.9%    622   922    16   500  Medium
197   Sigilyph                     39.9%    622   927    11   490  Medium
198   Harshock                     39.6%    618   923    19   494  Medium
199   Amoonguss                    39.6%    617   914    29   464  Medium
200   Lycanroc (Midnight)          39.3%    613   937    10   487  Medium
201   Galveon                      39.2%    612   907    41   525  Medium
202   Zoroark                      39.2%    611   924    25   510  Low
203   Klefki                       38.7%    604   937    19   470  Medium
204   Cofagrigus                   38.7%    603   873    84   483  Medium
205   Probopass                    38.4%    599   953     8   525  Low
206   Crustle                      38.3%    598   953     9   485  Low
207   Corviknight                  37.7%    588   929    43   495  Low
208   Donphan                      37.6%    587   961    12   500  Low
209   Trevenant                    37.6%    586   854   120   474  Low
210   Apoptoxitic                  37.3%    582   922    56   510  Medium
211   Mr.Rime                      36.7%    573   973    14   520  Low
212   Cradily                      36.5%    570   970    20   495  High
213   Noctowl                      36.3%    567   969    24   452  Low
214   Abomasnow                    35.7%    557   956    47   494  Medium
215   Sandaconda                   34.9%    544  1004    12   510  Low
216   Sawsbuck                     34.4%    537   997    26   475  Medium
217   Alolan Marowak               34.2%    534   981    45   425  Medium
218   Carnivine                    34.2%    534  1013    13   454  Very Low
219   Alakazam                     34.0%    531  1010    19   500  Medium
220   Appletun                     34.0%    531  1012    17   485  Medium
221   Alolan Raichu                33.3%    519  1018    23   485  Medium
222   Mawile                       33.3%    519  1032     9   380  Very Low
223   Ambipom                      32.7%    510  1034    16   482  Medium
224   Shedinja                     32.1%    501  1042    17   236  Low
225   Turtonator                   31.5%    491   885   184   485  Low
226   Rampardos                    30.6%    477   992    91   495  Low
227   Twinktwin                    30.6%    477  1052    31   468  Low
228   Swoobat                      30.3%    473  1078     9   425  Very Low
229   Orbeetle                     29.9%    466  1086     8   505  Low
230   Sudowoodo                    29.2%    455  1040    65   410  Low
231   Maractus                     28.7%    448  1096    16   461  Very Low
232   Altaria                      28.5%    445  1051    64   490  Low
233   Bibarel                      28.5%    444  1095    21   410  Low
234   Garbodor                     28.5%    444  1107     9   474  Very Low
235   Chimecho                     27.8%    434  1108    18   455  Low
236   Gambler                      27.8%    433  1103    24   540  Secret
237   Galarian Weezing             27.4%    427  1009   124   490  Medium
238   Alolan Exeggutor             27.0%    421  1116    23   530  Low
239   Parasect                     26.5%    413  1128    19   405  Very Low
240   Snowchild                    26.0%    406  1131    23   390  Very Low
241   Emolga                       24.4%    381  1163    16   428  Very Low
242   Primeape                     24.4%    380  1158    22   455  Very Low
243   Bastiodon                    23.8%    371  1175    14   495  Low
244   Froslass                     23.0%    359   850   351   480  Low
245   Onix                         23.0%    359  1191    10   385  Very Low
246   Shiftry                      21.1%    329  1104   127   480  Low
247   Farfetch'd                   20.6%    321  1160    79   377  Very Low
248   Spiritomb                    18.7%    291  1244    25   485  Low
249   Alolan Raticate              18.5%    289  1237    34   413  Very Low
250   Claydol                      18.3%    285  1212    63   500  Medium
251   Dusknoir                     14.5%    226  1190   144   525  Low
252   Beedrill                     14.3%    223  1319    18   395  Very Low
253   Luvdisc                      13.7%    213  1321    26   330  Very Low
254   Watchog                      13.5%    211  1324    25   420  Very Low
255   Whimsicott                   13.1%    205  1346     9   480  Low
256   Psyduck                      12.5%    195  1349    16   320  Very Low
257   Pikachu                      10.6%    166  1377    17   320  Very Low
258   Jumpluff                     10.4%    162  1394     4   460  Very Low
259   Ferrothorn                    5.7%     89  1345   126   489  Low
260   Sunkern                       1.5%     24  1505    31   180  Very Low
261   Magikarp                      1.0%     16  1523    21   200  Very Low
```


## Does the tier ladder match what happens

If the tiers are calibrated, average win rate should climb steadily
with the tier. Where it does not, the tier is the thing to fix.

```
TIER              N MEAN WIN%      BEST     WORST
--------------------------------------------------
Very Low         22     21.8%     44.4%      1.0%
Low              45     36.8%     60.1%      5.7%
Medium           72     46.9%     69.9%     18.3%
High             76     54.6%     74.4%     36.5%
Very High        33     66.8%     83.4%     54.2%
Ultra High        6     77.8%     89.8%     65.5%
Boss              5     83.9%     96.1%     67.9%
Secret            2     36.5%     45.2%     27.8%
```


## Pokemon in the wrong tier

Each Pokemon's rank compared with the middle of its own tier. A
large positive number means it beats the company it is keeping and
belongs a tier up; a large negative one means the reverse. This is
the same idea as the MOVE column in the competitor table.

```
POKEMON                  TIER          RANK     WIN%  PLACES FROM ITS TIER'S MIDDLE
------------------------------------------------------------------------------
Diggersby                Low             59    60.1%  +148
Kangaskhan               Low             74    58.0%  +133
Mamoswine                Medium          21    69.9%  +133
Mudsdale                 Low             90    56.0%  +117
Gyutaro                  Medium          38    64.0%  +116
Durant                   Medium          40    63.8%  +114
Gardevoir                Medium          50    62.6%  +104
Weavile                  Medium          60    59.8%  +94
Centiskorch              Medium          61    59.7%  +93
Medicham                 Low            115    51.8%  +92
Charizard                High            13    74.4%  +90
Pelipper                 Medium          70    58.3%  +84
Cinderace                High            20    71.0%  +83
Empoleon                 Medium          73    58.0%  +81
Beartic                  Low            129    49.7%  +78
...                                                   
Alolan Marowak           Medium         217    34.2%  -63
Alakazam                 Medium         219    34.0%  -65
Appletun                 Medium         220    34.0%  -66
Gyokko                   High           169    45.3%  -66
Alolan Raichu            Medium         221    33.3%  -67
Ambipom                  Medium         223    32.7%  -69
Gengar                   High           172    44.8%  -69
Celesteela               Very High      102    54.2%  -70
Tentacruel               High           174    44.7%  -71
Chandelure               High           176    44.3%  -73
Glimmora                 High           177    44.2%  -74
Galarian Weezing         Medium         237    27.4%  -83
Decidueye                High           191    41.2%  -88
Claydol                  Medium         250    18.3%  -96
Cradily                  High           212    36.5%  -109
```
