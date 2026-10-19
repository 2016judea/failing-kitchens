"""Which trade fixes a violation. Deterministic regexes over the inspector's own words and the
rule cited, nothing learned. Tuned by hand-reading samples on 2026-10-18 (see tests/test_model.py
for the fixed cases). A flag the regexes miss simply does not ship; a flag misfiled is the risk
we accept and say so on the page.

  refrigeration  a cooler, freezer, walk-in, prep table or ice machine that is out of temp or in
                 disrepair. NOT food left out on a counter or in an ice bath: that is a kitchen
                 habit, and no refrigeration tech can sell to it.
  pest           evidence of pests (droppings, flies, roaches, mice) or a cited pest-control rule.
                 NOT 'seal the gap under the door': prevention is the owner's job, not a service call.
  hood           a hood, baffles, exhaust duct, grease build-up or fire suppression, including
                 equipment that must move under a hood or a hood that is missing.
"""
import re

UNIT = re.compile(r"cooler|refrigerat|freezer|walk[- ]?in|reach[- ]?in|low[- ]?boy|prep (table|unit)|sandwich unit|"
                  r"cold (well|line|rail|top|drawer)|coldwell|ice (machine|maker)|display case|merchandiser|\bunits?\b", re.I)
UNIT_FAULT = re.compile(r"ambient|not (holding|maintain|working|cool|keep)|unable to (hold|maintain|keep)|repair|service|"
                        r"broken|malfunction|compressor|condens|thermostat|out of order|do not use|discontinue use|"
                        r"troubleshoot|adjust|(unit|cooler|freezer|refrigerator|walk[- ]?in|reach[- ]?in|lowboy|low boy|drawer)s?[^.]{0,40}"
                        r"(above|at|reading|holding|was|were|is|are)[^.]{0,12}\d{2}\s?(°|\*|degrees| ?f\b)|gasket|door (seal|does not close)|"
                        r"frost|ice build|leak", re.I)
NOT_UNIT = re.compile(r"ice bath|room temp|on (the )?(counter|line|table|cart)|out of temperature control|left out|"
                      r"sitting out|held out|time as a public health control|tphc|overstock|over ?fill|above the (fill|load) line|"
                      r"lid open|door (was |left )?(open|ajar)", re.I)
PEST_EVIDENCE = re.compile(r"rodent|\bmice\b|\bmouse\b|\brats?\b|\bdroppings?\b|cockroach|\broach(es)?\b|\bflies\b|\bfly\b|"
                           r"fruit fl|drain fl|\bgnats?\b|infest|vermin|maggot|larvae|\bants?\b", re.I)
PEST_CODES = {"MN Rule 4626.1565ABD", "MN Rule 4626.1565C", "MN Rule 4626.1570", "MCO 188.590", "MN Rule 4626.1385B"}
HOOD = re.compile(r"\bhoods?\b|exhaust|baffles?\b|\bduct(s|work)?\b|ansul|fire suppression|make[- ]?up air|"
                  r"ventilation (hood|system|duct|fan)s?|ventilation above", re.I)
# A hood mentioned only as a landmark or an aside, or a dish machine's hood, is not a hood job
# (hand-read 2026-10-19: ~30% of the first cut was grease on floors, cooler handles, or
# "the cooler across from the hood"). Grease build-up alone no longer routes here.
HOOD_NOISE = re.compile(r"\((e\.?g|ie)[^)]*\)|(across from|next to|near|by|beside|opposite) (the )?(\w+ )?hoods?\b|"
                        r"dish ?(machine|washer)('s)? hoods?|plan[- ]?review", re.I)
ICE = re.compile(r"ice (machine|maker)", re.I)
HOOD_CODES = {"MN Rule 4626.1530A", "MN Rule 4626.1475A"}
REFRIG_CODES = {"MN Rule 4626.0395A2", "MN Rule 4626.0735AB", "MN Rule 4626.0840C", "MN Rule 4626.0855"}

LABEL = {"refrigeration": "Refrigeration / HVAC-R", "pest": "Pest control", "hood": "Hood & exhaust cleaning"}
ORDER = ["refrigeration", "pest", "hood"]


def trade_of(code, comment):
    """-> 'refrigeration' | 'pest' | 'hood' | None. `code` is FoodCodeItem, `comment` InspectorComments."""
    c = comment or ""
    code = code or ""
    if code in PEST_CODES or PEST_EVIDENCE.search(c):
        return "pest"
    if code in REFRIG_CODES and UNIT.search(c) and UNIT_FAULT.search(c) and not NOT_UNIT.search(c):
        return "refrigeration"
    h = HOOD_NOISE.sub(" ", c)
    if (code in HOOD_CODES and not HOOD_NOISE.search(c)) or (HOOD.search(h) and not (ICE.search(h) and not re.search(r"\bhoods?\b|exhaust", h, re.I))):
        return "hood"
    return None
