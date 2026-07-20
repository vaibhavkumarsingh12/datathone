# SPEAR Intelligence Brief — Synthetic Karnataka, Jan 2023 – Jan 2026

**Prepared by:** themamba_bros · KSP Datathon 2026 · Challenge 2
**Data:** 10,770 synthetic FIRs across 31 districts, grounded in NCRB/SCRB aggregates.
Ground-truth patterns were planted in the data, sealed in `data/ground_truth/`, and used
**only to validate** — never to train, and never read by the dashboard.

---

## 1 · The situation

A commissioner sees 10,770 FIRs as a spreadsheet: one row per case, no memory of people,
no map of pressure, no sense of what comes next. SPEAR reads the same records and returns
**four decisions** — where to patrol, who to investigate, what to expect, and what doesn't fit.

---

## 2 · Where and when to patrol  *(Spatial + Pattern)*

Theft is the single largest category at **1,245 cases (12% of all crime)**, but volume is
the wrong lens for deployment — concentration is the right one.

- **Space:** DBSCAN (ε = 2 km, min 25 cases) isolates **4 patrol-sized hotspots that hold
  19% of all cases** — zones an officer can actually be assigned to, not pixel noise.
- **Per-capita pressure:** **Kalaburagi, Ballari and Raichur** carry the heaviest load at
  up to **22 cases per 100k** — a different list than raw counts would give.
- **Time:** incidents peak **Saturday around 22:00**, with **23% of all incidents falling in
  the weekend-evening window**. That is a shift roster, not a statistic.

> **Recommended action:** weight weekend-evening strength toward the four detected hotspot
> clusters, prioritising the three high per-capita districts.

---

## 3 · Who to investigate  *(Entity-network)*

The official schema has no persistent person identity — its PersonID resets every case, so
the same individual appears as unrelated accused across FIRs.

- Entity resolution collapsed **11,069 accused records into 8,911 distinct identities**,
  scoring **F1 0.910** against sealed truth (precision 0.859, recall 0.969).
- Louvain community detection over **102 co-offence edges** recovered **4 of 4 planted
  rings**, at **100% coverage and 100% purity**.
- Centrality finds leadership: **10 of the top-10 betweenness entities were confirmed ring
  members**.
- The money shot: **Entity 702, "Prakash Shetty" — 5 aliases across 18 cases**, one person
  the source system records as five strangers.

> **Recommended action:** open ring dossiers on the four detected communities; treat the
> highest-betweenness entities as connectors, not foot soldiers.

---

## 4 · What to expect next  *(Risk)*

A gradient-boosting model scored district × crime-type × month cells and was validated on a
**temporal holdout** — trained on the past, tested on six months it never saw.

- Patrolling the model's **top-20 cells captures 47.5% of next-window crime**.
- That is a **16.2× lift over random allocation** (random expectation 2.9%), and it also
  beats the naive "same as last month" persistence baseline (37.5%).
- **1,725 cells** currently sit in the High band — the top-decile shortlist.
- Band calibration behaves correctly: High-band cells realise **1.24×** their expected
  crime, Low-band only **0.20×**.

> **Recommended action:** allocate reserve strength against the top-20 list each month;
> High-band is scarce enough to be actionable.

---

## 5 · What doesn't fit  *(Anomaly)*

Two complementary detectors, one case-level and one aggregate-level.

- **IsolationForest flagged 108 incidents** (a ~1% triage budget) whose feature
  combinations break their local pattern — e.g. an unusual time of day for that crime type.
- **Z-scoring surfaced 4 month-level spikes above 2.5σ.** The most extreme:
  **Kalaburagi's Drug Possession ran 186σ above its own baseline in Nov 2024 — 141 cases
  against ~1 expected.** That planted eruption was recovered blind.
- Honest limit: against the planted case-level anomalies, recall at the 2% triage budget is
  **0.27 (73 of 270 recovered)** — this layer is a prioritiser for analyst attention, not a
  complete census of every oddity.
- **The why:** OLS on district profiles shows **literacy is the strongest socio-economic
  driver (β = −18.881, p = 0.0003, r = −0.524)** — districts with lower literacy carry
  structurally higher crime per 100k.

> **Recommended action:** route the 108 flagged cases to review; treat low-literacy
> districts as *structural* risk, not seasonal noise.

---

## 6 · Why these numbers can be trusted

Every module sat a blind exam. Patterns were planted in the synthetic data, sealed in
`data/ground_truth/`, and the platform — which never reads that folder — had to rediscover
them. Each metric quoted above is read directly from `reports/module2_metrics.json` and
`reports/module3_metrics.json`; the dashboard quotes the same files, so the deck, the report
and the live app cannot disagree.

Where a result is modest (anomaly recall 0.27), it is reported as-is rather than reframed.

---

## 7 · One sentence

> **SPEAR turns 10,770 fragmented FIRs into four decisions — where to patrol, who to
> investigate, what to expect, and what doesn't fit — computed offline against a sealed
> exam and served from a stateless read layer that boots in 1.3 s and answers in
> under 50 ms on Zoho Catalyst.**

---

*Live dashboard:* `https://spear-intel-50043295151.development.catalystappsail.in`
*Local research console:* `streamlit run app/streamlit_app.py`
