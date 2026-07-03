# reference_data.py — the fixed facts of the world.

# 31 real Karnataka districts. lat/lon ≈ district HQ. pop/literacy = APPROXIMATE placeholders.
# (district_id, name, lat, lon, population, literacy, urban_ratio)
DISTRICTS = [
    (1,  "Bengaluru Urban",   12.97, 77.59, 9600000, 0.87, 0.90),
    (2,  "Bengaluru Rural",   13.29, 77.59,  990000, 0.77, 0.35),
    (3,  "Mysuru",            12.30, 76.64, 3000000, 0.72, 0.41),
    (4,  "Belagavi",          15.85, 74.50, 4780000, 0.73, 0.31),
    (5,  "Kalaburagi",        17.33, 76.83, 2560000, 0.64, 0.33),
    (6,  "Dakshina Kannada",  12.87, 74.88, 2080000, 0.88, 0.48),
    (7,  "Dharwad",           15.36, 75.12, 1850000, 0.80, 0.57),
    (8,  "Ballari",           15.14, 76.92, 2450000, 0.67, 0.44),
    (9,  "Tumakuru",          13.34, 77.10, 2680000, 0.75, 0.23),
    (10, "Shivamogga",        13.93, 75.57, 1750000, 0.80, 0.35),
    (11, "Vijayapura",        16.83, 75.71, 2180000, 0.67, 0.24),
    (12, "Davanagere",        14.47, 75.92, 1940000, 0.76, 0.33),
    (13, "Bidar",             17.91, 77.52, 1700000, 0.71, 0.24),
    (14, "Raichur",           16.20, 77.36, 1930000, 0.60, 0.27),
    (15, "Hassan",            13.00, 76.10, 1780000, 0.77, 0.18),
    (16, "Mandya",            12.52, 76.90, 1810000, 0.70, 0.16),
    (17, "Udupi",             13.34, 74.75, 1180000, 0.86, 0.29),
    (18, "Chitradurga",       14.23, 76.40, 1660000, 0.73, 0.20),
    (19, "Kolar",             13.13, 78.13, 1540000, 0.74, 0.32),
    (20, "Bagalkot",          16.18, 75.70, 1890000, 0.68, 0.29),
    (21, "Gadag",             15.43, 75.63, 1060000, 0.75, 0.35),
    (22, "Haveri",            14.80, 75.40, 1600000, 0.77, 0.21),
    (23, "Koppal",            15.35, 76.15, 1390000, 0.67, 0.17),
    (24, "Chikkamagaluru",    13.32, 75.77, 1140000, 0.79, 0.19),
    (25, "Chikkaballapur",    13.43, 77.73, 1250000, 0.70, 0.19),
    (26, "Kodagu",            12.42, 75.74,  550000, 0.82, 0.15),
    (27, "Chamarajanagar",    11.92, 76.94, 1020000, 0.61, 0.17),
    (28, "Ramanagara",        12.72, 77.28, 1080000, 0.69, 0.24),
    (29, "Yadgir",            16.77, 77.14, 1170000, 0.52, 0.19),
    (30, "Uttara Kannada",    14.81, 74.13, 1440000, 0.84, 0.29),
    (31, "Vijayanagara",      15.27, 76.39, 1350000, 0.66, 0.30),
]

STATIONS_PER_DISTRICT = (3, 6)   # generate this many police stations per district

# Crime heads (major categories)
CRIME_HEADS = [
    (1, "Crimes Against Body"),
    (2, "Property Crime"),
    (3, "Economic & Cyber"),
    (4, "Crimes Against Women"),
    (5, "Public Order"),
    (6, "Narcotics"),
]

# Crime sub-heads: (id, parent_head_id, name, base_weight, hotspot_prone, time_bias)
# base_weight  = how common (relative). hotspot_prone = clusters in space if True.
# time_bias    = "weekend_evening" | "night" | "daytime" | "uniform"
CRIME_SUBHEADS = [
    (101, 1, "Murder",              2,  False, "night"),
    (102, 1, "Attempt to Murder",   3,  False, "night"),
    (103, 1, "Grievous Hurt",       8,  False, "weekend_evening"),
    (104, 1, "Simple Hurt",        14,  False, "weekend_evening"),
    (105, 1, "Kidnapping",          3,  False, "uniform"),
    (201, 2, "House Burglary",     16,  True,  "night"),
    (202, 2, "Theft",              22,  True,  "daytime"),
    (203, 2, "Chain Snatching",     9,  True,  "weekend_evening"),
    (204, 2, "Vehicle Theft",      13,  True,  "night"),
    (205, 2, "Robbery",             6,  True,  "night"),
    (206, 2, "Dacoity",             2,  True,  "night"),
    (301, 3, "Cheating / Fraud",   12,  False, "daytime"),
    (302, 3, "Online Financial Fraud", 15, False, "uniform"),
    (303, 3, "Cyber Harassment",    5,  False, "night"),
    (401, 4, "Assault on Women",    7,  False, "weekend_evening"),
    (402, 4, "Dowry-related",       4,  False, "uniform"),
    (403, 4, "Domestic Cruelty",    9,  False, "uniform"),
    (501, 5, "Rioting",             4,  False, "daytime"),
    (502, 5, "Unlawful Assembly",   5,  False, "daytime"),
    (503, 5, "Public Nuisance",     8,  False, "weekend_evening"),
    (601, 6, "Drug Possession",     6,  True,  "night"),
    (602, 6, "Drug Trafficking",    3,  True,  "night"),
]

# Sub-head -> legal sections it typically invokes (Act "IPC" for demo simplicity)
SUBHEAD_SECTIONS = {
    101: ["302"], 102: ["307"], 103: ["325", "326"], 104: ["323"], 105: ["363", "365"],
    201: ["454", "457"], 202: ["379", "380"], 203: ["356", "379"], 204: ["379"],
    205: ["392"], 206: ["395"], 301: ["420"], 302: ["420", "66D"], 303: ["354D", "67"],
    401: ["354"], 402: ["498A", "304B"], 403: ["498A"], 501: ["147", "148"],
    502: ["143"], 503: ["268"], 601: ["27"], 602: ["21", "29"],
}

CASE_CATEGORIES = [   # (id, code_digit, name) — first digit of CrimeNo
    (1, 1, "FIR"),
    (2, 3, "UDR"),
    (3, 4, "PAR"),
    (4, 8, "Zero FIR"),
]

GRAVITY = [(1, "Heinous"), (2, "Non-Heinous")]

CASE_STATUS = [
    (1, "Under Investigation"),
    (2, "Charge Sheeted"),
    (3, "Convicted"),
    (4, "Closed"),
    (5, "False Case"),
]

OCCUPATIONS = [
    (1, "Farmer"), (2, "Labourer"), (3, "Business"), (4, "Student"),
    (5, "Government Employee"), (6, "Private Employee"), (7, "Unemployed"),
    (8, "Homemaker"), (9, "Driver"), (10, "Retired"),
]

UNIT_TYPES = [(1, "Police Station"), (2, "Circle Office"), (3, "District Office")]
