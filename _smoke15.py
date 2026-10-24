# -*- coding: utf-8 -*-
import day15_water_security as d

climate = {"rain_monthly": {1:25,2:20,3:30,4:60,5:120,6:180,7:160,8:150,9:110,10:140,11:90,12:40},
           "annual_rain":1125.0, "source":"test"}
SIMPLE = "Simple diversion → garden"
TREATED = "Treated recycling → toilet + garden"

r = d.plan_water(4, 130, 90, 0.85, 30, SIMPLE, climate)
for k in ["score","coverage_pct","rain_pct","grey_pct","total_daily","indoor_daily","garden_daily",
          "annual_coll","rain_supplied","grey_usable","tank_liters","tank_days","deficit_months","deficit_list","cost"]:
    print(f"{k:16} {r[k]}")

print("--- dry / no greywater ---")
dry = {"rain_monthly": {m:8 for m in range(1,13)}, "annual_rain":96.0, "source":"test"}
r2 = d.plan_water(4,130,90,0.85,0,"None",dry)
print("score",r2["score"],"cov",r2["coverage_pct"],"tank",r2["tank_liters"],"deficit",r2["deficit_months"])

print("--- wet / treated ---")
r3 = d.plan_water(2,80,150,0.90,10,TREATED,climate)
print("score",r3["score"],"cov",r3["coverage_pct"],"rain",r3["rain_pct"],"grey",r3["grey_pct"])

print("--- prompt builds ---")
p = d.build_roadmap_prompt(r, {"name":"Chennai","admin1":"Tamil Nadu","country":"India"})
print("prompt chars:", len(p))
